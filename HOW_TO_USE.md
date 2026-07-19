# How to Use — Gold + Crypto + Crude Intraday Liquidity Sweep Indicator

Complete guide to installing, configuring, and trading with this TradingView Pine Script v6 indicator.

---

## Table of Contents

1. [What This Indicator Does](#what-this-indicator-does)
2. [Installation](#installation)
3. [Understanding the Strategy](#understanding-the-strategy)
4. [Chart Elements Explained](#chart-elements-explained)
5. [Market Modes](#market-modes)
6. [All Input Settings](#all-input-settings)
7. [How to Take Trades](#how-to-take-trades)
8. [Trade Management (SL / TP1 / TP2 / TP3)](#trade-management-sl--tp1--tp2--tp3)
9. [Alerts & Telegram Bot](#alerts--telegram-bot)
10. [Best Practices & Rules](#best-practices--rules)
11. [Timezone & Session Reference (IST)](#timezone--session-reference-ist)
12. [Broker Recommendations for Indian Traders](#broker-recommendations-for-indian-traders)
13. [Troubleshooting](#troubleshooting)
14. [Risk Warnings](#risk-warnings)

---

## What This Indicator Does

This indicator implements an **ICT / SMC-style liquidity sweep reversal strategy**. It identifies places where retail stop-losses cluster ("liquidity"), waits for institutions to sweep those stops, and signals a reversal entry.

### Core capabilities

1. **Day High / Day Low tracking** — live session H/L that resets daily
2. **Multi-timeframe S/R** — pivot-based support/resistance from 4H, 1H, 5m, 1m
3. **Liquidity pool detection** — equal highs (BSL) and equal lows (SSL) where stops sit
4. **Filtered sweep signals** — only fires when:
   - A sweep pattern forms (wick past level + close back inside)
   - Trading during a killzone (major session)
   - HTF bias agrees (4H EMA)
   - Sweep wick is meaningful (≥ ATR × multiplier)
5. **Full trade management** — SL, three targets, partial exits, trailing stop
6. **Multi-asset presets** — Gold, Crypto, and Crude Oil configurations
7. **Auto chart cleanup** — removes swept, old, or duplicate levels

---

## Installation

1. Open TradingView → your chosen chart (XAUUSD / BTCUSDT / USOIL / MCX Gold etc.)
2. Bottom panel → **Pine Editor**
3. Copy the entire contents of `trading-view-algo` into the editor
4. Click **Save** → give it a name
5. Click **Add to chart**
6. Open the indicator settings (gear icon) — **Auto-Detect Market Mode** is ON by default, so it will pick Gold/Crypto/Crude automatically from the chart symbol. Leave it on and you never need to touch the Market Mode dropdown again when switching charts (see [Market Modes](#market-modes)).

**Recommended chart timeframe:** 5m (best balance of signals and reliability).
Alternative: 1m for scalping, 15m for slower/higher-quality setups.

---

## Understanding the Strategy

### The core idea

Retail traders place stop-losses in predictable spots:
- Just above swing highs (BSL — buy-side liquidity)
- Just below swing lows (SSL — sell-side liquidity)
- At the Day High / Day Low

Institutions know this. They push price to hunt those stops, then reverse in the opposite direction. This is called a **liquidity sweep**.

A sweep = **wick through the level + close back inside the range**.

### Why the filters matter

Not every sweep is real. False sweeps trap you in the wrong direction. The indicator filters out ~60% of bad sweeps by requiring:

1. **Killzone** — only trade during high-institutional-flow sessions
2. **HTF bias** — only take longs when higher timeframe is bullish, shorts when bearish
3. **Wick size** — the sweep must actually run stops meaningfully (≥ 0.5–0.8× ATR)

---

## Chart Elements Explained

| Element | Meaning | Action |
|---|---|---|
| **Red dashed line** ("Day High") | Session high — extended right | Watch as target/sweep zone |
| **Green dashed line** ("Day Low") | Session low | Watch as target/sweep zone |
| **Red/Green solid** (thick) | 4H S/R — major levels | Strongest reversal zones |
| **Orange/Blue** (medium) | 1H S/R | Intraday structure |
| **Purple/Teal** (thin) | 5m S/R | Short-term levels |
| **Gray dotted** | 1m S/R (chart must be 1m) | Micro-structure |
| **Pink horizontal line** with **"BSL"** label | Equal highs — buy-side liquidity | Target for shorts, don't buy near it |
| **Cyan horizontal line** with **"SSL"** label | Equal lows — sell-side liquidity | Target for longs, don't short near it |
| **Yellow line** | HTF bias EMA (4H default) | Above = bullish bias, below = bearish |
| **Blue background tint** | Killzone (active session) | Only take signals here |
| **X-cross above bar** | Day High swept — **short signal** | Take short with box's SL/TP |
| **X-cross below bar** | Day Low swept — **long signal** | Take long with box's SL/TP |
| **Triangle down (orange/pink)** | 1H R or BSL swept — short signal | Take short |
| **Triangle up (blue/cyan)** | 1H S or SSL swept — long signal | Take long |
| **Green box "LONG @..."** | Full trade plan for long entry | Enter at price shown |
| **Red box "SHORT @..."** | Full trade plan for short entry | Enter at price shown |
| **Red dashed** (near entry) | Active SL line | Stop-loss (auto-updates when trailing) |
| **Green dotted** (near entry) | Active TP1 / TP2 / TP3 | Take-profit targets |

### Status table (top-right)

| Row | Shows |
|---|---|
| **Symbol** | The chart's actual ticker (e.g. XAUUSD, BTCUSD, CL1!) — this is what appears in every alert/Telegram message, so gold, crypto, and crude no longer look identical |
| **Mode** | Gold / Crypto / Crude (color-coded), plus `(auto)` if auto-detected from the symbol, `(manual)` if you turned auto-detect off, or `(fallback)` if the symbol wasn't recognized and it fell back to your manual dropdown pick |
| **Session** | ACTIVE (green) or OFF (gray) |
| **HTF Bias** | BULL (green) / BEAR (red) |
| **ATR** | Current ATR value |
| **Day Range** | Distance from day high to day low |
| **Trade** | LONG / SHORT / FLAT |
| **Progress** | Open / TP1 hit / TP2 hit / TP3 |

---

## Market Modes

Three preset configurations: Gold, Crypto, Crude Oil.

### Auto-Detect (default: ON)
With **Auto-Detect Market Mode from Chart Symbol** enabled, the indicator reads the chart's ticker and applies the right preset automatically — switch from an XAUUSD chart to a BTCUSD chart and it silently re-tunes itself, no settings menu needed. It recognizes:
- **Gold:** tickers containing XAU, GOLD, GC1, MGC
- **Crypto:** tickers containing BTC, ETH, SOL, XRP, DOGE, USDT, USDC, or any symbol TradingView classifies as `crypto` type
- **Crude:** tickers containing CL1, MCL, USOIL, UKOIL, WTI, BRENT, QM1

If the symbol doesn't match any pattern (e.g. an unfamiliar stock/index ticker), it falls back to the manual **Market Mode** dropdown below. Turn Auto-Detect off if you want to force a specific mode regardless of symbol (e.g. testing Crypto settings on a Gold chart).

This also fixes alert text: every `alert()` now includes the actual chart symbol (e.g. `BTCUSD LONG entry @ ...`) instead of always saying "GOLD", so your Telegram messages correctly identify which instrument fired.

### 🟡 Gold Mode (default)
- **Instruments:** XAUUSD, MCX Gold, MCX Gold Mini/Petal
- **Sessions:** London (07:00–10:00 GMT), NY AM (12:30–15:00 GMT), Overlap (12:00–16:00 GMT)
- **ATR wick threshold:** 0.5×
- **HTF bias:** 4H EMA 50
- **Best chart timeframe:** 5m

### 🟠 Crypto Mode
- **Instruments:** BTC/USDT, ETH/USDT (recommended); avoid meme coins
- **Sessions:** Off by default (24/7 market); optional US window 13:00–21:00 UTC
- **ATR wick threshold:** 0.8× (crypto wicks larger)
- **HTF bias:** 1H EMA 50 (crypto trends faster)
- **Liquidity tolerance:** 50 ticks (wider zones)
- **Pivot bars:** 3/3 (more responsive)

### 🔵 Crude Oil Mode
- **Instruments:** WTI/USOIL, CL futures, MCX Crude Mini
- **Sessions:** same killzones as Gold — London (07:00–10:00 GMT), NY AM (12:30–15:00 GMT), Overlap (12:00–16:00 GMT). (The old crude-only "NY Pit 14:30–16:30 GMT" window was removed — it was redundant on top of these killzones.)
- **ATR wick threshold:** 0.6×
- **HTF bias:** 4H EMA 50
- **Liquidity tolerance:** 50 ticks
- **Merge zones:** 80 ticks (prevents stacked BSL/SSL)
- **⚠️ Skip Wed EIA report:** 10:30 AM EST ±15 min

---

## All Input Settings

Grouped by the setting panel section.

### Market Mode
- **Auto-Detect Market Mode from Chart Symbol** — ON by default; auto-picks Gold/Crypto/Crude from the ticker on chart switch
- **Market Mode (manual / fallback)** — Gold / Crypto / Crude preset selector; used directly if Auto-Detect is off, or as the fallback if the symbol isn't recognized

### Crypto Overrides *(only used in Crypto mode)*
- ATR wick multiplier, liquidity tolerance, session filter, US window, HTF timeframe, pivot bars, SL buffer

### Crude Overrides *(only used in Crude mode)*
- ATR wick multiplier, liquidity tolerance, merge zone size, session filter (uses the same Gold killzones), HTF timeframe, pivot bars, SL buffer

### Day Levels
- **Show Day High/Low** — toggle daily H/L lines
- **Day High/Low colors** — customize

### Multi-Timeframe S/R
- **Show 4H / 1H / 5m / 1m S/R** — individual toggles
- **Pivot Left/Right Bars** — pivot detection sensitivity (higher = fewer/stronger pivots)
- **Max Levels per TF** — cap on how many old S/R lines to keep

### Liquidity
- **Show Equal High/Low Pools** — BSL/SSL detection
- **Equal H/L Tolerance (ticks)** — how close two highs/lows must be to form a pool
- **Pivots Remembered** — how far back to look for equal H/L pairs

### Filters: Session
- **Only Signal During Killzones** — master session filter
- **London / NY / Overlap sessions** — customize kill windows
- **Session Timezone** — GMT / America/New_York / Europe/London / Asia/Tokyo

### Filters: HTF Bias
- **Use 4H EMA Bias Filter** — require higher timeframe agreement
- **HTF EMA Length** — default 50
- **HTF Timeframe** — 60m / 240m / Daily

### Filters: Sweep Quality
- **Require Meaningful Sweep Wick** — enforce minimum wick size
- **ATR Length** — default 14
- **Min Wick × ATR** — sweep must be at least this fraction of ATR

### Chart Cleanup
- **Hide Old Sweeps & Liquidity Pools** — auto-delete after N hours
- **Keep Only Last N Hours** — default 4
- **Auto-Remove Swept BSL/SSL Levels** — delete zones once price closes through them
- **Max Active BSL/SSL Levels** — cap at 4 by default
- **Merge Zones Within (ticks)** — prevent duplicate stacked lines

### Trade Management
- **Enable Trade Management** — master toggle for SL/TP system
- **SL Buffer × ATR** — extra buffer beyond sweep wick
- **TP1 / TP2 / TP3 Exit %** — default 50 / 30 / 20
- **Hybrid Trailing** — auto BE at TP1, structure trail after TP2

---

## How to Take Trades

### Step 1: Wait for the killzone
Blue background tint = session is active. If off, be patient — no signals will fire.

### Step 2: Watch for a sweep signal
A colored triangle or X-cross appears on the chart:
- **Above bar (red/orange/pink)** = short opportunity
- **Below bar (lime/blue/cyan)** = long opportunity

### Step 3: Wait for the entry box
Along with the triangle, a **green (LONG) or red (SHORT) box** appears with:
- Entry price
- SL price
- TP1 / TP2 / TP3 prices
- Exit percentages

This is your **complete trade plan**. Nothing else needed.

### Step 4: Wait for candle CLOSE
Do NOT enter mid-candle. Wait for the 5m timer to reach 0:00. Sweeps can invalidate in the last seconds.

### Step 5: Enter the trade in your broker
1. Copy Entry, SL, TP1, TP2, TP3 from the box
2. Open your broker (MCX/Delta/XM/etc.)
3. Place a **market or limit order** at the entry
4. Set **stop-loss** at the SL price
5. Set **three take-profit orders** at TP1, TP2, TP3 with the exit percentages shown

### Step 6: Manage the trade
- **When TP1 hits:** move SL to entry price (breakeven). Indicator sends alert.
- **When TP2 hits:** trail SL to last swing low (long) or swing high (short). Indicator sends alert.
- **When TP3 hits:** close remaining position. Done.
- **If SL hits before TP1:** accept the loss. Move on.

---

## Trade Management (SL / TP1 / TP2 / TP3)

The indicator calculates targets using **structure**, not fixed R multiples (though R fallback exists).

### SL calculation
- **Long:** Low of sweep bar − (ATR × SL buffer)
- **Short:** High of sweep bar + (ATR × SL buffer)

Buffer defaults: Gold 0.5×, Crypto 0.8×, Crude 0.6×.

### TP1 — nearest opposite pivot
- **Long TP1:** nearest chart-TF pivot high above entry (fallback: entry + 1R)
- **Short TP1:** nearest chart-TF pivot low below entry (fallback: entry − 1R)

**Action at TP1:** exit 50% + SL moves to breakeven.

### TP2 — opposite liquidity pool
- **Long TP2:** most recent BSL zone above entry (fallback: 2R)
- **Short TP2:** most recent SSL zone below entry (fallback: 2R)

**Action at TP2:** exit 30% + SL trails to last structure pivot.

### TP3 — Day High/Low
- **Long TP3:** Day High (fallback: 3R)
- **Short TP3:** Day Low (fallback: 3R)

**Action at TP3:** exit remaining 20% (runner). Trade closed.

### Hybrid trailing after TP2
Once TP2 hits, if a new opposite pivot forms in profit direction, SL moves to it. This locks in gains while letting the runner extend.

---

## Alerts & Telegram Bot

### Setting up TradingView alerts

1. Right-click chart → **Add alert** (or `Alt+A`)
2. **Condition** dropdown 1: your indicator
3. **Condition** dropdown 2: **"Any alert() function call"** ← one alert catches everything
4. **Trigger:** Once Per Bar Close
5. **Expiration:** Open-ended
6. **Notifications:** popup + sound + mobile push (+ email if using Telegram bot)
7. **Create**

### Free tier reality
- 1 active alert on free plan (enough — one alert = all signals)
- Server-side triggers work (fires even when browser closed)
- Mobile push works via TradingView app
- **No webhooks on free plan** (needs Essential $15/mo)

### Telegram bot (folder: `telegram-bot/`)

Two ways to route alerts to Telegram — see **`telegram-bot/SETUP.md`** for full setup.

**Free approach:** `email_to_telegram.py` — polls Gmail for TV alert emails, forwards to Telegram (~15 sec delay).
**Paid approach:** `webhook_bot.py` — direct TV webhook to Telegram bot (instant).

---

## Best Practices & Rules

### Position sizing (mandatory)
- **Max 1% of account per trade**
- Position size = (1% of account) ÷ (entry − SL distance × contract point value)
- Never override this rule for a "sure thing" trade

### Trade limits
- **Max 2 trades per session**
- **Stop after 2 consecutive losses**
- **No revenge trading** — if you feel emotional, close TradingView

### What NOT to do
- ❌ Don't enter mid-candle
- ❌ Don't take BSL/SSL labels as entry signals (those are targets, not triggers)
- ❌ Don't trade during news (NFP, CPI, FOMC, EIA for crude)
- ❌ Don't run indicator across 3 markets simultaneously — pick one
- ❌ Don't disable filters to "get more signals"
- ❌ Don't move SL to give the trade "more room"
- ❌ Don't skip taking TP1 profit — it's what makes the strategy work

### What TO do
- ✅ Screenshot every trade for review
- ✅ Journal outcomes vs. rules followed
- ✅ Backtest 20+ setups on TradingView bar-replay before live trading
- ✅ Trade demo/paper for 2 weeks first
- ✅ Take TP1 partial exactly as shown — this is what makes losing streaks survivable

---

## Timezone & Session Reference (IST)

| Session | GMT | **IST** | Best for |
|---|---|---|---|
| Asian | 00:00–07:00 | 05:30–12:30 | Avoid (traps common) |
| **London** | **07:00–10:00** | **12:30–15:30** | Gold, Crude |
| **London/NY Overlap** | **12:00–16:00** | **17:30–21:30** | Gold, Crude ⭐ prime window |
| **NY AM** | **12:30–15:00** | **18:00–20:30** | Gold, Crude |
| Crypto US Window | 13:00–21:00 | 18:30–02:30 | BTC/ETH |

**Best evening window for Indian trader:** **5:30 PM–9:30 PM IST**
- Gold & Crude: London/NY overlap (same killzones for both — Crude no longer has its own separate NY Pit window)
- Crypto: US session opening

---

## Broker Recommendations for Indian Traders

### 🥇 Primary: MCX via Zerodha / Dhan
- **SEBI regulated, fully legal**
- **Gold Mini** (100g) or **Crude Mini** (10 barrels) — retail-friendly sizes
- Extended session covers London/NY overlap (5:00 PM+ IST)
- Lowest fees, best fills
- Tax clarity (F&O business income)

### 🥈 Secondary: Delta Exchange India
- **SEBI registered**, INR via UPI
- Gold + crypto futures 23/7
- Good for crypto exposure legally
- Slightly lower liquidity than MCX

### ⚠️ Offshore: XM Broker
- Globally regulated (CySEC/ASIC) but **not SEBI**
- Legal grey zone under FEMA in India
- 20% TCS on remittances > ₹7L/year
- Only use if you accept banking + tax complexity

**Skip:** WazirX, CoinDCX (spot-only), unknown offshore forex brokers, telegram signal groups pretending to be brokers.

---

## Troubleshooting

### "No signals firing"
- Check session — is the blue tint showing? If not, wait for killzone
- HTF bias may be conflicting (e.g., 4H bearish but you're waiting for a long)
- ATR wick threshold too high — try lowering to 0.4× temporarily
- Turn off filters one by one to isolate

### "Too many stacked BSL/SSL lines"
- Increase **Merge Zones Within (ticks)** (crypto: 200, gold: 30, crude: 80+)
- Reduce **Max Active BSL/SSL Levels** to 3
- Ensure **Auto-Remove Swept** is ON

### "Old sweep markers cluttering chart"
- Enable **Hide Old Sweeps & Liquidity Pools**
- Set **Keep Only Last N Hours** to 2 or 3

### "Alert not firing"
- Ensure alert condition is **"Any alert() function call"** (not a specific alertcondition)
- Ensure **Trigger** is set to **Once Per Bar Close**
- Free tier: only 1 alert allowed — delete old ones
- Mobile app: enable notifications in TradingView app settings

### "Trade box didn't appear after sweep"
- One filter didn't pass — check status table:
  - Session must be ACTIVE
  - HTF Bias must match sweep direction
  - Sweep candle wick must be ≥ ATR threshold
- View plotshape triangle without box = filters blocked entry (indicator is protecting you)

### "Getting stopped out repeatedly"
- Widen **SL Buffer × ATR** to 0.7–1.0
- Trade higher timeframe (15m instead of 5m)
- Skip news windows (NFP/CPI/FOMC/EIA)
- HTF bias may be wrong — check 4H trend visually

---

## Risk Warnings

⚠️ **This indicator is not a guarantee of profit.** No indicator is. It's a tool that structures a strategy — execution and risk management determine outcomes.

⚠️ **Repainting risk:** Pivots need `pivotRight` bars to confirm. Sweep signals fire on bar close but rely on prior pivots that were confirmed at their time. Do not act on live/unclosed bars.

⚠️ **Backtest before live:** Use TradingView **bar replay** (Plus plan) to replay 30–50 setups and check the strategy's realistic win rate on your chosen instrument.

⚠️ **Paper trade first:** Trade demo for 2 weeks minimum. Real money adds emotional pressure that changes execution.

⚠️ **India legal:** Offshore forex/CFD trading (XM etc.) is a FEMA grey zone. Use SEBI-regulated brokers (MCX, Delta India) when in doubt.

⚠️ **Tax:**
- MCX F&O: business income, slab rates, can offset losses
- Crypto: 30% capital gains + 1% TDS on every sell
- Offshore forex profits: "income from other sources" at slab rate

⚠️ **Position sizing is more important than entries.** A 60% winrate strategy blows up if position sizes are too big. Respect the 1% rule.

---

## Quick Start Checklist

Before your first live trade:

- [ ] Indicator added to chart on 5m timeframe
- [ ] Auto-Detect Market Mode ON (or Market Mode set correctly if you're using it manually)
- [ ] Session filter ON (unless trading crypto 24/7)
- [ ] HTF Bias filter ON
- [ ] Trade Management enabled
- [ ] Alert created: "Any alert() function call", Once Per Bar Close, mobile push ON
- [ ] Telegram bot running (optional)
- [ ] Broker account funded and tested with a demo trade
- [ ] Position size calculator ready (1% risk per trade)
- [ ] Journal / spreadsheet set up for trade logging
- [ ] Read this document fully
- [ ] Paper traded 20+ setups
- [ ] Know today's news calendar (skip trades ±15 min around releases)

---

## Files in This Project

| Path | Purpose |
|---|---|
| `trading-view-algo` | The Pine Script v6 indicator (paste into TradingView) |
| `HOW_TO_USE.md` | This guide |
| `telegram-bot/webhook_bot.py` | Webhook receiver for TV Essential plan |
| `telegram-bot/email_to_telegram.py` | Email bridge for TV free plan |
| `telegram-bot/requirements.txt` | Python deps for bot |
| `telegram-bot/SETUP.md` | Bot setup instructions |

---

## Support / Questions

Since this is a personal setup, the indicator's inputs are the "documentation." Every setting has a tooltip in TradingView — hover the (i) icon.

For strategy questions, revisit the **How to Take Trades** and **Best Practices** sections. Most issues come from skipping the "wait for candle close" rule or ignoring the HTF bias filter.

**Trade safe. Position size first. Setup second.**
