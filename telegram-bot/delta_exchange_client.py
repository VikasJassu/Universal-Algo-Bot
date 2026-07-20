"""
Delta Exchange (India) API client — thin wrapper around Delta's REST API.
Docs: https://docs.delta.exchange/  (India endpoint: https://api.india.delta.exchange)

SAFETY: shares the same LIVE_TRADING kill switch as kotak_neo_client.py — until
LIVE_TRADING=true, place_order() never signs or sends a request to Delta's
servers; it just returns a dry-run summary of what would have been sent.

Required env vars (only checked/used when LIVE_TRADING=true):
  DELTA_API_KEY     - from Delta Exchange India -> Account -> API Keys
  DELTA_API_SECRET  - shown once when the key is created; store it securely

Optional:
  DELTA_BASE_URL    (default "https://api.india.delta.exchange")
  DELTA_ORDER_TYPE  (default "market_order"; other option "limit_order")

Auto-trade (BTC/ETH/SOL only, no manual confirm — see the AUTO-TRADE section below):
  DELTA_AUTO_TRADE_CRYPTO  (default "true")
  DELTA_CAPITAL_PCT        (default "15" — percent of balance used as margin, per symbol)
  DELTA_LEVERAGE_BTC       (default "200")
  DELTA_LEVERAGE_ETH       (default "200")
  DELTA_LEVERAGE_SOL       (default "100" — Delta's actual max for SOLUSD)
  DELTA_BRACKET_TP_TIER    (default "tp1" — which of the alert's tp1/tp2/tp3 to attach
                             as the take-profit; position exits 100% there, not tiered)
  DELTA_BRACKET_TRIGGER    (default "mark_price" — confirmed by inspecting a real
                             request from Delta's own web UI; NOT "last_traded_price",
                             which was an earlier guess from ambiguous docs)

Note on architecture: entry + bracket SL/TP are placed together in ONE call to
POST /v2/orders (market_order, product_id, bare bracket_stop_loss_price /
bracket_take_profit_price with NO *_limit_price sub-fields, mark_price trigger,
explicit reduce_only) — this exact field structure was copied from a real request
captured from Delta's own web UI placing a bracket order, after two earlier guesses
(order_type="limit_order"; then a separate follow-up call to Delta's dedicated
/v2/orders/bracket endpoint) both failed to actually attach the SL/TP. Every bracketed
auto-trade is still followed by verify_bracket_orders(), an independent GET check that
the SL/TP orders actually exist — this doesn't trust the order call's own success flag,
regardless of how confident the field structure now is.
"""
import hashlib
import hmac
import json
import os
import time

import requests

LIVE_TRADING = os.environ.get("LIVE_TRADING", "false").strip().lower() == "true"

API_KEY    = os.environ.get("DELTA_API_KEY", "")
API_SECRET = os.environ.get("DELTA_API_SECRET", "")
BASE_URL   = os.environ.get("DELTA_BASE_URL", "https://api.india.delta.exchange").rstrip("/")


def _sign(method: str, path: str, query: str, body: str):
    """Delta's prehash string is: method + timestamp + requestPath + query + body,
    HMAC-SHA256'd with the API secret. Signatures older than 5s are rejected by
    Delta's servers, so this must be called right before the request is sent."""
    timestamp = str(int(time.time()))
    prehash = method + timestamp + path + query + body
    signature = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return timestamp, signature


def _headers(method: str, path: str, query: str, body: str) -> dict:
    timestamp, signature = _sign(method, path, query, body)
    return {
        "api-key": API_KEY,
        "signature": signature,
        "timestamp": timestamp,
        "User-Agent": "gold-algo-webhook-bot/1.0",
        "Content-Type": "application/json",
    }


def place_order(symbol: str, side: str, quantity: int, order_type: str = None,
                 limit_price: float = None, product_id=None, reduce_only: bool = False,
                 stop_loss_price: float = None, take_profit_price: float = None) -> dict:
    """
    side: "BUY" or "SELL" — map LONG->BUY, SHORT->SELL before calling this.
    quantity: number of contracts (Delta calls this "size").
    symbol: Delta's product_symbol (e.g. "BTCUSD" for the perpetual). Used only if
            product_id isn't given — pass product_id when you have it (auto_place_order
            already looked it up), it's what a confirmed-working request actually used.
    product_id: preferred over symbol when available (see above).
    limit_price: only used when order_type="limit_order" — otherwise ignored.
    reduce_only: True for closing/reducing orders, False (default) for a fresh entry.
    stop_loss_price / take_profit_price: optional absolute prices, attached as flat
    bracket_* fields on THIS SAME call — confirmed to work this way by inspecting a
    real request captured from Delta's own web UI placing a bracket order: bare
    bracket_stop_loss_price/bracket_take_profit_price (no *_limit_price sub-fields at
    all), bracket_stop_trigger_method="mark_price", order_type="market_order",
    product_id (not product_symbol), explicit reduce_only. Two earlier guesses both
    failed to actually attach the bracket: first switching to order_type="limit_order"
    (based on ambiguous docs), then splitting into a separate follow-up call to
    Delta's dedicated bracket endpoint — neither was the actual problem; the field
    structure now matches what Delta's own UI sends, verbatim.

    Returns: {"ok": bool, "dry_run": bool, "raw": <api response or None>,
              "error": <str or None>, "summary": <human-readable str>}
    """
    order_type = order_type or os.environ.get("DELTA_ORDER_TYPE", "market_order")
    delta_side = "buy" if side.upper() == "BUY" else "sell"
    trigger_method = os.environ.get("DELTA_BRACKET_TRIGGER", "mark_price")

    bracket_desc = ""
    if stop_loss_price is not None:
        bracket_desc += f" | SL {stop_loss_price}"
    if take_profit_price is not None:
        bracket_desc += f" | TP {take_profit_price}"

    if not LIVE_TRADING:
        summary = (f"[DRY RUN] Would place {delta_side} {quantity} x {symbol} "
                   f"({order_type}){bracket_desc} on Delta Exchange. Set LIVE_TRADING=true on Render to go live.")
        return {"ok": True, "dry_run": True, "raw": None, "error": None, "summary": summary}

    if not API_KEY or not API_SECRET:
        err = "Missing DELTA_API_KEY / DELTA_API_SECRET env vars."
        return {"ok": False, "dry_run": False, "raw": None, "error": err, "summary": err}

    path = "/v2/orders"
    # Field structure below was corrected to match a real captured request from Delta's
    # own web UI placing a market entry + bracket SL/TP in one call (bare
    # bracket_stop_loss_price/bracket_take_profit_price, NO *_limit_price sub-fields,
    # trigger method "mark_price", product_id rather than product_symbol, explicit
    # reduce_only) — this is authoritative, not a docs-page guess like the previous two
    # attempts (order_type="limit_order", then splitting into two separate calls) that
    # both failed to actually attach the bracket.
    body_obj = {
        "size": int(quantity),
        "side": delta_side,
        "order_type": order_type,
        "reduce_only": "true" if reduce_only else "false",
    }
    if product_id is not None:
        body_obj["product_id"] = product_id
    else:
        body_obj["product_symbol"] = symbol

    if order_type == "limit_order" and limit_price is not None:
        body_obj["limit_price"] = str(limit_price)

    if stop_loss_price is not None:
        body_obj["bracket_stop_loss_price"] = str(stop_loss_price)
    if take_profit_price is not None:
        body_obj["bracket_take_profit_price"] = str(take_profit_price)
    if stop_loss_price is not None or take_profit_price is not None:
        body_obj["bracket_stop_trigger_method"] = trigger_method

    body = json.dumps(body_obj, separators=(",", ":"))
    headers = _headers("POST", path, "", body)

    try:
        resp = requests.post(f"{BASE_URL}{path}", data=body, headers=headers, timeout=10)
        data = resp.json()
        ok = bool(data.get("success"))
        summary = (f"{delta_side} {quantity} x {symbol}{bracket_desc} submitted to Delta Exchange."
                   if ok else f"Delta Exchange rejected the order: {data}")
        return {"ok": ok, "dry_run": False, "raw": data, "error": None if ok else str(data), "summary": summary}
    except Exception as e:
        return {"ok": False, "dry_run": False, "raw": None, "error": str(e), "summary": f"Order failed: {e}"}


# ============================================================
# AUTO-TRADE: BTC / ETH / SOL only — no manual confirm tap.
#
# Triggered directly from webhook_bot.py the instant an entry alert for one of these
# three arrives. Position size = DELTA_CAPITAL_PCT of current wallet balance (default
# 15%), used as MARGIN, independently PER SYMBOL — so BTC, ETH, and SOL can each use
# their own 15% slice of balance (up to 45% combined exposure if all three fire close
# together). Leverage is set automatically per symbol before the order is placed.
#
# ⚠️ LEVERAGE — EXPLICITLY CONFIRMED, NOT A DEFAULT TO TRUST BLINDLY:
# BTCUSD/ETHUSD default to 200x (Delta's max), SOLUSD to 100x (Delta's actual max for
# that product — 200x isn't offered there). At 200x, Delta's forced liquidation
# triggers at roughly a 0.5% adverse price move, well inside normal 5-minute BTC/ETH
# candle ranges. In practice this means the EXCHANGE's liquidation engine, not the
# indicator's own ATR-based stop-loss, decides the exit on most losing trades —
# consuming the full margin allocated to that symbol rather than the smaller loss the
# strategy's SL was sized for. This was surfaced explicitly and confirmed as intended.
# Change DELTA_LEVERAGE_BTC / DELTA_LEVERAGE_ETH / DELTA_LEVERAGE_SOL to lower it.
#
# ⚠️ FIELD NAMES: the wallet-balance and ticker response shapes below are built from
# Delta's docs + published Python SDK examples, but were NOT verified against a live
# response at build time (the docs page didn't fully render those exact JSON bodies).
# Test against Delta's TESTNET first — set DELTA_BASE_URL=https://cdn-ind.testnet.deltaex.org
# with a testnet-only API key/secret and LIVE_TRADING=true — and confirm the computed
# balance/size numbers look right BEFORE pointing this at the real account.
#
# NOT covered: exit management. TP1/TP2/TP3/SL-hit alerts are NOT auto-executed here —
# only entries. Exits still require manual action on Delta's app, same as before.
# ============================================================

AUTO_CRYPTO_SYMBOLS = {"BTC": "BTCUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}

AUTO_TRADE_ENABLED = os.environ.get("DELTA_AUTO_TRADE_CRYPTO", "true").strip().lower() == "true"
CAPITAL_PCT = float(os.environ.get("DELTA_CAPITAL_PCT", "15"))

DEFAULT_LEVERAGE = {
    "BTCUSD": int(os.environ.get("DELTA_LEVERAGE_BTC", "200")),
    "ETHUSD": int(os.environ.get("DELTA_LEVERAGE_ETH", "200")),
    "SOLUSD": int(os.environ.get("DELTA_LEVERAGE_SOL", "100")),
}

# Which of the alert's tp1/tp2/tp3 to attach as the bracket take-profit — the position
# closes 100% there, not tiered. "tp1" (closest, highest hit-probability) is the safer
# default given the leverage in play; webhook_bot.py resolves this into an actual price
# before calling auto_place_order().
BRACKET_TP_TIER = os.environ.get("DELTA_BRACKET_TP_TIER", "tp1").strip().lower()


def match_auto_symbol(raw_ticker: str):
    """Returns the Delta product symbol (BTCUSD/ETHUSD/SOLUSD) if raw_ticker names one
    of the auto-trade assets (e.g. TradingView's "BTCUSD", "BINANCE:BTCUSDT.P", etc all
    contain "BTC"), else None. BTC/ETH/SOL don't overlap as substrings so check order
    doesn't matter here."""
    if not raw_ticker:
        return None
    t = raw_ticker.upper()
    for key, delta_symbol in AUTO_CRYPTO_SYMBOLS.items():
        if key in t:
            return delta_symbol
    return None


def _get(path: str) -> dict:
    headers = _headers("GET", path, "", "")
    resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=10)
    return resp.json()


def _post(path: str, body_obj: dict) -> dict:
    body = json.dumps(body_obj, separators=(",", ":"))
    headers = _headers("POST", path, "", body)
    resp = requests.post(f"{BASE_URL}{path}", data=body, headers=headers, timeout=10)
    return resp.json()


def get_available_balance_usd() -> float:
    """Delta's crypto perpetuals (BTCUSD/ETHUSD/SOLUSD) are USDT-margined even on the
    India entity (INR is just the UPI deposit rail), so this looks for the USDT wallet
    entry specifically. Raises loudly on any unexpected shape rather than silently
    returning a wrong number — see the TESTNET note above."""
    data = _get("/v2/wallet/balances")
    balances = data.get("result", data) if isinstance(data, dict) else data
    if not isinstance(balances, list):
        raise RuntimeError(f"Unexpected wallet balance response shape: {data}")
    for b in balances:
        asset_symbol = (b.get("asset_symbol") or "").upper()
        if asset_symbol in ("USDT", "USD"):
            bal = b.get("available_balance", b.get("balance"))
            if bal is not None:
                return float(bal)
    raise RuntimeError(f"Could not find a USDT/USD balance entry in wallet response: {balances}")


def get_product_info(delta_symbol: str) -> dict:
    data = _get(f"/v2/products/{delta_symbol}")
    product = data.get("result", data) if isinstance(data, dict) else data
    if not isinstance(product, dict) or "id" not in product:
        raise RuntimeError(f"Unexpected product response for {delta_symbol}: {data}")
    return product


def set_leverage(product_id, leverage: int) -> dict:
    """Raises if Delta doesn't confirm the leverage change — previously this response
    was discarded, so a failed/ignored leverage change went unnoticed and the margin
    math below proceeded as if the requested leverage had actually been applied. That
    produced exactly this failure mode: sized for 200x, but Delta's own margin
    requirement reflected whatever leverage was ACTUALLY in effect (which the
    "insufficient_margin" error's numbers suggest was closer to 5x), so the order was
    undersized for the leverage Delta really used and got rejected."""
    resp = _post(f"/v2/products/{product_id}/orders/leverage", {"leverage": leverage})
    if not (isinstance(resp, dict) and resp.get("success")):
        raise RuntimeError(f"Delta did not confirm {leverage}x leverage on product {product_id}: {resp}")
    return resp


def get_mark_price(delta_symbol: str) -> float:
    data = _get(f"/v2/tickers/{delta_symbol}")
    ticker = data.get("result", data) if isinstance(data, dict) else data
    price = ticker.get("mark_price", ticker.get("close", ticker.get("last_price")))
    if price is None:
        raise RuntimeError(f"Unexpected ticker response for {delta_symbol}: {data}")
    return float(price)


def verify_bracket_orders(product_id, expect_sl: bool, expect_tp: bool) -> dict:
    """Queries Delta's open orders for this product right after placing a bracketed
    entry, to actually CONFIRM the stop-loss/take-profit orders exist rather than
    trusting the entry order's success=true — this is a direct response to the entry
    succeeding once while the bracket legs silently never attached (root cause: was
    using order_type="market_order", now fixed to "limit_order", but this check stays
    as a permanent safety net regardless of the underlying reason).

    Returns {"verified": bool, "missing": [...], "open_orders_count": int} — or
    {"verified": False, "reason": <str>} if the open-orders lookup itself failed.
    """
    try:
        data = _get(f"/v2/orders?product_ids={product_id}&states=open")
    except Exception as e:
        return {"verified": False, "missing": [], "reason": f"Could not verify — open-orders lookup failed: {e}"}

    orders = data.get("result", data) if isinstance(data, dict) else data
    if not isinstance(orders, list):
        return {"verified": False, "missing": [], "reason": f"Unexpected open-orders response: {data}"}

    stop_order_types = {o.get("stop_order_type") for o in orders if isinstance(o, dict)}
    has_sl = "stop_loss_order" in stop_order_types
    has_tp = "take_profit_order" in stop_order_types

    missing = []
    if expect_sl and not has_sl:
        missing.append("stop-loss")
    if expect_tp and not has_tp:
        missing.append("take-profit")

    return {"verified": not missing, "missing": missing, "open_orders_count": len(orders)}


def auto_place_order(delta_symbol: str, side: str, sl: float = None, tp: float = None) -> dict:
    """Full auto-size + auto-place flow, no manual confirm — called directly from the
    webhook handler the instant a BTC/ETH/SOL entry alert arrives.

    side: "BUY" or "SELL"
    sl: stop-loss price from the alert (structure ± ATR buffer, as computed by the
        Pine script). Attached as a bracket field on the SAME entry call to place_order()
        — see that function's docstring for the exact field structure, copied from a
        real request captured from Delta's own web UI after two earlier guesses failed.
    tp: take-profit price. Defaults to the alert's TP1 unless DELTA_BRACKET_TP_TIER
        overrides which tier to use (tp1/tp2/tp3 — passed in by the caller already
        resolved, this function just attaches whatever price it's given). Since it's
        sized for the FULL position, hitting it closes the entire trade — this directly
        satisfies "close on TP1" once the bracket actually attaches (verified below).

    ⚠️ This places ONE stop-loss and ONE take-profit for the FULL position size — it
    does NOT replicate the Pine script's tiered 50%/30%/20% partial exits (TP1/TP2/
    TP3). The position closes 100% at whichever single TP price is passed in. Splitting
    into three separate brackets (one per tier) with a shared SL, plus dynamically
    moving that SL to breakeven when a TP1-hit alert later arrives, is a separate,
    materially bigger feature — ask for it explicitly if you want true tiered parity.

    Returns the same shape as place_order(): {"ok","dry_run","raw","error","summary"}.
    """
    leverage = DEFAULT_LEVERAGE.get(delta_symbol, 50)
    bracket_desc = ""
    if sl is not None:
        bracket_desc += f" | SL {sl}"
    if tp is not None:
        bracket_desc += f" | TP {tp} (100% exit, not tiered)"

    if not LIVE_TRADING:
        # Dry run makes zero external API calls (same policy as place_order) — so this
        # can't validate the sizing math end-to-end. Use Delta's testnet for that.
        summary = (f"[DRY RUN] Would auto-place {side} on {delta_symbol} using "
                   f"{CAPITAL_PCT}% of balance as margin at {leverage}x leverage{bracket_desc}. "
                   f"Set LIVE_TRADING=true (ideally against testnet first) to see real numbers.")
        return {"ok": True, "dry_run": True, "raw": None, "error": None, "summary": summary}

    if not API_KEY or not API_SECRET:
        err = "Missing DELTA_API_KEY / DELTA_API_SECRET env vars."
        return {"ok": False, "dry_run": False, "raw": None, "error": err, "summary": err}

    try:
        balance = get_available_balance_usd()
        product = get_product_info(delta_symbol)
        product_id = product["id"]
        contract_value = float(product.get("contract_value") or 0)
        if contract_value <= 0:
            raise RuntimeError(f"Invalid contract_value for {delta_symbol}: {product}")

        set_leverage(product_id, leverage)

        mark_price = get_mark_price(delta_symbol)
        margin = balance * (CAPITAL_PCT / 100)
        notional = margin * leverage
        contracts = int(notional / mark_price / contract_value)

        if contracts < 1:
            err = (f"Computed size < 1 contract for {delta_symbol} (balance=${balance:.2f}, "
                   f"margin=${margin:.2f}, leverage={leverage}x, notional=${notional:.2f}, "
                   f"price=${mark_price}, contract_value={contract_value}) — trade skipped.")
            return {"ok": False, "dry_run": False, "raw": None, "error": err, "summary": err}

        # Single call: entry + bracket SL/TP attached together, matching a real request
        # captured from Delta's own web UI (market_order, product_id, bare
        # bracket_stop_loss_price/bracket_take_profit_price, mark_price trigger). Two
        # earlier guesses at the field structure (limit_order entry; then a separate
        # follow-up call to the dedicated bracket endpoint) both failed to actually
        # attach the bracket — this one is copied from a proven-working request, not
        # inferred from docs.
        result = place_order(symbol=delta_symbol, side=side, quantity=contracts,
                              order_type="market_order", product_id=product_id, reduce_only=False,
                              stop_loss_price=sl, take_profit_price=tp)
        prefix = (f"AUTO {side.upper()} {contracts} x {delta_symbol} @ ~${mark_price:.2f} | "
                  f"margin ${margin:.2f} ({CAPITAL_PCT:.0f}% of ${balance:.2f} balance) "
                  f"@ {leverage}x = ${notional:.2f} notional{bracket_desc}. ")
        result["summary"] = prefix + result.get("summary", "")

        if not result["ok"]:
            return result  # entry (with bracket) failed outright — nothing opened

        # Still don't trust success=true blindly for the bracket legs specifically —
        # confirm they actually exist. This is the permanent safety net for exactly
        # what happened before: the entry reports fine while protection silently isn't
        # there. Now backed by a proven-correct request structure, but kept regardless.
        if sl is not None or tp is not None:
            check = verify_bracket_orders(product_id, expect_sl=sl is not None, expect_tp=tp is not None)
            if not check["verified"]:
                reasons = list(check.get("missing") or [])
                if check.get("reason"):
                    reasons.append(check["reason"])
                result["summary"] = (
                    f"⚠️⚠️ POSITION OPEN WITHOUT FULL PROTECTION — {'; '.join(reasons)} — "
                    f"CHECK DELTA AND ADD MANUALLY NOW ⚠️⚠️\n" + result["summary"]
                )
                result["bracket_verified"] = False
            else:
                result["bracket_verified"] = True

        return result
    except Exception as e:
        return {"ok": False, "dry_run": False, "raw": None, "error": str(e), "summary": f"Auto-trade failed: {e}"}
