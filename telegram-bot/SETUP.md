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
