# How to Use — MCX Gold Mini (GOLDM) Intraday

Complete guide to trading MCX Gold Mini futures using the `trading-view-algo` indicator in **Gold mode**.

No code changes needed. Same indicator, same strategy — just applied to MCX Gold Mini with Indian market timings.

---

## Table of Contents

1. [Why MCX Gold Mini](#why-mcx-gold-mini)
2. [Contract Specs](#contract-specs)
3. [Trading Hours (IST)](#trading-hours-ist)
4. [Setup Steps](#setup-steps)
5. [Recommended Settings](#recommended-settings)
6. [Daily Trading Windows](#daily-trading-windows)
7. [Position Sizing](#position-sizing)
8. [How Signals Work](#how-signals-work)
9. [Correlation with XAUUSD](#correlation-with-xauusd)
10. [Broker Setup](#broker-setup)
11. [Days to Skip](#days-to-skip)
12. [Rules & Best Practices](#rules--best-practices)
13. [Troubleshooting](#troubleshooting)

---

## Why MCX Gold Mini

Perfect fit for Indian retail gold intraday trader.

### Advantages
- ✅ **SEBI regulated** — 100% legal in India
- ✅ **INR settled** — no forex conversion, no TCS
- ✅ **Deep liquidity** during evening session
- ✅ **Follows XAUUSD ~99%** — same technical patterns work
- ✅ **F&O tax treatment** — losses can offset gains
- ✅ **Zerodha/Dhan support** — cheap brokerage
- ✅ **Retail-friendly margin** (~₹45,000 for 1 lot)

### Why it beats XM/offshore forex
| Feature | XM Broker | **MCX Gold Mini** |
|---|---|---|
| Legal in India | Grey zone (FEMA) | **Fully legal** |
| Currency | USD | **INR** |
| Tax | Slab rate | F&O business income |
| Bank scrutiny | High (FEMA) | None |
| Regulation | Offshore | **SEBI** |
| TCS on funding | 20% >₹7L/yr | None |

---

## Contract Specs

### GOLDM (Gold Mini) ⭐ Recommended
- **Lot size:** 100 grams of gold
- **Quote:** ₹ per 10 grams (e.g., 75,000)
- **Tick:** ₹1 per 10 grams
- **Point value:** ₹100 per rupee move
- **Margin:** ~₹40,000–50,000 intraday
- **Expiry:** Monthly (5th of every month)

### GOLDPETAL (1 gram)
- 100× smaller than GOLDM
- Point value: ₹1 per rupee move
- Margin: ~₹500
- **For very small accounts** (<₹1L)

### GOLD (Full)
- 1kg contract
- Point value: ₹1,000 per rupee move
- Margin: ~₹4-5 lakh
- Too big for retail

**Retail recommendation: GOLDM.** If capital <₹1L, use GOLDPETAL.

---

## Trading Hours (IST)

| Session | IST Time | GMT | Volume | Overlap with |
|---|---|---|---|---|
| Morning | 9:00 AM – 5:00 PM | 03:30–11:30 | Low-medium | Asia (early) → London (later) |
| **Evening** ⭐ | **5:00 PM – 11:30 PM** | 11:30–18:00 | **Highest** | London/NY overlap |

### Golden window for you
**5:30 PM – 9:30 PM IST**

This overlaps perfectly with:
- **London PM close** (5:30–7:00 PM IST)
- **NY AM open** (6:30–8:30 PM IST) ⭐ prime
- **London/NY overlap** (5:30–9:30 PM IST) ⭐ prime

**Highest institutional flow = cleanest signals = best trades.**

---

## Setup Steps

### 1. Open TradingView chart
Symbol: **MCX:GOLDM1!** (continuous mini contract)

Or specific month: MCX:GOLDMOCT2026 etc.

### 2. Set timeframe to 5m
5-minute chart is the standard for this strategy.

### 3. Load indicator
- Pine Editor → paste `trading-view-algo` contents → Save → Add to chart
- (Skip if already loaded from before — same indicator works)

### 4. Verify settings
- **Auto-Detect Market Mode:** ON (default) — `MCX:GOLDM1!` contains "GOLD" so it auto-selects Gold mode; no manual step needed. **Market Mode (manual/fallback):** Gold (default, used if you turn auto-detect off)
- **Session filter:** ON
- Session Timezone: **GMT** (killzones auto-align with IST evening)
- All other filters: default

### 5. Set up alerts
- Right-click chart → Add alert
- Condition: your indicator → **"Any alert() function call"**
- Trigger: Once Per Bar Close
- Notifications: mobile push + Telegram webhook (if bot set up)

### 6. Done — wait for evening
Chart is ready. Now wait for the 5–9:30 PM IST window to trade.

---

## Recommended Settings

Default Gold mode works. Optional tweaks:

| Setting | Default (XAUUSD) | **Optimal for MCX GOLDM** |
|---|---|---|
| Market Mode | Gold | **Gold** (keep) |
| Session filter | ON | **ON** (keep) |
| London Killzone | `0700-1000` GMT | Keep |
| NY AM Killzone | `1230-1500` GMT | Keep |
| Overlap | `1200-1600` GMT | Keep |
| Session Timezone | GMT | **GMT** (keep) |
| HTF Bias TF | 4H (240) | Keep |
| ATR wick × mult | 0.5 | **0.5** (keep) |
| Equal H/L Tolerance | 10 ticks | **15 ticks** (MCX gold ticks slightly wider) |
| Merge zones | 30 ticks | **40 ticks** |
| SL buffer × ATR | 0.5 | **0.6** (MCX spikes more) |
| Max Active Levels | 4 | Keep |
| Cleanup lookback | 4 hours | **3 hours** |

**Minimum viable config:** Just switch Mode to Gold, everything else default. Trade.

---

## Daily Trading Windows

### Morning session (Skip most days)
| Time (IST) | Notes |
|---|---|
| 9:00–10:00 AM | Low volume, wait |
| 10:00 AM – 2:00 PM | Almost dead — skip |
| 2:00–4:00 PM | Asia + early London — sometimes decent |
| 4:00–5:00 PM | Pre-evening buildup |

### ⭐ Evening session (PRIME WINDOW)
| Time (IST) | Session | Trade? |
|---|---|---|
| **5:00–5:30 PM** | Evening open + London PM catchup | Wait for setup |
| **5:30–7:00 PM** ⭐ | London PM close activity | Yes — high probability |
| **7:00–9:30 PM** ⭐⭐ | NY AM + Overlap | Best trades of day |
| 9:30–11:30 PM | NY afternoon | Yes but reduce size |
| 11:30 PM close | Market ending | Don't take new trades |

### Simple rule
**Trade 5:30 PM – 9:30 PM only.**

If you can only trade 2 hours a day, make it **6:30 PM – 8:30 PM IST** — highest institutional flow window on the planet for gold.

---

## Position Sizing

### GOLDM sizing formula
```
Position (lots) = (Account × Risk%) ÷ (SL Distance × ₹100)
```

### Example 1: Standard account
- Account: **₹2,00,000**
- Risk per trade: 1% = **₹2,000**
- Entry: 75,000, SL: 74,950 (**50-point stop**)
- Risk per lot: 50 × ₹100 = **₹5,000 per lot**
- **Position: 0 lots** ❌ SL too wide for account size

### Example 2: Tight setup
- Account: ₹2,00,000
- Entry: 75,000, SL: 74,980 (**20-point stop**)
- Risk per lot: 20 × ₹100 = ₹2,000
- **Position: 1 lot** ✅

### Example 3: Larger account
- Account: **₹5,00,000**
- Risk: 1% = ₹5,000
- 50-point SL
- **Position: 1 lot** ✅ with room

### The math reality
| Account | Max SL for 1 GOLDM lot (1% risk) |
|---|---|
| ₹1L | Skip GOLDM — use GOLDPETAL |
| ₹2L | 20-point SL max |
| ₹3L | 30-point SL max |
| ₹5L | 50-point SL max |
| ₹10L | 100-point SL max ⭐ comfortable |

**If ₹2L account:** either wait for tight setups (20-point SL) OR trade GOLDPETAL (100× smaller).

### GOLDPETAL sizing
- Account: ₹1,00,000, Risk: ₹1,000
- 50-point SL × ₹1 (petal point value) = ₹50 risk per lot
- **Position: 20 lots** ✅ easy sizing

**GOLDPETAL is way more retail-friendly for small accounts.**

---

## How Signals Work

Exactly the same as XAUUSD — no difference.

### Signal flow
1. **Sweep candle closes** (wick past level, close back inside)
2. **All filters must pass:**
   - In killzone (London PM / NY AM / Overlap — all matter for MCX evening)
   - HTF bias agrees (4H EMA)
   - Wick ≥ 0.5× ATR
3. **Green LONG or red SHORT box appears** with:
   - Entry price
   - SL
   - TP1 (nearest opposite pivot)
   - TP2 (opposite BSL/SSL pool)
   - TP3 (Day High/Low)
4. **You enter at market or limit** in Kite/Dhan at the shown entry price
5. **Follow alerts** as TP1/TP2/TP3/SL hit

### Example signal on MCX GOLDM

```
GOLD LONG @ 75,240
SL: 75,180 (60-point stop)
TP1 (50%): 75,320
TP2 (30%): 75,410
TP3 (20%): 75,540
```

### Execution
1. Copy prices into Zerodha Kite
2. Buy 1 lot GOLDMCT2026 at market (75,240)
3. Place SL-M order at 75,180
4. Place 3 target orders: 50 units at 75,320, 30 units at 75,410, 20 units at 75,540

Wait — GOLDM lot = 100g = 1 unit. You can't do partial lots on MCX futures.

**Practical workaround:**
- Trade **2 GOLDM lots** (if capital allows) → close 1 at TP1, 1 at TP2/TP3
- Or use **20 GOLDPETAL lots** — do partial fills: 10 at TP1, 6 at TP2, 4 at TP3

---

## Correlation with XAUUSD

MCX GOLDM tracks XAUUSD closely.

### Why to also watch XAUUSD chart
- Better tick data (deeper liquidity globally)
- Signals form 2-5 min BEFORE MCX price catches up
- Cleaner charts (less noise)

### Recommended dual-chart setup
- **Primary chart:** XAUUSD 5m with indicator loaded (for signal generation)
- **Execution chart:** MCX:GOLDM1! for placing actual orders

When XAUUSD signal fires → immediately place order on MCX in Kite.

### Watch for divergence
Rare, but if MCX price is significantly off XAUUSD (>0.3% differential), skip — likely arbitrage in progress or MCX-specific issue.

---

## Broker Setup

### 🥇 Zerodha
- Best for MCX
- ₹20 flat per order
- Kite has decent charts (but use TradingView for signals)
- Full MCX gold contract range

### Steps to trade GOLDM
1. Zerodha → Kite → Search "GOLDM"
2. Pick nearest expiry (e.g., GOLDMOCT2026 if in Oct)
3. Buy/sell → market or limit
4. Place SL-M and GTT target orders separately

### Alternative brokers
- **Angel One** — good MCX interface
- **Dhan** — fast execution, options-focused
- **5paisa** — sometimes lower margins

---

## Days to Skip

Do not trade MCX Gold on:

| Event | Frequency | Why |
|---|---|---|
| **US FOMC** (Fed meeting) | ~8/year | 2 AM IST → next-day gap |
| **US CPI release** | Monthly | 6 PM IST → wild moves |
| **US NFP** | Monthly (1st Fri) | 6 PM IST → chaos |
| **Powell speeches** | ~monthly | Gold whipsaws |
| **Israel/geopolitical news** | Rare | Overnight gaps |
| **Budget Day (India)** | Yearly | Feb 1, chaotic |
| **RBI Policy** | Bi-monthly | 2:30 PM IST, affects INR → indirectly gold in ₹ |
| **Contract expiry (5th monthly)** | Monthly | Roll to next month prior |
| **Bank holidays** | Yearly | Reduced liquidity |

Check https://www.forexfactory.com/calendar or Investing.com daily before 5 PM IST.

---

## Rules & Best Practices

### DO
- ✅ Trade only 5:30–9:30 PM IST
- ✅ Max 2 trades per session
- ✅ Stop after 2 losses in one session
- ✅ Wait for candle CLOSE before entering
- ✅ Use exact SL/TP from indicator box
- ✅ Move SL to breakeven at TP1
- ✅ Journal every trade with screenshots
- ✅ Skip news days
- ✅ Roll to next contract 3 days before expiry

### DON'T
- ❌ Don't trade morning session (too illiquid, false signals)
- ❌ Don't trade during US news releases
- ❌ Don't enter mid-candle
- ❌ Don't take BSL/SSL labels alone as entries — WAIT FOR THE BOX
- ❌ Don't move SL wider "for room"
- ❌ Don't ignore TP1 partial — it's what makes the strategy work
- ❌ Don't take a 3rd trade after 2 losses — statistical noise
- ❌ Don't trade GOLD (full 1kg) unless you have ₹10L+ account

### Position management
- Enter → set SL → set 3 targets
- TP1 hit → close partial + move SL to entry (breakeven)
- TP2 hit → close partial + trail SL to last swing low
- TP3 hit → close all
- SL hit → accept the loss, no revenge

---

## Troubleshooting

### "MCX chart shows delayed data"
- TradingView free tier shows 15-min delayed MCX data
- **Fix:** Subscribe to TradingView India data (~₹100/month) for real-time
- Or watch XAUUSD (always real-time) for signals, execute on MCX

### "No signals during morning session"
- Expected — morning MCX has poor liquidity
- Session filter correctly rejects morning setups
- **Wait for 5:30 PM IST**

### "Signal fires but MCX price didn't move yet"
- MCX often lags XAUUSD by 2-5 min
- If you have both charts open, execute on MCX when it catches up
- If only MCX chart, wait for MCX candle to close beyond signal level

### "Contract expired — can't trade"
- Roll to next month contract 3 days before expiry (5th of month)
- Use MCX:GOLDM1! (continuous) for chart, but execute on specific expiry contract

### "Losing trades even in evening session"
- Check if you're taking every signal — should be 1-2/day max
- Verify HTF bias is aligned (status table)
- Skip if in-session news is pending (check Forex Factory)

### "Position size too big"
- 1 GOLDM lot = ₹4L exposure — needs ₹5L+ account for proper sizing
- Solution: use GOLDPETAL instead (100× smaller)
- Or trade Gold options (buy far OTM call/put — smaller premium at risk)

---

## Quick Start Checklist

Before your first live GOLDM trade:

- [ ] Zerodha account funded with ₹2L+ (for GOLDM) or ₹1L (for GOLDPETAL)
- [ ] `trading-view-algo` loaded on MCX:GOLDM1! 5m chart
- [ ] Market Mode: Gold (default)
- [ ] TradingView alert created ("Any alert() function call")
- [ ] Telegram bot receiving alerts (test with existing setup)
- [ ] Watched a full 5–9:30 PM session in demo mode
- [ ] Understand sizing: max risk = 1% of account
- [ ] Know today's news calendar (skip if Fed/CPI/NFP)
- [ ] Verified contract expiry is >3 days away
- [ ] Journal ready for logging

---

## Files Reference

| Path | Purpose |
|---|---|
| `trading-view-algo` | The indicator (Gold mode works for MCX GOLDM) |
| `HOW_TO_USE.md` | General guide for the indicator (gold/crypto/crude) |
| `HOW_TO_USE_INDIAN.md` | Indian stocks intraday guide |
| `HOW_TO_USE_GOLDMINI_MCX.md` | **This guide** — MCX Gold Mini specific |

---

## Bottom Line

**MCX Gold Mini + `trading-view-algo` Gold mode = perfect combo for Indian retail gold trader.**

- No code changes needed
- Same strategy that works on XAUUSD
- Legal + tax-clean
- INR native
- Best window: **5:30–9:30 PM IST**
- Perfect overlap with London/NY prime hours

**Trade the evening session, follow the box, take TP1 partial, stop after 2 losses. That's the whole playbook.**
