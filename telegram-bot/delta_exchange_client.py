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
  DELTA_BRACKET_TP_TIER    (default "tp1" — which of the alert's tp1/tp2/tp3 to use as
                             the take-profit price; position exits 100% there, not tiered)

Note on architecture (rewritten after re-reading Delta's docs + a browser-captured
request from Delta's own UI): SL/TP ARE placed via Delta's native bracket mechanism —
bracket_stop_loss_price / bracket_take_profit_price / bracket_stop_trigger_method on
the market entry (POST /v2/orders), the exact payload Delta's web UI itself sends.

The earlier rounds that "proved" this mechanism broken were misreading two things:
  1. They judged success by the "bracket_order" field on the ENTRY order's response.
     Per Delta's docs, a MARKET entry fills instantly and its SL/TP are created as
     SEPARATE order objects — so "bracket_order" on the (already-filled) entry is
     STRUCTURALLY null. It was never the success signal; it was a red herring.
  2. Their verify step looked for the TP as a plain reduce_only limit order with
     stop_order_type == None, and assumed "take_profit_order" wasn't a real value.
     Delta's docs confirm both "stop_loss_order" AND "take_profit_order" are valid
     stop_order_type values, and that the child legs carry bracket_stop_loss_price /
     bracket_take_profit_price. So a genuinely-placed bracket TP was invisible to the
     old check — hence "proven-correct request still reports missing SL/TP".

Current approach: place the bracket market entry, then verify by GET-ing the child
legs and identifying them by their bracket_* prices / stop_order_type (see
verify_bracket_orders). If the native bracket somehow doesn't materialize, fall back
to the dedicated POST /v2/orders/bracket endpoint against the now-open position, and
only as a last resort to two independent reduce_only orders. verify runs regardless —
we still never trust a lone success=true given this problem's history.
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
                 stop_order_type: str = None, stop_price: float = None) -> dict:
    """
    side: "BUY" or "SELL" — map LONG->BUY, SHORT->SELL before calling this.
    quantity: number of contracts (Delta calls this "size").
    symbol: Delta's product_symbol (e.g. "BTCUSD" for the perpetual). Used only if
            product_id isn't given — pass product_id when you have it (auto_place_order
            already looked it up), it's what a confirmed-working request actually used.
    product_id: preferred over symbol when available (see above).
    limit_price: only used when order_type="limit_order" — otherwise ignored.
    reduce_only: True for closing/reducing orders, False (default) for a fresh entry.
    stop_order_type: pass "stop_loss_order" to make this a real stop order (triggers
    at stop_price, then fills as order_type once triggered) — this field name and
    behavior IS confirmed by Delta's docs, unlike the bracket_* mechanism below.
    stop_price: required alongside stop_order_type — the trigger price.

    ⚠️ Delta's "bracket" mechanism (bracket_stop_loss_price/bracket_take_profit_price
    attached to an entry, or the dedicated /v2/orders/bracket endpoint) was tried in
    THREE different forms and never actually attached a working SL/TP — confirmed by
    inspecting a real order's raw response, which had bracket_stop_loss_price/
    bracket_take_profit_price echoed back but "bracket_order": null (Delta's own field
    for "a bracket got linked to this order") and "stop_order_type": null. So this
    function no longer has any bracket_* support. Protective orders are placed as
    genuinely independent reduce_only orders instead (see auto_place_order()) — a
    stop-market order for SL (stop_order_type="stop_loss_order", confirmed by docs) and
    a plain reduce_only limit order for TP (no Delta-specific mechanism needed at all).

    Returns: {"ok": bool, "dry_run": bool, "raw": <api response or None>,
              "error": <str or None>, "summary": <human-readable str>}
    """
    order_type = order_type or os.environ.get("DELTA_ORDER_TYPE", "market_order")
    delta_side = "buy" if side.upper() == "BUY" else "sell"

    desc = ""
    if stop_order_type is not None:
        desc = f" [{stop_order_type} @ {stop_price}]"
    elif reduce_only:
        desc = f" [reduce-only @ {limit_price}]"

    if not LIVE_TRADING:
        summary = (f"[DRY RUN] Would place {delta_side} {quantity} x {symbol} "
                   f"({order_type}){desc} on Delta Exchange. Set LIVE_TRADING=true on Render to go live.")
        return {"ok": True, "dry_run": True, "raw": None, "error": None, "summary": summary}

    if not API_KEY or not API_SECRET:
        err = "Missing DELTA_API_KEY / DELTA_API_SECRET env vars."
        return {"ok": False, "dry_run": False, "raw": None, "error": err, "summary": err}

    path = "/v2/orders"
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

    if limit_price is not None:
        body_obj["limit_price"] = str(limit_price)
    if stop_order_type is not None:
        body_obj["stop_order_type"] = stop_order_type
    if stop_price is not None:
        body_obj["stop_price"] = str(stop_price)

    body = json.dumps(body_obj, separators=(",", ":"))
    headers = _headers("POST", path, "", body)

    try:
        resp = requests.post(f"{BASE_URL}{path}", data=body, headers=headers, timeout=10)
        data = resp.json()
        ok = bool(data.get("success"))
        summary = (f"{delta_side} {quantity} x {symbol}{desc} submitted to Delta Exchange."
                   if ok else f"Delta Exchange rejected the order: {data}")
        return {"ok": ok, "dry_run": False, "raw": data, "error": None if ok else str(data), "summary": summary}
    except Exception as e:
        return {"ok": False, "dry_run": False, "raw": None, "error": str(e), "summary": f"Order failed: {e}"}


def place_bracket_market_order(delta_symbol: str, side: str, quantity: int, product_id,
                                stop_loss_price: float, take_profit_price: float) -> dict:
    """Places a market entry WITH a native Delta bracket attached, using the EXACT
    payload Delta's own web UI sends (captured from the browser network tab):

        {"order_type":"market_order","side":"buy","product_id":<id>,
         "reduce_only":"false","order_source":"place_order","size":<n>,
         "bracket_take_profit_price":"<tp>","bracket_stop_loss_price":"<sl>",
         "bracket_stop_trigger_method":"mark_price","source":"desktop"}

    This is byte-for-byte the request the UI issues, so if the bracket works in the UI
    it works here. Delta fills the market entry immediately and then creates the SL and
    TP as SEPARATE child orders (see verify_bracket_orders) — genuine native OCO, where
    filling one leg auto-cancels the other.

    IMPORTANT: do NOT judge bracket success from result["result"]["bracket_order"]. On
    a market entry that field is structurally null (the entry is already filled; the
    bracket lives on as separate child orders, not on the entry record). Success of the
    ENTRY is result["success"]; success of the BRACKET is confirmed by GET-ing the
    child legs in verify_bracket_orders(), not from this response.

    Returns Delta's raw parsed JSON response.
    """
    delta_side = "buy" if side.upper() == "BUY" else "sell"
    body_obj = {
        "order_type": "market_order",
        "side": delta_side,
        "product_id": product_id,
        "reduce_only": "false",
        "order_source": "place_order",
        "size": int(quantity),
        "bracket_take_profit_price": str(take_profit_price),
        "bracket_stop_loss_price": str(stop_loss_price),
        "bracket_stop_trigger_method": "mark_price",
        "source": "desktop",
    }
    body = json.dumps(body_obj, separators=(",", ":"))
    headers = _headers("POST", "/v2/orders", "", body)
    resp = requests.post(f"{BASE_URL}/v2/orders", data=body, headers=headers, timeout=10)
    return resp.json()


def attach_bracket_to_position(product_id, stop_loss_price: float,
                                take_profit_price: float,
                                trigger_method: str = "mark_price") -> dict:
    """Fallback: attach a bracket to an ALREADY-OPEN position via the dedicated
    POST /v2/orders/bracket endpoint (documented request shape below). Unlike the
    entry-attached bracket, this operates on a confirmed-open position, so there's no
    fill-timing ambiguity — "size need not be specified as it closes the entire
    position" (Delta docs).

    The stop_loss_order / take_profit_order legs are plain stop-market orders here
    (order_type="market_order" + stop_price) so they always trigger and fully close,
    rather than resting as limits that might not fill. Delta derives the closing side
    from the open position, so no side is passed here.

    Returns Delta's raw parsed JSON response ({"success": true} on success).
    """
    body_obj = {
        "product_id": product_id,
        "stop_loss_order": {
            "order_type": "market_order",
            "stop_price": str(stop_loss_price),
        },
        "take_profit_order": {
            "order_type": "market_order",
            "stop_price": str(take_profit_price),
        },
        "bracket_stop_trigger_method": trigger_method,
    }
    return _post("/v2/orders/bracket", body_obj)


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


def verify_bracket_orders(product_id, expect_sl: bool, expect_tp: bool, retries: int = 2, retry_delay: float = 1.5) -> dict:
    """Queries Delta's open orders for this product right after placing the independent
    SL/TP orders (see auto_place_order()), to actually CONFIRM they exist rather than
    trusting either order's own success=true. Retries a couple times with a short delay
    in case there's propagation lag between an order call succeeding and it becoming
    visible via this GET — checked immediately after the write, a race here would look
    identical to the order never having been placed at all. (Name kept as
    verify_bracket_orders for now even though nothing here is a Delta "bracket" order
    anymore — it verifies "the SL/TP protection", regardless of the underlying mechanism.)

    ⚠️ Queries states=open,pending — NOT just "open". Delta's own docs distinguish
    "open" (resting in the orderbook, e.g. the TP limit order) from "pending" (waiting
    for its trigger condition — exactly what a stop order is before price reaches it).
    A states=open-only query would NEVER find the stop-loss leg, confirmed by Delta's
    own web UI splitting "Open Orders" and "Stop Orders" into separate tabs — this was
    a real bug here (false "missing" on the SL leg even when it genuinely existed).

    Returns {"verified": bool, "missing": [...], "open_orders_count": int, "raw": <last
    response>} — or {"verified": False, "reason": <str>} if the lookup itself failed.
    """
    last_data = None
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(retry_delay)
        try:
            data = _get(f"/v2/orders?product_ids={product_id}&states=open,pending")
        except Exception as e:
            return {"verified": False, "missing": [], "reason": f"Could not verify — open-orders lookup failed: {e}"}
        last_data = data

        orders = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(orders, list):
            return {"verified": False, "missing": [], "reason": f"Unexpected open-orders response: {data}"}

        # Identify the protective legs. This must catch BOTH shapes we might create:
        #   - native bracket child legs (from place_bracket_market_order): these carry
        #     stop_order_type "stop_loss_order" / "take_profit_order" — both confirmed
        #     real values in Delta's docs. (The old check wrongly assumed take_profit_order
        #     didn't exist and that the TP leg had stop_order_type==None, so it missed
        #     genuinely-placed bracket TPs every time.)
        #   - independent fallback legs (from the last-resort path): SL is a stop order
        #     (stop_order_type "stop_loss_order"); TP is a plain reduce_only limit with
        #     no stop_order_type.
        # stop_order_type is THE discriminator between SL and TP — the bracket_*_price
        # fields are deliberately NOT used here, since Delta may echo both prices onto
        # both child legs, which would let an SL-only fill masquerade as having a TP.
        def _is_sl(o):
            return o.get("stop_order_type") == "stop_loss_order"

        def _is_tp(o):
            return (o.get("stop_order_type") == "take_profit_order"
                    or (o.get("reduce_only") is True and o.get("order_type") == "limit_order"
                        and o.get("stop_order_type") is None))

        has_sl = any(isinstance(o, dict) and _is_sl(o) for o in orders)
        has_tp = any(isinstance(o, dict) and _is_tp(o) for o in orders)

        missing = []
        if expect_sl and not has_sl:
            missing.append("stop-loss")
        if expect_tp and not has_tp:
            missing.append("take-profit")

        if not missing:
            break  # found on this attempt, no need to retry further

    return {"verified": not missing, "missing": missing, "open_orders_count": len(orders), "raw": last_data}


def auto_place_order(delta_symbol: str, side: str, sl: float = None, tp: float = None) -> dict:
    """Full auto-size + auto-place flow, no manual confirm — called directly from the
    webhook handler the instant a BTC/ETH/SOL entry alert arrives.

    side: "BUY" or "SELL"
    sl: stop-loss price from the alert (structure ± ATR buffer, as computed by the
        Pine script).
    tp: take-profit price. Defaults to the alert's TP1 unless DELTA_BRACKET_TP_TIER
        overrides which tier to use (tp1/tp2/tp3 — passed in by the caller already
        resolved). Since it's sized for the FULL position, hitting it closes the
        entire trade — this directly satisfies "close on TP1".

    HOW PROTECTION IS PLACED (in this order of preference):
    1. If both sl and tp are given, place a native bracket market entry via
       place_bracket_market_order() — the EXACT payload Delta's own web UI sends. This
       gives real native OCO (filling one leg auto-cancels the other). Then confirm the
       child legs actually exist via verify_bracket_orders() — NOT via the entry's
       "bracket_order" field, which is structurally null on a filled market entry.
    2. If verify can't find both legs, attach a bracket to the now-open position via
       the dedicated POST /v2/orders/bracket endpoint (attach_bracket_to_position()),
       then verify again.
    3. If that still fails (or only one of sl/tp was given), last-resort fallback: place
       SL/TP as two INDEPENDENT reduce_only orders — a stop-market SL and a reduce_only
       limit TP. These reliably attach but do NOT auto-cancel each other.
    verify_bracket_orders() runs after each step as an independent confirmation that the
    protection actually exists — we never trust a lone success=true.

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

        prefix = (f"AUTO {side.upper()} {contracts} x {delta_symbol} @ ~${mark_price:.2f} | "
                  f"margin ${margin:.2f} ({CAPITAL_PCT:.0f}% of ${balance:.2f} balance) "
                  f"@ {leverage}x = ${notional:.2f} notional{bracket_desc}. ")

        close_side = "SELL" if side.upper() == "BUY" else "BUY"
        want_bracket = sl is not None and tp is not None

        # ---- Step 1: entry (native bracket market order if we have both SL and TP) ----
        if want_bracket:
            try:
                entry_raw = place_bracket_market_order(delta_symbol, side, contracts, product_id, sl, tp)
            except Exception as e:
                return {"ok": False, "dry_run": False, "raw": None, "error": str(e),
                        "summary": prefix + f"Bracket-entry call failed: {e}"}
            if not (isinstance(entry_raw, dict) and entry_raw.get("success")):
                return {"ok": False, "dry_run": False, "raw": entry_raw,
                        "error": str(entry_raw), "summary": prefix + f"Delta rejected the order: {entry_raw}"}
            result = {"ok": True, "dry_run": False, "raw": entry_raw, "error": None,
                      "summary": f"{contracts} x {delta_symbol} submitted to Delta Exchange (native bracket)."}
        else:
            # Only one (or neither) of sl/tp — a native bracket needs both, so plain entry.
            result = place_order(symbol=delta_symbol, side=side, quantity=contracts,
                                  order_type="market_order", product_id=product_id, reduce_only=False)

        result["summary"] = prefix + result.get("summary", "")
        if not result["ok"]:
            return result  # entry failed outright — nothing opened, nothing to protect

        if sl is None and tp is None:
            result["bracket_verified"] = None  # no protection requested
            return result

        # ---- Step 2: verify the native bracket legs actually exist ----
        check = verify_bracket_orders(product_id, expect_sl=sl is not None, expect_tp=tp is not None)
        leg_errors = []

        # ---- Step 3: attach-to-position fallback if the native bracket didn't show ----
        if want_bracket and not check["verified"]:
            try:
                attach_raw = attach_bracket_to_position(product_id, sl, tp)
                if not (isinstance(attach_raw, dict) and attach_raw.get("success")):
                    leg_errors.append(f"attach-bracket-to-position rejected: {attach_raw}")
            except Exception as e:
                leg_errors.append(f"attach-bracket-to-position failed: {e}")
            check = verify_bracket_orders(product_id, expect_sl=True, expect_tp=True)

        # ---- Step 4: last-resort independent reduce_only orders for whatever's missing ----
        if not check["verified"]:
            missing = set(check.get("missing") or [])
            if "stop-loss" in missing and sl is not None:
                r = place_order(symbol=delta_symbol, side=close_side, quantity=contracts,
                                order_type="market_order", product_id=product_id, reduce_only=True,
                                stop_order_type="stop_loss_order", stop_price=sl)
                if not r["ok"]:
                    leg_errors.append(f"stop-loss order rejected: {r.get('error') or r.get('raw')}")
            if "take-profit" in missing and tp is not None:
                r = place_order(symbol=delta_symbol, side=close_side, quantity=contracts,
                                order_type="limit_order", product_id=product_id, reduce_only=True,
                                limit_price=tp)
                if not r["ok"]:
                    leg_errors.append(f"take-profit order rejected: {r.get('error') or r.get('raw')}")
            check = verify_bracket_orders(product_id, expect_sl=sl is not None, expect_tp=tp is not None)

        # ---- Final verdict ----
        if check["verified"] and not leg_errors:
            result["bracket_verified"] = True
            result["summary"] += " [SL/TP confirmed present via open-orders check]"
        else:
            reasons = list(check.get("missing") or [])
            if check.get("reason"):
                reasons.append(check["reason"])
            reasons.extend(leg_errors)
            result["summary"] = (
                f"⚠️⚠️ POSITION OPEN WITHOUT FULL PROTECTION — {'; '.join(reasons)} — "
                f"CHECK DELTA AND ADD MANUALLY NOW ⚠️⚠️\n" + result["summary"] +
                f"\nOpen-orders check: {check.get('raw')}"
            )
            result["bracket_verified"] = False

        return result
    except Exception as e:
        return {"ok": False, "dry_run": False, "raw": None, "error": str(e), "summary": f"Auto-trade failed: {e}"}
