"""
TradingView Webhook → Telegram Bot
Receives POST requests from TradingView alerts and forwards to Telegram.
Requires TradingView Essential plan (webhook alerts).
"""
import os
import json
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "PASTE_YOUR_CHAT_ID_HERE")
WEBHOOK_SECRET     = os.environ.get("WEBHOOK_SECRET",     "change-me-to-random-string").strip()


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


def send_telegram(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
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
    return f"{emoji}\n\n`{raw}`"


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

    if not (text or "").strip():
        return jsonify({"error": "empty message"}), 400

    result = send_telegram(format_message(text.strip()))
    return jsonify({"ok": result.get("ok", False), "telegram": result}), 200


@app.route("/debug", methods=["GET"])
def debug():
    return jsonify({
        "telegram_token_set": bool(TELEGRAM_BOT_TOKEN) and TELEGRAM_BOT_TOKEN != "PASTE_YOUR_BOT_TOKEN_HERE",
        "chat_id_set": bool(TELEGRAM_CHAT_ID) and TELEGRAM_CHAT_ID != "PASTE_YOUR_CHAT_ID_HERE",
        "webhook_secret_set": WEBHOOK_SECRET != "change-me-to-random-string",
        "webhook_secret_length": len(WEBHOOK_SECRET),
        "webhook_secret_preview": WEBHOOK_SECRET[:3] + "..." + WEBHOOK_SECRET[-2:] if len(WEBHOOK_SECRET) > 5 else "TOO_SHORT",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
