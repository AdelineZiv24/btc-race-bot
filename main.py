"""cbBTC bar-replay bot v4 (agent-fun/bars-replay/v1), Python 3.13 stdlib only.

Design: staged mean reversion with a persistence-checked entry, full-size
tranches, a light first bank, a deeper final target for two-tranche
positions, and one large re-entry after the bank.

The dev window's 1-minute bars revert after sharp drops under a slow mean,
but a round trip here is expensive (4 bps fee, 2 bps slippage, plus
constant-product impact against each bar's pool depth), so the bot only
trades deep, decelerating dips — and before entering it asks that the dip
be a regime, not a flicker: the deviation must have closed at or under
-30 bps on at least 8 of the last 12 bars. Then:

  - Anchor: EMA of the last 300 closes; deviation = close vs anchor, bps.
  - Entry: deviation <= -40 bps, the last 15 bars not in freefall (their
    return above -15 bps), and the persistence check above. First tranche:
    60% of equity.
  - Add-on: one extra tranche of 40% of equity if the deviation deepens to
    -70 bps; never more than these two tranches.
  - Take-profit, step 1: at deviation >= +10 bps, sell 35% of the position
    — a light bank that keeps most of the size on for the real recovery.
  - Take-profit, step 2: the rest goes at deviation >= +35 bps — or at
    +50 bps when the position holds both tranches: a dip deep enough to
    trigger the add-on has further to recover, and the extra room is worth
    more than the earlier exit.
  - Re-entry: once step 1 has banked, if the price sinks back to -40 bps
    while the remainder is still held, buy back in once with 40% of
    equity — the same dip, sold twice.
  - Risk exits, either step: a hard stop 90 bps under the average entry
    price, or 420 bars held, sells whatever remains.
  - Five quiet bars after every exit; no fresh entries in the last 20 bars
    of the window, where a fill would only pay costs.

Deterministic: the reply is a pure function of the bars seen. No clock, no
network, no files, no randomness.
"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

ANCHOR_SPAN = 300        # EMA length for the mean we revert to
DIP_BPS = -40.0          # first tranche at or under this deviation
DEEPER_BPS = -70.0       # add-on tranche at or under this deviation
FREEFALL_BPS = -15.0     # 15-bar return must stay above this to enter
FIRST_SHARE = 0.60       # first tranche, share of equity
ADDON_SHARE = 0.40       # add-on tranche, share of equity
BANK_BPS = 10.0          # take-profit step 1 at this deviation
BANK_FRAC = 0.35         # step 1 sells this fraction of the position
DONE_BPS = 35.0          # take-profit step 2: sell the rest here
DONE_DEEP_BPS = 50.0     # step 2 when both tranches are in: let it run
REENTRY_SHARE = 0.40     # one rebuy after banking, share of equity
PERSIST_BPS = -30.0      # entry persistence: deviation at/under this ...
PERSIST_HITS = 8         # ... on at least this many of the last ...
PERSIST_BARS = 12        # ... this many bars
STOP_BPS = 90.0          # hard stop under the average entry price
TIME_STOP = 420          # bars
REST_BARS = 5            # cooldown after an exit
SLIP_CAP = 200           # max_slippage_bps guard on every order
FINAL_ENTRY_SEQ = 1420   # 1,440-batch window: later entries only pay costs
MIN_BUY = 1_000_000      # harness minimum notional (quote units)


class StagedReversion:
    """One position at a time: 0 = flat, 1 = first tranche in, 2 = added."""

    def __init__(self):
        self.mean = None               # EMA of closes
        self.recent = deque(maxlen=512)  # closes, for the 15-bar return
        self.devs = deque(maxlen=64)     # deviations, for the entry check
        self.stage = 0
        self.book_cost = 0             # position cost at the last fill seen
        self.book_qty = 0
        self.avg_entry = 0.0           # average fill price (raw price units)
        self.opened_seq = -1
        self.banked = False            # take-profit step 1 already taken
        self.reentered = False         # the one post-bank rebuy already used
        self.expect_reentry = False    # a rebuy order is in flight
        self.awaiting = 0              # batches to let an order land
        self.rest = 0                  # cooldown batches left

    # -- order plumbing ---------------------------------------------------
    def _send(self, spec):
        self.awaiting = 1
        return [spec]

    def _buy(self, state, share):
        spend = min(state.cash, int(state.equity * share))
        room = state.weight_room(SYMBOL)
        if room is not None:
            spend = min(spend, room)
        if spend < MIN_BUY:
            return None
        return self._send({"side": "buy", "symbol": SYMBOL,
                           "notional_quote_units": spend,
                           "max_slippage_bps": SLIP_CAP})

    def _sell(self, qty):
        return self._send({"side": "sell", "symbol": SYMBOL, "qty": qty,
                           "max_slippage_bps": SLIP_CAP})

    # -- bookkeeping ------------------------------------------------------
    def _sync_position(self, state):
        """Fold the account's position into our stage counter; fills are
        recognised by the booked cost/quantity changing between batches."""
        pos = state.positions.get(SYMBOL)
        held = pos is not None and pos.qty > 0
        if held and (pos.cost != self.book_cost or pos.qty != self.book_qty):
            if self.stage == 0:
                self.stage = 1
                self.opened_seq = state.seq
                self.banked = False
                self.reentered = False
            elif pos.qty > self.book_qty:
                if self.expect_reentry:
                    # the rebuy landed: same stage, not an add-on
                    self.expect_reentry = False
                else:
                    self.stage = 2     # the add-on landed
            self.avg_entry = pos.cost * 10**7 / pos.qty
            self.book_cost = pos.cost
            self.book_qty = pos.qty
        elif not held and self.stage:
            self.stage = 0
            self.book_cost = 0
            self.book_qty = 0
            self.rest = REST_BARS
        return held

    # -- entry quality ------------------------------------------------------
    def _dip_is_real(self):
        """The dip must be a regime, not a flicker: the deviation closed at
        or under PERSIST_BPS on at least PERSIST_HITS of the last
        PERSIST_BARS bars (the current bar included)."""
        recent = list(self.devs)[-PERSIST_BARS:]
        if len(recent) < PERSIST_BARS:
            return False
        return sum(1 for d in recent if d <= PERSIST_BPS) >= PERSIST_HITS

    # -- decisions ----------------------------------------------------------
    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return None
        price = float(close)
        self.recent.append(price)
        if self.mean is None:
            self.mean = price
        else:
            self.mean += (2.0 / (ANCHOR_SPAN + 1)) * (price - self.mean)
        dev_bps = (price / self.mean - 1.0) * 10000.0
        self.devs.append(dev_bps)

        held = self._sync_position(state)

        if self.awaiting:
            # an order decided last batch fills at this bar's open; give the
            # account one batch to show it before deciding anything else
            self.awaiting += 1
            if self.awaiting > 2:
                self.awaiting = 0
            else:
                return None
        if state.warming_up:
            return None

        if held:
            pos = state.positions[SYMBOL]
            # a two-tranche position entered on a deeper dip: its recovery
            # has further to travel, so the final exit waits for +50 bps
            done_bps = DONE_DEEP_BPS if self.stage == 2 else DONE_BPS
            if not self.banked and dev_bps >= BANK_BPS:
                # recovery reached: bank a light slice, keep the rest on
                self.banked = True
                return self._sell(max(1, int(pos.qty * BANK_FRAC)))
            if self.banked and dev_bps >= done_bps:
                return self._sell(pos.qty)
            if price <= self.avg_entry * (1.0 - STOP_BPS / 10000.0):
                return self._sell(pos.qty)
            if state.seq - self.opened_seq >= TIME_STOP:
                return self._sell(pos.qty)
            if self.stage == 1 and dev_bps <= DEEPER_BPS:
                return self._buy(state, ADDON_SHARE)
            if self.banked and not self.reentered and dev_bps <= DIP_BPS:
                # banked a slice, price sank back to the entry dip: buy back
                # in once and sell the same recovery a second time
                self.reentered = True
                self.expect_reentry = True
                return self._buy(state, REENTRY_SHARE)
            return None

        if self.rest:
            self.rest -= 1
            return None
        if state.seq > FINAL_ENTRY_SEQ or len(self.recent) <= 16:
            return None
        ret15 = (price / self.recent[-16] - 1.0) * 10000.0
        if dev_bps <= DIP_BPS and ret15 > FREEFALL_BPS and self._dip_is_real():
            return self._buy(state, FIRST_SHARE)
        return None


_BOT = StagedReversion()


def on_batch(state, batch):
    return _BOT.on_batch(state, batch)


makefun_bars.run(on_batch)
