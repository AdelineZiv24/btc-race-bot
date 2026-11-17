"""Clik's cbBTC bar-replay bot (agent-fun/bars-replay/v1), Python 3.13 stdlib only.

Strategy: slow-mean reversion with cascade protection, long only.

This pool's 1-minute bars revert: sharp drops under the slow mean are
followed, over the next half hour or so, by a bounce, while strength just as
reliably fades (and long-only cannot fade anything). A full-size round trip
costs roughly 35-40 bps here once the 4 bps fee, 2 bps slippage and the
constant-product impact against the bars' real depth are paid, so the bot
trades rarely, at moderate size, and only when price is far enough under its
slow mean for the expected bounce to clear those costs:

  - Mean: EMA of the last 300 closes. Deviation is the close's distance
    from it, in bps.
  - Entry: deviation <= -40 bps, but only when the last 15 bars are not in
    freefall (their return above -15 bps): buy the dip once it stops
    accelerating, not while it is still cascading.
  - Add-on: if the deviation deepens to -70 bps, one extra tranche of 35%
    of equity joins the position (deeper dips revert harder); never twice.
  - Size: 45% of equity for the first tranche, so impact stays small.
  - Exits: deviation back above +10 bps (the reversion is done), a hard
    stop 90 bps under the average entry price, or 420 bars held.
  - A 5-bar cooldown after every exit; no entries in the last 20 bars of
    the window, where a fill would only pay costs.

Deterministic: closes in, orders out. No clock, no network, no randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

EMA_SPAN = 300
ENTER_DEV_BPS = -40.0     # buy at or under this deviation from the slow mean
ADD_DEV_BPS = -70.0       # add once at or under this deeper deviation
EXIT_DEV_BPS = 10.0       # sell once the deviation recovers to here
DECEL_BPS = -15.0         # 15-bar return must be above this to enter (no freefall)
SIZE_FRAC = 0.45          # first tranche, share of equity
ADD_FRAC = 0.35           # add-on tranche, share of equity
STOP_BPS = 90.0           # hard stop under the average entry price
MAX_HOLD = 420            # bars
COOLDOWN = 5              # bars to sit out after an exit
SLIP_BPS = 200            # max_slippage_bps guard on every order
LAST_ENTRY_SEQ = 1420     # windows are 1,440 batches; late entries only pay costs
MIN_NOTIONAL = 1_000_000  # the harness's minimum buy (fees.min_notional_quote_units)


class Bot:
    def __init__(self):
        self.ema = None
        self.closes = []            # raw closes, one per bar seen (for the 15-bar return)
        self.holding = False
        self.last_cost = 0          # booked cost of the open position, to spot fills
        self.entry_price = 0.0      # average fill price (raw units)
        self.entry_seq = -1
        self.added = False
        self.pending = 0            # batches since an order was sent, awaiting its effect
        self.cooldown = 0

    def order(self, state, spec):
        self.pending = 1
        return [spec]

    def buy(self, state, frac):
        notional = min(state.cash, int(state.equity * frac))
        room = state.weight_room(SYMBOL)
        if room is not None:
            notional = min(notional, room)
        if notional < MIN_NOTIONAL:
            return None
        return self.order(state, {"side": "buy", "symbol": SYMBOL,
                                  "notional_quote_units": notional,
                                  "max_slippage_bps": SLIP_BPS})

    def sell(self, state, holding):
        return self.order(state, {"side": "sell", "symbol": SYMBOL,
                                  "qty": holding.qty,
                                  "max_slippage_bps": SLIP_BPS})

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return None
        self.closes.append(close)
        x = float(close)
        if self.ema is None:
            self.ema = x
        else:
            self.ema += (2.0 / (EMA_SPAN + 1)) * (x - self.ema)
        dev_bps = (x / self.ema - 1.0) * 10000.0

        holding = state.positions.get(SYMBOL)
        now_holding = holding is not None and holding.qty > 0
        if now_holding and holding.cost != self.last_cost:
            # a buy filled (the first tranche, or the add-on): reprice the average
            if self.holding:
                self.added = True
            else:
                self.entry_seq = state.seq
                self.added = False
            self.entry_price = holding.cost * 10**7 / holding.qty  # raw price units
            self.last_cost = holding.cost
        if self.holding and not now_holding:
            self.cooldown = COOLDOWN
            self.last_cost = 0
        self.holding = now_holding

        if self.pending:
            self.pending += 1
            if self.pending > 2:
                self.pending = 0
            else:
                return None
        if state.warming_up:
            return None

        if self.holding:
            if dev_bps >= EXIT_DEV_BPS:
                return self.sell(state, holding)
            if close <= self.entry_price * (1.0 - STOP_BPS / 10000.0):
                return self.sell(state, holding)
            if state.seq - self.entry_seq >= MAX_HOLD:
                return self.sell(state, holding)
            if not self.added and dev_bps <= ADD_DEV_BPS:
                return self.buy(state, ADD_FRAC)
            return None

        if self.cooldown:
            self.cooldown -= 1
            return None
        if state.seq > LAST_ENTRY_SEQ or len(self.closes) <= 15:
            return None
        ret15 = (x / self.closes[-16] - 1.0) * 10000.0
        if dev_bps <= ENTER_DEV_BPS and ret15 > DECEL_BPS:
            return self.buy(state, SIZE_FRAC)
        return None


_BOT = Bot()


def on_batch(state, batch):
    return _BOT.on_batch(state, batch)


makefun_bars.run(on_batch)
