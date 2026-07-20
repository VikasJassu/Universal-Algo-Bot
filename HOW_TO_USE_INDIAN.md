# How to Use — Indian Index Intraday Multi-Strategy Indicator

Complete guide to the Pine Script indicator combining **ORB + VWAP + EMA + Liquidity Sweep** for Indian index intraday trading.

**This version is index-only** (Nifty 50 / Bank Nifty / Sensex) — individual large-cap
stocks and MCX Crude mode have been removed to focus tuning specifically on index
behavior. It also adds several things the original version was missing, which is why
signals could feel unreliable on Nifty/Sensex before:

- **HTF trend-bias filter** — every signal must now agree with the day's actual
  direction (a higher-timeframe EMA gate). Previously VWAP mean-reversion could fire
  SHORT while ORB/EMA momentum fired LONG on the same trending day — nothing stopped
  the four strategies from fighting each other.
- **Morning Bias classifier (Bullish / Bearish / Sideways / Volatile)** — locked once
  per day from the first hour's behavior (range vs the recent average, and whether that
  range was net-directional or a round-trip whipsaw). Bullish/Bearish mornings keep only
  the breakout family (ORB/EMA) active in that direction; Sideways mornings keep only
  VWAP mean-reversion active; **Volatile mornings (wide but non-directional first hour)
  mute both families** — only Liquidity Sweep stays active, since fading a stop-hunt is
  the strategy best suited to genuinely choppy conditions.
- **Auto-detected index** — reads the chart symbol and applies Bank Nifty's wider
  ATR/tolerance buffers automatically (it moves harder per point than Nifty/Sensex).
- **Strictly intraday, structurally enforced** — every trade is stamped with the exact
  IST calendar day it opened on. If a trade is still open when a new IST day begins, it
  is force-closed immediately, before any TP/SL check can run against the new day's
  price — a signal from today can never show as "TP hit" using tomorrow's move. This
  also fixed a subtler bug: day-boundary detection previously depended on the chart's
  timezone display setting rather than an explicit IST anchor, which could let a trade
  slip past end-of-day cleanup if your chart wasn't set to Exchange/IST time.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [The 4 Strategies Explained](#the-4-strategies-explained)
4. [Chart Elements Legend](#chart-elements-legend)
5. [All Input Settings](#all-input-settings)
6. [Recommended Setup by Instrument](#recommended-setup-by-instrument)
7. [Daily Trading Routine](#daily-trading-routine)
8. [How to Take Trades](#how-to-take-trades)
9. [Trade Management](#trade-management)
10. [Learning Roadmap (Phase 1 → 3)](#learning-roadmap-phase-1--3)
11. [Alerts + Telegram Setup](#alerts--telegram-setup)
12. [Broker Setup](#broker-setup)
13. [Position Sizing (Indian Context)](#position-sizing-indian-context)
14. [Rules and Do/Don't](#rules-and-dodont)
15. [Days to SKIP](#days-to-skip)
16. [Troubleshooting](#troubleshooting)

---

## Overview

This indicator runs **4 independent intraday strategies** in one Pine Script, each toggleable:

| # | Strategy | Best for | Win Rate |
|---|---|---|---|
| 1 | **ORB** (Opening Range Breakout) | Trending days, first hour | 55–65% |
| 2 | **VWAP + PDH/PDL Reversal** | Range/reversal days | 50–60% |
| 3 | **EMA Momentum** | Strong trend days | 45–55% |
| 4 | **Liquidity Sweep** | Any day, needs pattern skill | 45–55% |

All 4 share a unified trade plan: entry → SL → TP1 (50%) → TP2 (30%) → TP3 (20% runner) with automatic SL trailing.

**Timezone:** IST (Asia/Kolkata) hardcoded — no manual timezone setup needed.

---

## Installation

1. Open TradingView → your Indian instrument chart (e.g., BANKNIFTY, NIFTY, RELIANCE)
2. Bottom panel → **Pine Editor**
3. Copy the entire contents of `indian-multi-strategy` file
4. Click **Save** → name it (e.g., "Indian Multi-Strategy")
5. Click **Add to chart**
6. Set chart timeframe to **5 minutes**

---

## The 4 Strategies Explained

### Strategy 1: ORB (Opening Range Breakout)

**Logic:**
- Marks the high and low of the first 15 minutes (9:15–9:30 IST)
- Locks the range after 9:30
- Long signal: close breaks above ORB High
- Short signal: close breaks below ORB Low
- SL = opposite end of range
- TP2 = range size × 1.5 (e.g., 100-point range → 150-point target)

**Best conditions:**
- Range < 1% of price (skips if wider — poor R:R)
- Only takes FIRST breakout each direction (one long attempt, one short attempt per day)

**Skip on:** Bank Nifty expiry Wednesday, budget day, Fed announcement mornings

---

### Strategy 2: VWAP + Previous Day High/Low Reversal

**Logic:**
- Draws Previous Day High (PDH) and Previous Day Low (PDL) at each new day
- **Long signal:** Price wicks into PDL zone (within 0.15%) + closes above VWAP
- **Short signal:** Price wicks into PDH zone + closes below VWAP

**Why it works:**
- Retail stops sit above PDH and below PDL — institutions hunt these
- VWAP is the institutional benchmark — reclaims/losses signal directional intent

**Best time window:**
- 10:30 AM – 12:00 PM (post-opening exhaustion)
- 1:30 PM – 3:00 PM (afternoon reversal)

---

### Strategy 3: EMA Momentum (9/21 Pullback)

**Logic:**
- Requires 9 EMA > 21 EMA + 21 EMA rising (bullish trend)
- Waits for pullback where low touches 9 EMA
- Enters on bullish candle close above 9 EMA
- Mirror for shorts

**Best conditions:**
- Trending days (check SGX Nifty gap pre-market)
- Skip choppy/consolidation days (multiple failed pullbacks)

**Simplest of the four** — great for beginners after mastering ORB.

---

### Strategy 4: Liquidity Sweep

**Logic:**
- Detects when price wicks past a recent pivot high/low but closes back inside
- Requires wick size ≥ 0.5 × ATR (filters weak pokes)
- **Sweep of high** (bearish) → short signal
- **Sweep of low** (bullish) → long signal

**Best used:**
- As confluence with other signals (e.g., ORB + Sweep = high conviction)
- After 2+ months of screen time — pattern recognition matters

For the **full-featured sweep detection** (with equal high/low pools, HTF bias, multi-TF S/R), use the gold-crypto indicator instead.

---

## Chart Elements Legend

| Element | Color | Meaning |
|---|---|---|
| **Red dashed line** | Red | Previous Day High (PDH) |
| **Green dashed line** | Green | Previous Day Low (PDL) |
| **Yellow dotted lines** | Yellow | ORB High / ORB Low (locked after 9:30) |
| **Yellow solid line** | Yellow | VWAP (Volume Weighted Average Price) |
| **Aqua line** | Aqua | 9 EMA |
| **Orange line** | Orange | 21 EMA |
| **Green background tint** | Green | Tradable window (market open, not lunch/gap/close) |
| **Red background tint** | Red | Lunch break (no trades) |
| **No tint** | — | Market closed or opening/closing chop |
| **Green entry box** ("STRATEGY LONG @ …") | Green | Confirmed long signal with full plan |
| **Red entry box** ("STRATEGY SHORT @ …") | Red | Confirmed short signal with full plan |
| **Red dashed line** near entry | Red | Active SL (auto-moves to BE at TP1) |
| **Green dotted lines** near entry | Green | TP1 / TP2 / TP3 targets |

### Status Table (top-right)

| Row | Shows |
|---|---|
| **Index** | Nifty 50 / Bank Nifty / Sensex, plus `(auto)` if detected from the chart symbol, `(manual)` if you turned auto-detect off, or `(fallback)` if unrecognized |
| **Day Bias** | BULL (green) / BEAR (red) / FLAT — the HTF trend-bias gate; only signals matching this direction fire |
| **Morning Bias** | "Building…" / **Bullish** (green) / **Bearish** (red) / **Sideways** (aqua) / **Volatile** (orange) — locked after the first hour; decides which strategy family stays active for the rest of the day |
| **Session** | TRADE (green) / LUNCH (red) / OPEN CHOP / CLOSE CHOP / CLOSED |
| **ORB** | "Building…" or "Range: X" once locked |
| **VWAP** | ABOVE (green) or BELOW (red) |
| **EMA** | BULL / BEAR / FLAT |
| **ATR** | Current ATR value |
| **Trade** | Which strategy fired + direction (or FLAT) |
| **Progress** | Open / TP1 hit / TP2 hit |

---

## All Input Settings

### Index Mode
- **Auto-Detect Index from Chart Symbol** — ON by default; reads NIFTY/BANKNIFTY/SENSEX from the ticker and auto-tunes buffers
- **Index (manual / fallback)** — Nifty 50 / Bank Nifty / Sensex; used directly if auto-detect is off, or as the fallback if the symbol isn't recognized

### Trend Filter
- **Require HTF Trend Bias** — ON by default (recommended); gates every signal to the day's actual direction
- **HTF for Bias** — 15 / 30 / 60 minute EMA used as the bias timeframe (default 15)
- **HTF EMA Length** — default 50

### Morning Bias
- **Adapt to Morning Bias (Bullish/Bearish/Sideways/Volatile)** — ON by default. Bullish/Bearish -> only breakout (ORB/EMA) stays active in that direction. Sideways -> only VWAP mean-reversion stays active. Volatile -> both muted, only Liquidity Sweep remains
- **Avg Daily Range Lookback (days)** — default 10
- **Wide First Hour: Range > Avg Daily Range ×** — default 1.3 (first hour must be 30% wider than the recent average to count as "wide")
- **Directional vs Choppy: Net Move ÷ Range ≥** — default 0.35. Within a wide first hour, this fraction of the total range must be net directional travel (not round-tripping) to call it Bullish/Bearish rather than Volatile — lower this to classify more wide-range mornings as directional

### Strategies (toggle each on/off)
- **Enable ORB Strategy**
- **Enable VWAP + PDH/PDL**
- **Enable EMA Momentum**
- **Enable Liquidity Sweep**

### Session
- **Indian Market Session** — default `0915-1530` (IST)
- **Lunch — no trades** — default `1200-1330`
- **Skip First 15 Min** — avoid post-gap chop (recommended ON)
- **Skip Last 15 Min** — avoid auction volatility (recommended ON)

### ORB
- **ORB Range Duration (mins)** — default 15
- **Skip If Range > % of Price** — default 1.0% (wider = worse R:R)
- **TP2 = Range × N** — default 1.5

### VWAP + PDH/PDL
- **PDH/PDL Rejection Tolerance %** — default 0.15% (how close price must get)

### EMA Momentum
- **Fast EMA** — default 9
- **Slow EMA** — default 21

### Liquidity Sweep
- **Pivot Bars (L=R)** — default 5
- **Min Sweep Wick × ATR** — default 0.5

### Common
- **ATR Length** — default 14

### Trade Management
- **SL Buffer × ATR** — default 0.5
- **TP1 / TP2 / TP3 (R multiples)** — default 1 / 2 / 3
- **TP1 / TP2 / TP3 Exit %** — default 50 / 30 / 20

---

## Recommended Setup by Instrument

This version only targets Nifty 50, Bank Nifty, and Sensex — individual stocks and
MCX Crude aren't covered here. Set **Auto-Detect Index** ON and just load the chart;
the indicator tunes itself.

> ⚠️ **Expiry days changed in Sept 2025** (SEBI's single-weekly-expiry-per-exchange
> reform): NSE moved its entire F&O segment to **Tuesday**, and Bank Nifty **lost its
> weekly expiry entirely** — it's monthly-only now (last Tuesday). BSE's Sensex is the
> weekly-expiry index there, on **Thursday**. If you're trading options around expiry
> chop, use the table below, not the old Wednesday/Thursday assumption.

| Index | Weekly expiry | Monthly expiry | Skip trading |
|---|---|---|---|
| **Nifty 50** | Tuesday | Last Tuesday | Tuesday (expiry chop) |
| **Bank Nifty** | — (none since Nov 2024) | Last Tuesday | Last Tuesday of the month |
| **Sensex** | Thursday | Last Thursday | Thursday (expiry chop) |

### 🥇 Nifty 50 (NIFTY) — primary recommendation
- **Chart:** NIFTY, 5m
- **All 4 strategies:** ON, Auto-Detect Index: ON
- Deepest liquidity/tightest spreads of the three — best fit for this indicator's
  tight ATR-based stops (less slippage eating into the edge on tight stops)
- **Skip:** Tuesday expiry chop, Budget Day, RBI policy afternoons

### 🥈 Bank Nifty (BANKNIFTY)
- **Chart:** BANKNIFTY, 5m
- **All 4 strategies:** ON, Auto-Detect Index: ON (auto-widens ATR/tolerance buffers)
- Bigger, sharper point moves — good once comfortable with Nifty; size down since
  margin per lot is highest of the three
- **Skip:** last-Tuesday-of-month expiry

### 🥉 Sensex (SENSEX)
- **Chart:** SENSEX, 5m
- Tracks Nifty very closely (high correlation) — not real diversification, mainly
  useful for its own Thursday weekly-expiry cycle or if your broker gives better BSE fills
- **Skip:** Thursday expiry chop

### ❌ AVOID
- Individual stocks and MCX Crude (not covered by this version — use a dedicated
  setup for those if needed)
- Trading through expiry-day chop on whichever index you're on
- Position sizes that ignore the 1% risk rule below

---

## Daily Trading Routine

### Pre-market (8:45–9:15 AM IST)
1. Check **SGX Nifty** overnight movement (indicates opening bias)
2. Check **Dow Jones close** last night (US = trend leader)
3. Check economic calendar for today (RBI meet, US data at 6 PM)
4. Form your own rough read on the day, but let the **Morning Bias** row confirm it
   after 10:15 AM rather than trading on the pre-market guess alone
5. Open Bank Nifty / Nifty 5m chart with indicator loaded

### Session 1: Opening (9:15–9:30 AM)
- **Do NOT trade** (skipped by indicator)
- Watch price action — is it directional or choppy?
- Note the ORB range as it builds

### Session 2: ORB window (9:30–10:30 AM)
- **Primary window for ORB signals**
- Watch for green/red entry box on breakout
- Enter with SL/TP as shown

### Session 3: Trend continuation (10:30–12:00 PM)
- **VWAP + EMA signals** most active
- Only take trades in the direction of the day's initial move

### Session 4: Lunch (12:00–1:30 PM)
- **NO TRADES** — red background tint on chart
- Grab lunch, review the morning

### Session 5: Afternoon reversal (1:30–3:00 PM)
- **VWAP + PDH/PDL setups** most active
- Best window for counter-trend trades

### Session 6: Closing (3:00–3:15 PM)
- Aggressive last-hour moves possible
- Skip if you already have 2 trades done

### Post-market (3:30–4:00 PM)
- Journal today's trades
- Check FII/DII data (6 PM release) for tomorrow's bias

---

## How to Take Trades

### Step 1: Wait for green tradable window
Chart shows **green background tint** = OK to trade.
Red tint = lunch, no trades.
No tint = market closed or in gap/close chop.

### Step 2: Watch for entry box
When any of the 4 strategies fires:
- **Green box "ORB LONG @ 52340"** = confirmed long
- **Red box "VWAP SHORT @ 47820"** = confirmed short
- Box shows strategy name + entry + SL + TP1 + TP2 + TP3 + exit %s

### Step 3: Wait for candle CLOSE
Do NOT enter mid-candle. Wait for the 5m timer to hit 0:00.

### Step 4: Execute in your broker
1. Copy entry, SL, TP1, TP2, TP3 from the box
2. Open Kite / Fyers / Dhan
3. Place market or limit order at entry
4. Set stop-loss at SL price
5. Set 3 GTT/target orders at TP1 (50%), TP2 (30%), TP3 (20%)

### Step 5: Follow alerts
As price moves, indicator alerts:
- **TP1 hit** → close 50%, move SL to entry (breakeven)
- **TP2 hit** → close 30%
- **TP3 hit** → close final 20%
- **SL hit** → accept the loss, move on

---

## Trade Management

### SL Calculation
- **ORB signal:** opposite ORB level ± ATR × 0.5 buffer
- **Other signals:** wick low/high ± ATR × 0.5 buffer

### TP1 (50% exit)
- Fixed at 1R from entry
- SL auto-moves to breakeven

### TP2 (30% exit)
- **ORB signal:** entry ± (ORB range × 1.5)
- **Others:** 2R fallback
- **PDH/PDL bonus:** if PDH/PDL is more favorable, uses that

### TP3 (20% runner)
- **PDH (long) or PDL (short)** if positioned favorably
- Otherwise 3R from entry
- Full exit here — trade closed

### Force-Close (strictly intraday — no exceptions)
- Every trade is stamped with the exact IST calendar day it opened on
- If a trade is still open when a new IST day begins (you didn't get out, or the
  session simply ended without hitting SL/TP), it is force-closed **before** any
  further TP/SL check can run — you'll see a gray "Force-Close" label and an alert
  tagged `[EOD]` or `[stale (previous day)]`
- This means a signal from today can never later show as "TP hit" using tomorrow's
  price move — match your own broker position to this: **close everything yourself
  by the time the market shuts, don't rely on the indicator's visual state carrying
  meaning overnight**

---

## Learning Roadmap (Phase 1 → 3)

### 📅 Phase 1: Months 1–2 (ORB only)
**Goal:** Build discipline + Indian market rhythm

Settings:
- Turn OFF: VWAP, EMA, Sweep
- Turn ON: ORB only
- Instrument: **Bank Nifty futures** (5m)
- Time: 9:30–10:30 AM window only
- Trades: **1 per day maximum**
- Capital: minimum ₹1.5 lakh (for 1 lot with proper sizing)

Journal every trade: setup, execution, outcome, mistakes.

**Only progress to Phase 2 after 30+ trades with positive expectancy.**

### 📅 Phase 2: Months 3–4 (Add VWAP)
**Goal:** Trade both opening and afternoon windows

Settings:
- Turn ON: ORB + VWAP
- Keep OFF: EMA, Sweep
- Time windows: 9:30–10:30 + 1:30–3:00
- Trades: **2 per day maximum**

### 📅 Phase 3: Month 5+ (Full setup)
**Goal:** All 4 strategies, higher R:R

Settings:
- Turn ON: All 4 strategies
- Trade any window inside the green background
- Trades: 2–3 per day maximum
- Add the second index (e.g. started on Bank Nifty → add Nifty 50, or vice versa)

---

## Alerts + Telegram Setup

### TradingView Alert
1. Right-click chart → **Add alert** (Alt+A)
2. **Condition:** your indicator → **"Any alert() function call"**
3. **Trigger:** Once Per Bar Close
4. **Expiration:** Open-ended
5. Save

You'll get alerts like (using the chart's actual symbol, not a generic "INDIAN" label):
```
NIFTY ORB LONG @ 24580 | SL 24540 | TP1 24660 | TP2 24720 | TP3 24800
```

### Send to Telegram
Reuse the same bot from your gold indicator:
- Webhook URL: `https://universal-algo-bot.onrender.com/webhook`
- Message field: `{"secret":"myGoldBot2026","text":"{{message}}"}`

Same Telegram bot handles both indicators — no need for a second setup.

---

## Broker Setup

### 🥇 Zerodha (recommended)
- Kite platform
- ₹20 flat per order intraday
- Bank Nifty futures margin: ~₹1.4 lakh
- Fastest and cheapest for retail

### Alternatives
- **Fyers** — native TradingView integration inside their platform
- **Dhan** — great for options intraday
- **Upstox** — clean UI

### Auto-execution (advanced)
Zerodha doesn't allow direct auto-execution from webhooks. Options:
1. **Manual** (recommended) — see Telegram alert, place order in Kite
2. **AlgoBridge / AutoTrader** — 3rd-party bridges (₹500–2000/month, adds latency)

---

## Position Sizing (Indian Context)

### Formula
```
Position size = (Account × Risk%) ÷ (Entry - SL distance × Point value)
```

### Bank Nifty Example
- Account: ₹2,00,000
- Risk per trade: 1% = ₹2,000
- Bank Nifty at 52,000, SL at 51,880 (120-point stop)
- Point value: ₹15 per point (1 lot = 15 shares)
- Position: ₹2,000 ÷ (120 × ₹15) = **1.1 lots** → **1 lot**

### Nifty 50 Example
- Same account (₹2 lakh), 1% risk (₹2,000)
- Nifty at 24,500, SL at 24,460 (40-point stop)
- Point value: ₹75 per point (1 lot = 75 shares)
- Position: ₹2,000 ÷ (40 × ₹75) = **0.66 lot** → **skip** (can't do 0.66 lots on futures)

Nifty needs tighter stops or larger account.

### Options sizing
- Buy premium: keep total premium spent ≤ 1% risk
- If SL = 30% of premium loss, position = (₹2,000 ÷ 30%) = ₹6,667 max premium
- At ₹80 premium: 1 lot (75 shares) = ₹6,000 — fits ✅

---

## Rules and Do/Don't

### DO
- ✅ Wait for candle close before entering
- ✅ Enter with EXACT SL/TP levels from the entry box
- ✅ Take TP1 partial (50%) — non-negotiable
- ✅ Journal every trade with screenshots
- ✅ Stop after 2 losses in a day
- ✅ Max 1% risk per trade
- ✅ Trade only during green background (tradable window)
- ✅ Backtest 30+ setups in TradingView bar-replay before live

### DON'T
- ❌ Don't enter mid-candle "because it's obvious"
- ❌ Don't skip TP1 partial hoping for TP3
- ❌ Don't move SL wider to give it "room"
- ❌ Don't take 3+ trades in a day
- ❌ Don't revenge trade after a loss
- ❌ Don't trade small-cap stocks or new listings
- ❌ Don't use full margin — keep 30%+ free
- ❌ Don't disable filters "to get more signals"

---

## Days to SKIP

Do not trade on:

| Event | Frequency | Why |
|---|---|---|
| **Bank Nifty Expiry (last Tue of month)** | Monthly | Chaos in Bank Nifty (weekly expiry was discontinued Nov 2024) |
| **Nifty Expiry (Tue)** | Weekly | Chaos in Nifty |
| **Sensex Expiry (Thu)** | Weekly | Chaos in Sensex |
| **Budget Day (Feb 1)** | Yearly | Wild moves all day |
| **RBI Policy** | Bi-monthly | 2:30 PM violent moves |
| **Result Days** | Quarterly (per stock) | Individual stock chaos |
| **US Fed Announcement (2 AM IST)** | ~8/year | Overnight gap next day |
| **US CPI/NFP Release** | Monthly | Overnight gap |
| **Election Result Day** | 5 years | 5-10% moves |
| **Major geopolitical event** | Rare | Unpredictable gaps |

Check https://www.investing.com/economic-calendar/ each morning.

---

## Troubleshooting

### "No signals firing"
- Check background — is it green (tradable)? If red/none, wait
- ORB range too wide → indicator skips this signal type today
- Strategies all disabled → enable at least ORB in settings

### "ORB range not showing"
- Chart timeframe must be ≤ 15m (5m recommended)
- Wait until 9:30 AM IST for it to lock
- Reload indicator if it's been sitting overnight

### "PDH/PDL missing"
- Only appears after first full trading day of data loaded
- Reload chart if you just opened it

### "Trade box appears but no alert"
- Alert not created → right-click chart → Add alert
- Alert condition wrong → must be "Any alert() function call"
- Trigger set to "Only Once" → change to "Once Per Bar Close"

### "Position size too big/small"
- Recalculate: risk% × account ÷ SL distance
- Bank Nifty needs ~₹2 lakh minimum for proper 1% sizing
- If lot size too big → use Bank Nifty options ATM (10-25 delta)

### "Getting stopped out repeatedly"
- Check if you're trading during expiry or news days (skip these)
- Widen SL buffer to 0.7× ATR
- Increase ORB max range to 1.5% to skip narrow-range whipsaw days

---

## Quick Start Checklist

Before your first live trade:

- [ ] Indicator loaded on Bank Nifty 5m chart
- [ ] Only ORB enabled (Phase 1)
- [ ] Zerodha account funded with ₹1.5+ lakh
- [ ] TradingView alert created ("Any alert() function call")
- [ ] Telegram bot working (test with existing setup)
- [ ] Journal spreadsheet ready
- [ ] Read this document fully
- [ ] Backtested 20+ ORB setups in bar-replay
- [ ] Confirmed today is NOT expiry/budget/news day
- [ ] Position size calculated for ₹2,000 max risk

---

## Files in This Project

| Path | Purpose |
|---|---|
| `trading-view-algo` | Gold / Crypto / Crude indicator (multi-asset ICT sweeps) |
| `indian-multi-strategy` | This indicator — Nifty/Bank Nifty/Sensex ORB/VWAP/EMA/Sweep, trend-bias + day-type filtered |
| `HOW_TO_USE.md` | Guide for gold/crypto/crude indicator |
| `HOW_TO_USE_INDIAN.md` | This guide |
| `telegram-bot/*` | Telegram alert forwarder (works with both indicators) |

---

## Final Note

**No indicator makes you money — process does.**

The 4 strategies in this file are proven mechanical setups. Your job is:
1. Position size correctly (1% risk)
2. Wait for the setup (not force it)
3. Take TP1 partial always
4. Stop after 2 losses
5. Journal + review weekly

Trade small until profitable for 3 months, then scale. That's the path.

**Trade safe. Position size first. Setup second.**
