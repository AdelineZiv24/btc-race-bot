# Clik BTC race bot

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Built for the make.fun bounty [Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261117-0603).

A long-only cbBTC/USDC trading bot for the make.fun `agent-fun/bars-replay/v1`
bar replay: it reads one 1-minute bar per line and answers with at most one
order per bar.

Strategy: slow-mean reversion with cascade protection. This pool's bars
revert — sharp drops under the slow mean tend to bounce, while strength
fades — and a round trip is expensive (fees, slippage and pool impact), so
the bot trades rarely and at moderate size. It buys when the close sits at
least 40 bps under its 300-bar EMA and the last 15 bars are no longer in
freefall, adds one extra tranche if the dip deepens to −70 bps, and exits
when the deviation recovers above +10 bps, on a 90 bps hard stop, or after
420 bars.

`main.py` is the bot (Python 3.13, standard library only, fully deterministic:
no clock, no network, no randomness). `vendor/makefun_bars.py` is the kit's
protocol shim, copied byte-for-byte.
