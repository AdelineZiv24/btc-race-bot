# Clik BTC race bot v2

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/AdelineZiv24/btc-race-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Built for the make.fun bounty [Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261117-0603).

A long-only cbBTC/USDC bot for the `agent-fun/bars-replay/v1` bar replay: it
reads one 1-minute bar per line on stdin and answers each batch with at most
one order.

Strategy: staged mean reversion with a two-step take-profit. The bot tracks
the deviation of the close from a 300-bar EMA. When price sits at least
40 bps under that mean and the last 15 bars are no longer in freefall, it
buys a first tranche of 55% of equity; if the dip deepens to −70 bps, one
add-on tranche of 40% joins. On the recovery it banks half the position at
+10 bps and sells the rest at +35 bps, so a bounce that stalls still pays.
A hard stop 90 bps under the average entry price and a 420-bar time stop
bound every trade, and the bot rests five bars after each exit. Trading is
sized and staged because a round trip is expensive here — 4 bps fee,
2 bps slippage and constant-product impact against each bar's pool depth —
so shallow or still-falling dips are never worth chasing.

`main.py` is the bot (Python 3.13, standard library only, fully
deterministic: no clock, no network, no randomness). `vendor/makefun_bars.py`
is the kit's protocol shim, copied byte-for-byte.

Run it the way the harness does:

    python3 -P -s main.py < bars.ndjson
