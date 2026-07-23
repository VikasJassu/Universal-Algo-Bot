"""
TradingView Webhook → Telegram Bot
Receives POST requests from TradingView alerts and forwards to Telegram.
Requires TradingView Essential plan (webhook alerts).

Entry signals (LONG/SHORT entry alerts) are handled one of two ways:

  - **BTC / ETH / SOL / PAXG / XAUT** -> fully automatic, no confirm tap. The instant
    the alert arrives, delta_exchange_client.auto_place_order() sizes the position at 15%
    of account balance as margin (independently per symbol) at a preset leverage
    (200x BTC/ETH, 100x SOL/PAXG/XAUT — Delta's own max), and places the order immediately.
    (PAXGUSD / XAUTUSD are Delta India's gold-token perpetuals.)
    Telegram gets a notification AFTER the fact reporting what happened — it's not
    a gate. Still dry-run by default until LIVE_TRADING=true. See the AUTO-TRADE
    section in delta_exchange_client.py for the full risk tradeoffs of this
    leverage/sizing combo (deliberately confirmed, not an oversight).
  - **Everything else** (Gold/MCX via Kotak Neo, or manual Delta/XM) -> the
    original three-button flow:
      - "Review & Place (Kotak Neo)" -> opens a confirmation page on this same
        server; tapping "Confirm & Place" calls the Kotak Neo Trade API
        (see kotak_neo_client.py). Dry-run by default until LIVE_TRADING=true.
      - "Review & Place (Delta Exchange)" -> same confirm/place flow via Delta's
        REST API, for any symbol not covered by the BTC/ETH/SOL/PAXG/XAUT auto-trade path.
      - "Open XM App" -> best-effort link to XM's app/web trading page. XM/MT5
        don't publish a deep-link format for pre-filling an order, so this only
        opens the app — you still enter the trade manually from the message text.
"""
import html
import json
import os
import re
import secrets
import time

from flask import Flask, request, jsonify, Response
import requests

import kotak_neo_client
import delta_exchange_client

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "PASTE_YOUR_CHAT_ID_HERE")
WEBHOOK_SECRET     = os.environ.get("WEBHOOK_SECRET",     "change-me-to-random-string").strip()

# Public base URL of this server, e.g. "https://tv-bot.onrender.com" — used to build
# the Kotak Neo confirmation link inside Telegram messages. Falls back to whatever
# Flask thinks the request host is if not set, but setting it explicitly avoids any
# http/https or proxy-header quirks behind Render's load balancer.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

# Best-effort "open the app" link for XM. Neither XM nor MT4/MT5 publish a documented
# deep-link format for pre-filling an order (symbol/SL/TP) from an external link, so
# this just opens XM's mobile trading page/app — you still type in the trade yourself
# using the numbers already in the alert text.
XM_APP_URL = os.environ.get("XM_APP_URL", "https://www.xm.com/mt5")

# Kotak Neo order defaults, editable on the confirmation page before submitting.
KOTAK_NEO_DEFAULT_QTY    = os.environ.get("KOTAK_NEO_DEFAULT_QTY", "1")
KOTAK_NEO_DEFAULT_SYMBOL = os.environ.get("KOTAK_NEO_DEFAULT_SYMBOL", "")

# Delta Exchange order defaults, editable on the confirmation page before submitting.
DELTA_DEFAULT_QTY    = os.environ.get("DELTA_DEFAULT_QTY", "1")
DELTA_DEFAULT_SYMBOL = os.environ.get("DELTA_DEFAULT_SYMBOL", "")

# Per-broker config driving the confirm page + place() dispatch. Each entry needs a
# client module exposing place_order(...) -> {"ok","dry_run","error","summary"} and
# a LIVE_TRADING attribute, plus a lambda adapting webhook_bot's generic call to
# whatever kwarg name that module's place_order() uses for the symbol.
BROKERS = {
    "kotak": {
        "label": "Kotak Neo",
        "client": kotak_neo_client,
        "default_symbol": KOTAK_NEO_DEFAULT_SYMBOL,
        "default_qty": KOTAK_NEO_DEFAULT_QTY,
        "symbol_hint": "Kotak Neo Trading Symbol (check contract/expiry!)",
        "place": lambda symbol, side, qty: kotak_neo_client.place_order(trading_symbol=symbol, side=side, quantity=qty),
    },
    "delta": {
        "label": "Delta Exchange",
        "client": delta_exchange_client,
        "default_symbol": DELTA_DEFAULT_SYMBOL,
        "default_qty": DELTA_DEFAULT_QTY,
        "symbol_hint": "Delta Exchange Symbol (e.g. BTCUSD, ETHUSD — check gold contract naming!)",
        "place": lambda symbol, side, qty: delta_exchange_client.place_order(symbol=symbol, side=side, quantity=qty),
    },
}

# Confirmation links expire after this long — an entry price from 10+ minutes ago
# is stale and shouldn't be one-tap-executable.
TOKEN_TTL_SEC = 600

# In-memory pending-order store: token -> {symbol, side, entry, sl, tp1, tp2, tp3,
# created, used}. NOTE: this only works correctly if the app runs as a single
# process (the Render start command `python webhook_bot.py` — do NOT switch to a
# multi-worker gunicorn setup, or confirm/place requests can land on a worker that
# never saw the original alert).
PENDING_ORDERS = {}

ENTRY_RE = re.compile(
    r'^(?P<symbol>\S+)\s+(?P<side>LONG|SHORT)\s+entry\s*@\s*(?P<entry>[\d.]+)\s*\|\s*'
    r'SL\s*(?P<sl>[\d.]+)\s*\|\s*TP1\s*(?P<tp1>[\d.]+)\s*\|\s*TP2\s*(?P<tp2>[\d.]+)\s*\|\s*TP3\s*(?P<tp3>[\d.]+)',
    re.IGNORECASE,
)


def parse_entry_signal(text: str):
    """Returns a dict for LONG/SHORT entry alerts (the ones worth a 'place order'
    button), or None for everything else (TP hits, SL hits, sweep alerts, etc.)."""
    m = ENTRY_RE.match(text.strip())
    if not m:
        return None
    d = m.groupdict()
    d["side"] = d["side"].upper()
    return d


def create_pending_order(parsed: dict) -> str:
    token = secrets.token_urlsafe(16)
    # "used" is tracked per-broker (not one flag for the whole token): the same
    # signal can legitimately be placed on Kotak AND Delta independently — they're
    # separate accounts/separate money. Placing via one must not lock out the other.
    PENDING_ORDERS[token] = {**parsed, "created": time.time(), "used": {b: False for b in BROKERS}}
    _cleanup_expired()
    return token


def _cleanup_expired():
    """Purge tokens well past their expiry so this dict doesn't grow forever."""
    cutoff = time.time() - (TOKEN_TTL_SEC * 3)
    for k in [k for k, v in PENDING_ORDERS.items() if v["created"] < cutoff]:
        PENDING_ORDERS.pop(k, None)


def build_keyboard(token: str, base_url: str) -> dict:
    base_url = base_url.rstrip("/")
    rows = [[{"text": f"🟢 Review & Place ({cfg['label']})", "url": f"{base_url}/confirm/{broker}/{token}"}]
            for broker, cfg in BROKERS.items()]
    rows.append([{"text": "📱 Open XM App", "url": XM_APP_URL}])
    return {"inline_keyboard": rows}


def extract_payload(req):
    """Return (secret, text) from a TradingView request, tolerating:
    - application/json bodies (the normal alert() case)
    - text/plain bodies that still contain valid JSON (content-type quirk)
    - double-wrapped JSON (message box re-wrapped an alert() that already sent JSON)
    - a secret passed in the URL query string (?secret=...) or X-Webhook-Secret header
    """
    raw = req.get_data(as_text=True) or ""

    # 1) Try normal JSON parsing regardless of content-type header.
    data = req.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            data = {}

    # 2) Handle the double-wrap case: text itself is another JSON object with a secret.
    inner_text = data.get("text") or data.get("message")
    if isinstance(inner_text, str) and inner_text.strip().startswith("{"):
        try:
            inner = json.loads(inner_text)
            if isinstance(inner, dict):
                data.setdefault("secret", inner.get("secret"))
                inner_text = inner.get("text") or inner.get("message") or inner_text
        except ValueError:
            pass

    # 3) Secret can also come from the URL (?secret=) or a header — most robust fallback.
    secret = data.get("secret")
    if secret is None:
        secret = req.args.get("secret")
    if secret is None:
        secret = req.headers.get("X-Webhook-Secret")

    text = inner_text or data.get("text") or data.get("message") or raw
    return (secret.strip() if isinstance(secret, str) else secret), text


def send_telegram(text: str, reply_markup: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(url, json=payload, timeout=10)
    return r.json()


def format_message(raw: str) -> str:
    lower = raw.lower()
    if "long entry" in lower:
        emoji = "🟢 *LONG SIGNAL*"
    elif "short entry" in lower:
        emoji = "🔴 *SHORT SIGNAL*"
    elif "tp1" in lower:
        emoji = "✅ *TP1 HIT*"
    elif "tp2" in lower:
        emoji = "✅ *TP2 HIT*"
    elif "tp3" in lower:
        emoji = "🎯 *TP3 HIT*"
    elif "stop hit" in lower or "sl hit" in lower:
        emoji = "🛑 *STOP LOSS*"
    elif "trail exit" in lower:
        emoji = "🟡 *TRAIL EXIT*"
    else:
        emoji = "📊 *Alert*"
    # Triple backticks (code block), not single (inline code span) — the auto-trade
    # summary appended for BTC/ETH/SOL entries is multi-line, and Telegram's legacy
    # Markdown parser isn't reliable with a newline inside single-backtick inline code
    # (send would silently fail with a 400 "can't parse entities" in that case).
    return f"{emoji}\n\n```\n{raw}\n```"


# ------------------------- Confirmation page rendering -------------------------

PAGE_CSS = """
body{background:#0f1115;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
     max-width:480px;margin:0 auto;padding:24px 16px}
h1{font-size:1.3rem}
.banner{padding:10px 14px;border-radius:8px;margin-bottom:18px;font-weight:600}
.dry{background:#173d2b;color:#7CFC9C}
.live{background:#3d1717;color:#ff8080}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #262a33}
.row span:first-child{color:#9aa0ab}
label{display:block;margin:16px 0 6px;color:#9aa0ab;font-size:.9rem}
input{width:100%;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid #333a45;
      background:#1a1d24;color:#fff;font-size:1rem}
button{width:100%;margin-top:22px;padding:14px;border:none;border-radius:8px;font-size:1.05rem;
       font-weight:700;background:#2f7d46;color:#fff}
button:active{opacity:.85}
.warn{font-size:.8rem;color:#9aa0ab;margin-top:14px;line-height:1.4}
"""


def render_status_page(title: str, body: str, ok: bool) -> str:
    color = "#7CFC9C" if ok else "#ff8080"
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head>
<body><h1 style="color:{color}">{html.escape(title)}</h1><p>{html.escape(body)}</p></body></html>"""


def render_confirm_form(broker: str, token: str, order: dict) -> str:
    cfg = BROKERS[broker]
    action = "BUY" if order["side"] == "LONG" else "SELL"
    live = cfg["client"].LIVE_TRADING
    banner = (f'<div class="banner live">🔴 LIVE — this places a REAL order on {html.escape(cfg["label"])}</div>'
              if live else
              '<div class="banner dry">🟢 DRY RUN — safe test mode, no real order will be sent</div>')
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Confirm {html.escape(order['symbol'])} {html.escape(action)} — {html.escape(cfg['label'])}</title><style>{PAGE_CSS}</style></head>
<body>
{banner}
<h1>{html.escape(order['symbol'])} — {html.escape(action)} <small>({html.escape(cfg['label'])})</small></h1>
<div class="row"><span>Signal Entry</span><span>{html.escape(order['entry'])}</span></div>
<div class="row"><span>SL</span><span>{html.escape(order['sl'])}</span></div>
<div class="row"><span>TP1 / TP2 / TP3</span><span>{html.escape(order['tp1'])} / {html.escape(order['tp2'])} / {html.escape(order['tp3'])}</span></div>
<form method="POST" action="/place/{html.escape(broker)}/{html.escape(token)}">
  <label for="order_symbol">{html.escape(cfg['symbol_hint'])}</label>
  <input id="order_symbol" name="order_symbol" required value="{html.escape(cfg['default_symbol'])}">
  <label for="quantity">Quantity {'(lots)' if broker == 'kotak' else '(contracts)'}</label>
  <input id="quantity" name="quantity" type="number" min="1" step="1" required value="{html.escape(cfg['default_qty'])}">
  <button type="submit">Confirm &amp; Place {html.escape(action)} Order</button>
</form>
<p class="warn">This sends a plain market entry only — SL/TP1/TP2/TP3 are NOT sent to the
broker. Manage exits manually off the levels above, exactly as before. Double-check the
symbol matches the current contract/pair before confirming — the indicator's symbol name
does not always match {html.escape(cfg['label'])}'s exact contract code.</p>
</body></html>"""


# ------------------------- Routes -------------------------

@app.route("/", methods=["GET"])
def health():
    return "TradingView → Telegram bot is running.", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_body = request.get_data(as_text=True) or ""
    received_secret, text = extract_payload(request)

    print("=" * 60)
    print(f"[webhook] content-type: {request.content_type!r}")
    print(f"[webhook] raw body: {raw_body}")
    print(f"[webhook] received secret: {received_secret!r}")
    print(f"[webhook] server secret:   {WEBHOOK_SECRET!r}")
    print(f"[webhook] match: {received_secret == WEBHOOK_SECRET}")
    print("=" * 60)

    if received_secret != WEBHOOK_SECRET:
        return jsonify({
            "error": "unauthorized",
            "hint": "secret did not match WEBHOOK_SECRET. Check: (1) Render env var value, "
                    "(2) not double-wrapping alert() JSON in the TradingView message box, "
                    "(3) you can also pass ?secret=... in the webhook URL.",
            "received": received_secret,
            "received_is_none": received_secret is None,
            "expected_length": len(WEBHOOK_SECRET),
        }), 401

    clean_text = (text or "").strip()
    if not clean_text:
        return jsonify({"error": "empty message"}), 400

    reply_markup = None
    display_text = clean_text
    parsed = parse_entry_signal(clean_text)
    if parsed:
        auto_symbol = delta_exchange_client.match_auto_symbol(parsed["symbol"])
        if auto_symbol and delta_exchange_client.AUTO_TRADE_ENABLED:
            # BTC/ETH/SOL: no confirm button — fire the order now, report the outcome after.
            side = "BUY" if parsed["side"] == "LONG" else "SELL"
            # SL/TP come straight from the alert (already computed by the Pine script).
            # TP tier is configurable (DELTA_BRACKET_TP_TIER, default tp1) — whichever
            # price is used, the position exits 100% there, not the strategy's tiered
            # 50/30/20 split (see auto_place_order()'s docstring for why).
            try:
                sl_price = float(parsed["sl"])
            except (KeyError, TypeError, ValueError):
                sl_price = None
            try:
                tp_price = float(parsed.get(delta_exchange_client.BRACKET_TP_TIER, parsed.get("tp1")))
            except (TypeError, ValueError):
                tp_price = None
            # entry price drives the marketable-limit slippage cap (see auto_place_order).
            try:
                entry_price = float(parsed["entry"])
            except (KeyError, TypeError, ValueError):
                entry_price = None
            auto_result = delta_exchange_client.auto_place_order(
                auto_symbol, side, sl=sl_price, tp=tp_price, entry=entry_price)
            if auto_result["dry_run"]:
                tag = "🤖 DRY RUN (auto-trade)"
            elif auto_result["ok"]:
                tag = "🤖 AUTO-EXECUTED"
            else:
                tag = "🤖 AUTO-TRADE FAILED"
            display_text = f"{clean_text}\n\n{tag}: {auto_result['summary']}"
        else:
            token = create_pending_order(parsed)
            base_url = PUBLIC_BASE_URL or request.url_root
            reply_markup = build_keyboard(token, base_url)

    result = send_telegram(format_message(display_text), reply_markup)
    return jsonify({"ok": result.get("ok", False), "telegram": result}), 200


@app.route("/confirm/<broker>/<token>", methods=["GET"])
def confirm(broker, token):
    if broker not in BROKERS:
        return render_status_page("Unknown broker", f"'{broker}' is not a supported broker.", ok=False), 404
    order = PENDING_ORDERS.get(token)
    if not order:
        return render_status_page(
            "Link not found",
            "This confirmation link is invalid, already cleaned up, or the server restarted "
            "since the alert fired. Wait for the next signal.", ok=False), 404
    if order["used"].get(broker):
        return render_status_page(
            "Already placed",
            f"This {order['side']} {order['symbol']} order was already submitted via {BROKERS[broker]['label']}. "
            "Check your broker for its status.", ok=True)
    if time.time() - order["created"] > TOKEN_TTL_SEC:
        return render_status_page(
            "Signal expired",
            "This signal is more than 10 minutes old — price has likely moved. "
            "Go back to the chart for a fresh signal.", ok=False), 410
    return Response(render_confirm_form(broker, token, order), mimetype="text/html")


@app.route("/place/<broker>/<token>", methods=["POST"])
def place(broker, token):
    if broker not in BROKERS:
        return render_status_page("Unknown broker", f"'{broker}' is not a supported broker.", ok=False), 404
    order = PENDING_ORDERS.get(token)
    if not order:
        return render_status_page("Link not found", "This confirmation link is invalid or expired.", ok=False), 404
    if order["used"].get(broker):
        return render_status_page("Already placed", f"This order was already submitted via {BROKERS[broker]['label']} — not sending it twice.", ok=True)
    if time.time() - order["created"] > TOKEN_TTL_SEC:
        return render_status_page(
            "Signal expired",
            "This signal is more than 10 minutes old. Go back to the chart for a fresh signal.", ok=False), 410

    qty_raw = (request.form.get("quantity") or "").strip()
    order_symbol = (request.form.get("order_symbol") or "").strip()
    if not qty_raw.isdigit() or int(qty_raw) < 1:
        return render_status_page("Invalid quantity", "Quantity must be a whole number of 1 or more.", ok=False), 400
    if not order_symbol:
        return render_status_page("Missing symbol", "Enter the broker's trading symbol before confirming.", ok=False), 400

    side = "BUY" if order["side"] == "LONG" else "SELL"
    result = BROKERS[broker]["place"](order_symbol, side, int(qty_raw))

    if result["ok"]:
        order["used"][broker] = True  # single-use for THIS broker only — the other broker's button stays live
        title = "✅ Dry run complete" if result["dry_run"] else "✅ Order placed"
        return render_status_page(title, result["summary"], ok=True)
    else:
        # Leave used[broker]=False on failure so a fixed retry (e.g. corrected symbol) can reuse this link.
        return render_status_page("❌ Order failed", result.get("error") or result["summary"], ok=False), 502


@app.route("/debug", methods=["GET"])
def debug():
    return jsonify({
        "telegram_token_set": bool(TELEGRAM_BOT_TOKEN) and TELEGRAM_BOT_TOKEN != "PASTE_YOUR_BOT_TOKEN_HERE",
        "chat_id_set": bool(TELEGRAM_CHAT_ID) and TELEGRAM_CHAT_ID != "PASTE_YOUR_CHAT_ID_HERE",
        "webhook_secret_set": WEBHOOK_SECRET != "change-me-to-random-string",
        "webhook_secret_length": len(WEBHOOK_SECRET),
        "webhook_secret_preview": WEBHOOK_SECRET[:3] + "..." + WEBHOOK_SECRET[-2:] if len(WEBHOOK_SECRET) > 5 else "TOO_SHORT",
        "public_base_url_set": bool(PUBLIC_BASE_URL),
        "kotak_neo_live_trading": kotak_neo_client.LIVE_TRADING,
        "delta_exchange_live_trading": delta_exchange_client.LIVE_TRADING,
        "delta_auto_trade_crypto_enabled": delta_exchange_client.AUTO_TRADE_ENABLED,
        "delta_auto_trade_capital_pct": delta_exchange_client.CAPITAL_PCT,
        "delta_auto_trade_leverage": delta_exchange_client.DEFAULT_LEVERAGE,
        "delta_api_key_set": bool(delta_exchange_client.API_KEY) and bool(delta_exchange_client.API_SECRET),
        "delta_base_url": delta_exchange_client.BASE_URL,
        "pending_orders_in_memory": len(PENDING_ORDERS),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
