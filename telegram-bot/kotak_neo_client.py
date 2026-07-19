"""
Kotak Neo Trade API client — thin wrapper around the official `neo_api_client` SDK.

SAFETY: this module runs in DRY-RUN mode by default (until the LIVE_TRADING env
var is set to exactly "true"). In dry-run mode, place_order() logs what it
*would* send and returns a fake success response — it never contacts Kotak's
servers, never logs in, and never touches real money. Flip LIVE_TRADING=true
only after you've confirmed dry-run summaries look correct.

Required env vars (only checked/used when LIVE_TRADING=true):
  KOTAK_NEO_CONSUMER_KEY  - from Kotak Neo app/web -> Invest -> Trade API -> Create Application
  KOTAK_NEO_MOBILE        - registered mobile number, e.g. "+919999999999"
  KOTAK_NEO_UCC           - your Kotak client code
  KOTAK_NEO_MPIN          - your Neo app login MPIN
  KOTAK_NEO_TOTP_SECRET   - the base32 secret behind the TOTP QR code you scanned
                            into Google/Microsoft Authenticator for Neo login
                            (shown as text when you set up 2FA in the Neo app —
                            NOT the 6-digit code itself, the secret it's generated from)

Optional order defaults (all overridable per-call):
  KOTAK_NEO_EXCHANGE_SEGMENT (default "mcx_fo")
  KOTAK_NEO_PRODUCT          (default "MIS")
  KOTAK_NEO_ORDER_TYPE       (default "MKT")
"""
import os
import time

import pyotp

LIVE_TRADING = os.environ.get("LIVE_TRADING", "false").strip().lower() == "true"

CONSUMER_KEY  = os.environ.get("KOTAK_NEO_CONSUMER_KEY", "")
MOBILE_NUMBER = os.environ.get("KOTAK_NEO_MOBILE", "")
UCC           = os.environ.get("KOTAK_NEO_UCC", "")
MPIN          = os.environ.get("KOTAK_NEO_MPIN", "")
TOTP_SECRET   = os.environ.get("KOTAK_NEO_TOTP_SECRET", "")

# Cached session — re-login periodically rather than on every single order.
_client = None
_client_ts = 0
SESSION_TTL_SEC = 6 * 60 * 60  # 6 hours


def _login():
    """Runs the Neo API's two-step login (TOTP login + MPIN validate). SDK is
    imported lazily here so dry-run mode works even without it installed."""
    try:
        from neo_api_client import NeoAPI
    except ImportError:
        raise RuntimeError(
            "neo_api_client is not installed (left out of requirements.txt by default — "
            "see the comment there for why). To go live with Kotak Neo: bump the requests "
            "pin to ==2.32.3 and add "
            "'git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git@v2.0.2#egg=neo_api_client' "
            "to requirements.txt, then redeploy."
        )

    missing = [name for name, val in [
        ("KOTAK_NEO_CONSUMER_KEY", CONSUMER_KEY),
        ("KOTAK_NEO_MOBILE", MOBILE_NUMBER),
        ("KOTAK_NEO_UCC", UCC),
        ("KOTAK_NEO_MPIN", MPIN),
        ("KOTAK_NEO_TOTP_SECRET", TOTP_SECRET),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing Kotak Neo env var(s): {', '.join(missing)}")

    client = NeoAPI(environment="prod", access_token=None, neo_fin_key=None, consumer_key=CONSUMER_KEY)
    totp_code = pyotp.TOTP(TOTP_SECRET).now()
    client.totp_login(mobile_number=MOBILE_NUMBER, ucc=UCC, totp=totp_code)
    client.totp_validate(mpin=MPIN)
    return client


def _get_client():
    global _client, _client_ts
    if _client is None or (time.time() - _client_ts) > SESSION_TTL_SEC:
        _client = _login()
        _client_ts = time.time()
    return _client


def place_order(trading_symbol: str, side: str, quantity: int,
                 exchange_segment: str = None, product: str = None, order_type: str = None) -> dict:
    """
    side: "BUY" or "SELL" — map LONG->BUY, SHORT->SELL before calling this.

    Only places a plain entry order (no SL/TP attached) — SL/TP1/TP2/TP3 stay
    exactly as the indicator manages them: you exit manually off the levels
    already shown on chart / sent in the Telegram alerts.

    Returns: {"ok": bool, "dry_run": bool, "raw": <sdk response or None>,
              "error": <str or None>, "summary": <human-readable str>}
    """
    exchange_segment = exchange_segment or os.environ.get("KOTAK_NEO_EXCHANGE_SEGMENT", "mcx_fo")
    product          = product          or os.environ.get("KOTAK_NEO_PRODUCT", "MIS")
    order_type       = order_type       or os.environ.get("KOTAK_NEO_ORDER_TYPE", "MKT")
    transaction_type = "B" if side.upper() == "BUY" else "S"

    if not LIVE_TRADING:
        summary = (f"[DRY RUN] Would place {transaction_type} {quantity} x {trading_symbol} "
                   f"({exchange_segment}/{product}/{order_type}). Set LIVE_TRADING=true on Render to go live.")
        return {"ok": True, "dry_run": True, "raw": None, "error": None, "summary": summary}

    try:
        client = _get_client()
        resp = client.place_order(
            exchange_segment=exchange_segment,
            product=product,
            price="0",
            order_type=order_type,
            quantity=str(quantity),
            validity="DAY",
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            amo="NO",
            disclosed_quantity="0",
            market_protection="0",
            pf="N",
            trigger_price="0",
        )
        # Neo API returns {"stat": "Ok", ...} on success, {"stat": "Not_Ok", "errMsg": "..."} on failure.
        ok = isinstance(resp, dict) and str(resp.get("stat", "")).lower() != "not_ok"
        summary = (f"{transaction_type} {quantity} x {trading_symbol} submitted to Kotak Neo."
                   if ok else f"Kotak Neo rejected the order: {resp}")
        return {"ok": ok, "dry_run": False, "raw": resp, "error": None if ok else str(resp), "summary": summary}
    except Exception as e:
        return {"ok": False, "dry_run": False, "raw": None, "error": str(e), "summary": f"Order failed: {e}"}
