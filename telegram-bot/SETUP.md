# TradingView → Telegram Bot Setup

Two ways to receive TradingView alerts on Telegram. Pick based on your TradingView plan.

---

## PART 1: Create Telegram Bot (needed for BOTH approaches)

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g., "Gold Gaurav Bot") and username (e.g., `gold_gaurav_bot`)
4. Copy the **bot token** (looks like `123456789:AAH...`)
5. Search your bot in Telegram → click **Start** → send any message ("hi")
6. Get your **chat ID:** open this URL in browser:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Look for `"chat":{"id":123456789,...}` — that number is your chat ID.

Save both:
- `TELEGRAM_BOT_TOKEN` = the bot token
- `TELEGRAM_CHAT_ID`   = your chat ID

---

## APPROACH A — Email Bridge (FREE TradingView plan)

Runs on your Mac. Polls Gmail for TradingView alert emails and forwards to Telegram.

### Setup
1. **Enable IMAP in Gmail:**
   Gmail → Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP → Save

2. **Create Gmail App Password** (regular password won't work):
   - Go to https://myaccount.google.com/apppasswords
   - Requires 2-Step Verification to be ON
   - Create password named "TV Bot" → copy 16-char password

3. **Install Python packages:**
   ```bash
   cd "/Users/trell/Desktop/untitled folder/telegram-bot"
   pip3 install -r requirements.txt
   ```

4. **Set environment variables** (edit or use export):
   ```bash
   export GMAIL_USER="gauravism2016@gmail.com"
   export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
   export TELEGRAM_BOT_TOKEN="123456789:AAH..."
   export TELEGRAM_CHAT_ID="123456789"
   ```

5. **Configure TradingView alert:**
   - Right-click chart → Add alert
   - Condition: your indicator → "Any alert() function call"
   - Notifications: **☑ Send email**
   - Save

6. **Run the bridge:**
   ```bash
   python3 email_to_telegram.py
   ```

You should get a "Bot connected" message in Telegram immediately.
Now whenever TradingView emails you an alert, it forwards to Telegram in ~15 seconds.

### Keep it running 24/7
Keep the terminal open, OR set up a launchd service on macOS to run in background.

---

## APPROACH B — Webhook (needs TradingView Essential ~$15/mo)

Runs on a free cloud host. Instant (<1 sec delay).

### Setup

1. **Install packages locally to test:**
   ```bash
   cd "/Users/trell/Desktop/untitled folder/telegram-bot"
   pip3 install -r requirements.txt
   ```

2. **Test locally:**
   ```bash
   export TELEGRAM_BOT_TOKEN="123..."
   export TELEGRAM_CHAT_ID="123..."
   export WEBHOOK_SECRET="mySecretPass123"
   python3 webhook_bot.py
   ```
   You'll see: `Running on http://0.0.0.0:5000`

3. **Test with curl** (in another terminal). Either method works:
   ```bash
   # Secret in the body (what the Pine alert() sends)
   curl -X POST http://localhost:5000/webhook \
     -H "Content-Type: application/json" \
     -d '{"secret":"mySecretPass123","text":"GOLD LONG entry @ 2385 | SL 2382 | TP1 2390"}'

   # Secret in the URL (most robust — recommended for TradingView)
   curl -X POST "http://localhost:5000/webhook?secret=mySecretPass123" \
     -H "Content-Type: application/json" \
     -d '{"text":"GOLD LONG entry @ 2385 | SL 2382 | TP1 2390"}'
   ```
   Check Telegram — you should get the formatted message.

4. **Deploy to free cloud host (Render.com recommended):**
   - Sign up at render.com
   - New → Web Service → Connect GitHub or upload code
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `python webhook_bot.py`
   - Add environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_SECRET)
   - Deploy → copy the URL (e.g., `https://tv-bot.onrender.com`)

5. **Configure TradingView webhook:**
   - Right-click chart → Add alert
   - Condition: your indicator → **"Any alert() function call"**
   - Notifications tab: **Webhook URL** = put the secret directly in the URL:
     ```
     https://tv-bot.onrender.com/webhook?secret=mySecretPass123
     ```
   - Message field (Alert message): leave it as just:
     ```
     {{message}}
     ```

   > ⚠️ **Do NOT double-wrap the JSON.** The Pine script's `alert()` already
   > sends a complete `{"secret":"...","text":"..."}` body via its `f_json()`
   > helper. If you ALSO wrap `{{message}}` inside another `{"secret":...}`
   > object in the message box, you get nested/broken JSON, the secret parses
   > as `null`, and the bot returns **401 Unauthorized**.
   >
   > Putting `?secret=` in the URL (as above) is the most reliable method — it
   > authenticates regardless of the body format, so it works for both
   > `alert()` messages and plain-text `alertcondition` sweep alerts.

   The `secret` value in the URL must match the `WEBHOOK_SECRET` env var on
   Render **exactly** (and the `webhookSecret` input in the indicator, which
   defaults to `telegram123`).

Done. Any alert now hits Telegram in under a second.

### Quick verification before relying on it
1. Open `https://tv-bot.onrender.com/debug` — confirm `webhook_secret_set: true`
   and that `webhook_secret_length` matches your secret's length.
2. Fire a test POST (matches what TradingView sends):
   ```bash
   curl -i -X POST "https://tv-bot.onrender.com/webhook?secret=mySecretPass123" \
     -H "Content-Type: application/json" \
     -d '{"text":"test 123"}'
   ```
   A `200` plus a Telegram message means it's wired correctly. A `401` means the
   secret in the URL does not match Render's `WEBHOOK_SECRET` — check the Render
   logs, which print the received vs expected secret side by side.

---

## PART 2 — One-Tap Order Button (Kotak Neo + Delta Exchange + XM)

Only works with **Approach B** (webhook), since it needs a public server to host
the confirmation page. Every LONG/SHORT **entry** alert (not TP/SL hit alerts)
now arrives in Telegram with three buttons:

- **🟢 Review & Place (Kotak Neo)** — opens a confirmation page on your Render
  server showing the signal (symbol, side, entry, SL, TP1–3), with editable
  **quantity** and **trading symbol** fields. Tapping **Confirm & Place** there
  calls the official Kotak Neo Trade API (MCX — gold) and submits a real market order.
- **🟢 Review & Place (Delta Exchange)** — same confirm/place flow, but calls
  Delta Exchange India's REST API (crypto perpetuals, plus their gold
  futures). Independent from the Kotak button — placing on one broker does
  **not** lock out the other for the same signal, since they're separate
  accounts/separate money.
- **📱 Open XM App** — just opens XM's app/trading page. XM (MT4/MT5) doesn't
  publish a deep-link format for pre-filling an order, so you still type the
  trade in yourself using the numbers in the alert message.

### ⚠️ Safety model — read before enabling

- **Defaults to DRY RUN for both brokers.** Until you set `LIVE_TRADING=true`,
  tapping "Confirm & Place" never contacts Kotak's or Delta's servers or risks
  real money — it just shows you what *would* have been sent. Verify a few
  dry runs look correct first. `LIVE_TRADING` is one shared switch for both
  brokers — there's no way to go live on one and stay dry-run on the other.
- **No SL/TP is sent to either broker.** Only a plain entry order is placed.
  You still manage exits manually off the SL/TP1/TP2/TP3 levels exactly as
  before (via the alerts you already get for TP/SL hits).
- **Confirmation links expire after 10 minutes**, and each broker's button is
  single-use once *that* broker's placement succeeds — an old, stale-priced
  signal can't be fired late, and a successful Kotak order won't block a
  legitimate Delta order on the same signal (or vice versa).
- **Keep the Render start command as `python webhook_bot.py`** (not a
  multi-worker gunicorn setup). The pending-order state lives in memory in one
  process; multiple workers would randomly 404 on confirm/place.
- **Double-check the symbol field every time.** The indicator's ticker (e.g.
  `XAUUSD`, `BTCUSD`) does not necessarily match Kotak Neo's exact contract
  code (e.g. `GOLDM26AUGFUT`) or Delta's product symbol — crypto usually lines
  up (`BTCUSD`), gold contracts often don't. The form pre-fills your
  configured default but you choose what actually gets sent.

### Setup — Kotak Neo

1. **Get Kotak Neo API credentials:**
   - Kotak Neo app/web → **Invest** tab → **Trade API** card → **Create Application**
   - Copy the generated **Consumer Key** (this is your API access token)
   - Set up **TOTP 2FA** for API login (Google/Microsoft Authenticator) — when
     scanning the QR code, your authenticator app (or Kotak's setup screen)
     will also show the underlying **base32 secret as text** — copy that, not
     the 6-digit code. This is `KOTAK_NEO_TOTP_SECRET`.
   - Note your **UCC** (client code) and **MPIN**

2. **Add environment variables on Render** (Dashboard → your service → Environment):
   ```
   KOTAK_NEO_CONSUMER_KEY=<consumer key from step 1>
   KOTAK_NEO_MOBILE=+91XXXXXXXXXX
   KOTAK_NEO_UCC=<your client code>
   KOTAK_NEO_MPIN=<your Neo app MPIN>
   KOTAK_NEO_TOTP_SECRET=<base32 secret from step 1>
   KOTAK_NEO_DEFAULT_SYMBOL=GOLDM26AUGFUT   # update each month when the contract rolls
   KOTAK_NEO_DEFAULT_QTY=1
   ```
   Optional (defaults shown): `KOTAK_NEO_EXCHANGE_SEGMENT=mcx_fo`,
   `KOTAK_NEO_PRODUCT=MIS`, `KOTAK_NEO_ORDER_TYPE=MKT`.

3. **The `neo_api_client` SDK is NOT installed by default.** It hard-pins
   `requests==2.32.3`, which conflicts with this project's own `requests==2.31.0`
   pin and breaks the Render build — so it's deliberately left out of
   `requirements.txt`. Dry-run mode never needs it (tapping "Confirm & Place"
   with `LIVE_TRADING=false` just shows a preview). **Only when you're ready to
   go live with Kotak specifically**, edit `telegram-bot/requirements.txt`:
   bump `requests==2.31.0` to `requests==2.32.3`, and add
   `git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git@v2.0.2#egg=neo_api_client`
   back in, then redeploy. Until then, flipping `LIVE_TRADING=true` and tapping
   Kotak's button will just return a clear "neo_api_client is not installed"
   error instead of a crash.

### Setup — Delta Exchange

1. **Get API credentials:** Delta Exchange India → Account → **API Keys** →
   create a new key. Copy the **API Key** and **API Secret** immediately — the
   secret is only shown once.
2. **Add environment variables on Render:**
   ```
   DELTA_API_KEY=<api key>
   DELTA_API_SECRET=<api secret>
   DELTA_DEFAULT_SYMBOL=BTCUSD   # e.g. BTCUSD/ETHUSD for crypto; check Delta's gold contract symbol separately
   DELTA_DEFAULT_QTY=1
   ```
   Optional (defaults shown): `DELTA_BASE_URL=https://api.india.delta.exchange`,
   `DELTA_ORDER_TYPE=market_order`.

### Setup — BTC/ETH/SOL Auto-Trade (no confirm tap)

Separate from the manual Delta button above: **entry alerts for BTC, ETH, or SOL skip
the Telegram confirm step entirely** and place the order automatically the instant the
webhook receives them. Everything else (Gold via Kotak, or any other symbol via the
manual Delta button) is unaffected.

⚠️ **Read this before enabling.** Defaults are 15% of account balance as margin **per
symbol** (so BTC+ETH+SOL firing together can use up to 45% combined), at **200x
leverage on BTC/ETH and 100x on SOL** (Delta's actual maximums). At 200x, Delta's
forced liquidation triggers at roughly a **0.5% adverse price move** — inside a normal
5-minute BTC/ETH candle range. In practice this means **the exchange's liquidation
engine, not the indicator's own stop-loss, decides the exit on most losing trades**,
consuming the full margin on that symbol rather than the smaller loss the strategy's SL
was sized for. This is documented in detail at the top of the AUTO-TRADE section in
`delta_exchange_client.py`. If you want the strategy's own SL to actually govern
outcomes instead, lower the leverage env vars below.

1. **Add environment variables on Render** (in addition to `DELTA_API_KEY`/`DELTA_API_SECRET` above):
   ```
   DELTA_AUTO_TRADE_CRYPTO=true    # master toggle — set false to disable entirely
   DELTA_CAPITAL_PCT=15            # % of balance used as margin, per symbol
   DELTA_LEVERAGE_BTC=200
   DELTA_LEVERAGE_ETH=200
   DELTA_LEVERAGE_SOL=100          # Delta caps SOLUSD at 100x — 200x isn't offered there
   ```
   Optional (defaults shown), controlling the SL/TP attached to every auto-trade:
   ```
   DELTA_BRACKET_TP_TIER=tp1          # which of the alert's TP1/TP2/TP3 to use as the target
   DELTA_BRACKET_SLIPPAGE_PCT=0.3     # limit-price buffer beyond SL/TP trigger, for fill odds
   DELTA_BRACKET_TRIGGER=last_traded_price
   ```

2. **What gets placed:** every auto-trade now attaches a stop-loss AND a take-profit to
   the entry in the same API call — the position isn't naked anymore. Both prices come
   straight from the alert (the Pine script already computes them). **Important:** the
   take-profit is a single price (TP1 by default) and the position closes **100% there**
   — this does **not** replicate the Pine script's tiered 50%/30%/20% partial-exit
   display. If you want the bot to actually mirror that tiering (3 separate bracket
   orders, plus moving the SL to breakeven when a TP1-hit alert later arrives), that's a
   bigger follow-up feature — ask for it explicitly.

3. **Test against Delta's TESTNET before touching the real account.** The field names
   this code expects for wallet balance, ticker, and bracket-order responses were built
   from Delta's docs and published Python SDK examples, but weren't confirmed against a
   live response at build time — this is true for the SL/TP bracket fields specifically
   (`bracket_stop_loss_price` etc.), not just the balance lookup. To validate safely:
   - Create a **separate testnet API key** (Delta's demo account — testnet keys only
     work against the testnet URL, and vice versa)
   - Temporarily set `DELTA_BASE_URL=https://cdn-ind.testnet.deltaex.org` and
     `DELTA_API_KEY`/`DELTA_API_SECRET` to the testnet key, with `LIVE_TRADING=true`
   - Fire a real BTC alert (or hit `/webhook` manually — see the curl example earlier
     in this doc) and check Render logs / the Telegram message for whether the computed
     balance, size, leverage, AND the attached SL/TP prices look sane, and then check
     Delta's testnet app directly to confirm the stop-loss and take-profit orders
     actually appear against the open position. If the code hits an unexpected response
     shape it raises a clear error rather than silently computing something wrong — if
     you see "AUTO-TRADE FAILED", the field-name assumptions need adjusting before going
     live, not just the sizing math.
   - Only once that looks right, switch `DELTA_BASE_URL` back to production and use
     your real API key.

4. **Note on webhook timing:** the auto-trade path makes several sequential API calls
   to Delta (balance → product info → set leverage → mark price → place order with
   bracket) before the webhook responds to TradingView. This can take longer than a
   simple order placement — worth watching Render's logs the first few times to confirm
   it's completing well within TradingView's webhook timeout.

5. **Still not automated:** TP1/TP2/TP3/SL-hit alerts for BTC/ETH/SOL remain
   notification-only for anything BEYOND the single bracket SL/TP placed at entry — e.g.
   the Pine script's SL→breakeven-at-TP1 logic doesn't get mirrored on Delta's side, and
   TP2/TP3 (if not the chosen bracket tier) don't trigger anything. The bracket SL/TP
   placed at entry is a static, one-time thing, not a dynamically managed position.

### Shared setup (both brokers)

1. **Add these env vars too:**
   ```
   PUBLIC_BASE_URL=https://tv-bot.onrender.com   # your actual Render URL
   XM_APP_URL=https://www.xm.com/mt5             # optional override
   LIVE_TRADING=false                             # keep false until dry runs look right
   ```

2. **Redeploy** so `requirements.txt` picks up `pyotp` (Delta only needs
   `requests`, already installed; Kotak's SDK is intentionally not installed
   yet — see step 3 above).

3. **Trigger a test entry alert** and tap either **Review & Place** button in
   Telegram — with `LIVE_TRADING=false` you'll land on a page reading
   "🟢 DRY RUN", and confirming will show `[DRY RUN] Would place ...` with no
   real order sent. Try both buttons on the same signal to confirm they don't
   block each other.

4. **Go live** only once dry runs look correct on both: set `LIVE_TRADING=true`
   on Render and redeploy. The confirmation pages will now show a red
   "🔴 LIVE" banner, and confirming submits a real order.

---

## Testing your setup

Force a test alert:
1. Change your indicator's session filter OFF temporarily
2. Or use TradingView's "Trigger Once" button in the alert dialog
3. Or send test HTTP request (Approach B)

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Telegram: "Unauthorized" | Bot token wrong or bot not started |
| No emails coming | Check spam folder; verify TradingView alert notification is set to email |
| Gmail login fails | You must use App Password, not regular password |
| Bot connected but no forwards | Ensure email FROM matches `noreply@tradingview.com` |
| Webhook returns 401 | Secret mismatch. Fix order: (1) put `?secret=YOURSECRET` in the webhook URL; (2) confirm Render `WEBHOOK_SECRET` == indicator `webhookSecret`; (3) don't double-wrap `{{message}}` in the message box — leave it as just `{{message}}`. Check Render logs: they print received vs expected secret. |
| 401 with `"received_is_none": true` | The bot found no secret at all — you're likely using a plain-text alert or double-wrapped JSON. Add `?secret=YOURSECRET` to the webhook URL. |
| Render sleeps after 15 min | Free tier limitation — cold start can exceed TradingView's ~3s wait and look like a failure. Use UptimeRobot to ping the app every 5 min. |

---

## Recommendation

**Start with Approach A** (email bridge, free).
- No cloud hosting cost
- No TradingView paid plan
- Only 15-second delay — acceptable for 5m/15m trading

Move to Approach B if you scale to 1m scalping or want zero-delay alerts.
