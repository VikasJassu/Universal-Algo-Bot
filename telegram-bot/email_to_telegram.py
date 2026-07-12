"""
Email → Telegram bridge (works with TradingView FREE plan)
Polls Gmail for TradingView alert emails, extracts message, forwards to Telegram.

Setup:
1. Enable IMAP in Gmail: https://mail.google.com/mail/u/0/#settings/fwdandpop
2. Create Gmail App Password: https://myaccount.google.com/apppasswords
   (Regular Gmail password will NOT work — you need an app password.)
3. Set env vars or edit constants below.
4. Run: python email_to_telegram.py
"""
import os
import time
import imaplib
import email
from email.header import decode_header
import requests

GMAIL_USER         = os.environ.get("GMAIL_USER", "gauravism2016@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "PASTE_16_CHAR_APP_PASSWORD_HERE")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "PASTE_YOUR_CHAT_ID_HERE")
POLL_INTERVAL_SEC  = int(os.environ.get("POLL_INTERVAL_SEC", 15))
TV_SENDER          = "noreply@tradingview.com"


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[telegram error] {e}")


def format_message(raw: str) -> str:
    lower = raw.lower()
    if "long entry" in lower:
        header = "🟢 *LONG SIGNAL*"
    elif "short entry" in lower:
        header = "🔴 *SHORT SIGNAL*"
    elif "tp1" in lower:
        header = "✅ *TP1 HIT*"
    elif "tp2" in lower:
        header = "✅ *TP2 HIT*"
    elif "tp3" in lower:
        header = "🎯 *TP3 HIT*"
    elif "stop hit" in lower or "sl hit" in lower:
        header = "🛑 *STOP LOSS*"
    elif "trail exit" in lower:
        header = "🟡 *TRAIL EXIT*"
    else:
        header = "📊 *TV Alert*"
    return f"{header}\n\n`{raw[:800]}`"


def extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(errors="ignore")
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(errors="ignore")


def check_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("INBOX")

    status, data = mail.search(None, f'(UNSEEN FROM "{TV_SENDER}")')
    if status != "OK":
        mail.close()
        mail.logout()
        return

    ids = data[0].split()
    for msg_id in ids:
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject_raw = decode_header(msg.get("Subject", ""))[0][0]
        subject = subject_raw.decode() if isinstance(subject_raw, bytes) else subject_raw
        body = extract_body(msg)

        alert_text = ""
        for line in body.splitlines():
            line = line.strip()
            if line and ("@" in line or "TP" in line or "SL" in line or "LONG" in line or "SHORT" in line):
                alert_text = line
                break
        if not alert_text:
            alert_text = subject

        print(f"[alert] {alert_text[:120]}")
        send_telegram(format_message(alert_text))
        mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.close()
    mail.logout()


def main():
    print("Email → Telegram bridge started.")
    print(f"Polling {GMAIL_USER} every {POLL_INTERVAL_SEC}s for TradingView alerts...")
    send_telegram("✅ *Bot connected* — TradingView alerts will now be forwarded here.")
    while True:
        try:
            check_emails()
        except Exception as e:
            print(f"[error] {e}")
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
