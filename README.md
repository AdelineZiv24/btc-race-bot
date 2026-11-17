# Clik BTC race bot v4

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Built for the make.fun bounty [Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261117-0603).

A long-only cbBTC/USDC trading bot for the make.fun `agent-fun/bars-replay/v1`
bar replay: it reads one 1-minute bar per line and answers with at most one
order per bar.

Strategy: staged mean reversion with a persistence-checked entry. This pool's
bars revert — sharp drops under the slow mean tend to bounce — and a round
trip is expensive (fees, slippage and pool impact), so the bot trades rarely
and at real size. It buys when the close sits at least 40 bps under its
300-bar EMA, the last 15 bars are no longer in freefall, and the dip is a
regime rather than a flicker (deviation at or under −30 bps on at least 8 of
the last 12 bars). The first tranche is 60% of equity; one add-on tranche of
40% follows if the dip deepens to −70 bps. On recovery it banks a light 35%
slice at +10 bps and lets the rest ride to +35 bps — or +50 bps for a
two-tranche position, whose deeper dip has further to travel. After banking,
a sink back to −40 bps buys back in once at 40% of equity, selling the same
recovery twice. A 90 bps hard stop under the average entry and a 420-bar time
stop bound every position.

`main.py` is the bot (Python 3.13, standard library only, fully deterministic:
no clock, no network, no randomness). `vendor/makefun_bars.py` is the kit's
protocol shim, copied byte-for-byte.
