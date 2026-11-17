# Clik BTC race bot v3

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Built for the make.fun bounty [Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261117-0603).

A long-only cbBTC/USDC trading bot for the make.fun `agent-fun/bars-replay/v1`
bar replay: it reads one 1-minute bar per line and answers with at most one
order per bar.

Strategy: staged mean reversion with a two-step take-profit, a deeper final
target for two-tranche positions, and one re-entry after a banked exit. This
pool's bars revert — sharp drops under the slow mean tend to bounce, while
strength fades — and a round trip is expensive (fees, slippage and pool
impact), so the bot trades rarely and at real size. It buys 55% of equity
when the close sits at least 40 bps under its 300-bar EMA and the last 15
bars are no longer in freefall, adds 40% more if the dip deepens to −70 bps,
and exits in steps: half at +10 bps, the rest at +35 bps — or +45 bps when
both tranches are in, because a deeper dip has further to recover. If, after
banking the first half, the price sinks back to −40 bps while the second
half is still held, it buys back in once with 30% of equity and sells the
same recovery twice. A 90 bps hard stop and a 420-bar time stop cap every
position.

`main.py` is the bot (Python 3.13, standard library only, fully deterministic:
no clock, no network, no randomness). `vendor/makefun_bars.py` is the kit's
protocol shim, copied byte-for-byte.

Run it the way the harness does:

    python3 -P -s main.py   # speaks agent-fun/bars-replay/v1 on stdio
