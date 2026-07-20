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
  DELTA_BRACKET_SLIPPAGE_PCT (default "0.3" — limit-price buffer beyond the SL/TP
                             trigger, to improve fill probability during fast moves)
  DELTA_BRACKET_TRIGGER    (default "last_traded_price" — the only value confirmed in
                             Delta's docs; "mark_price" may also work but is unverified)

Note on architecture: the entry order (plain market_order) and the SL/TP bracket are
placed as TWO SEPARATE API calls — place_order() for the entry, then place_bracket()
via Delta's dedicated /v2/orders/bracket endpoint once the position exists. This
replaced an earlier single-call approach (bracket_* fields attached directly to the
entry) after it silently dropped the SL/TP legs twice on testnet, with both
market_order and limit_order entries. Every bracketed auto-trade is followed by
verify_bracket_orders(), an independent GET check that the SL/TP orders actually
exist — this doesn't trust either call's own success flag.
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


def _closing_limit_price(trigger_price: float, delta_side: str, buffer_pct: float) -> float:
    """Computes the limit price for a bracket leg's closing order, offset from the
    trigger in whichever direction improves fill probability. delta_side here is the
    ENTRY side (buy=long, sell=short) — the closing order is the opposite:
      - LONG (delta_side="buy"): closing order is a SELL. Give room BELOW the trigger
        so it can still fill if price is moving fast through the level.
      - SHORT (delta_side="sell"): closing order is a BUY. Give room ABOVE the trigger.
    Same formula serves both stop-loss and take-profit legs — for a stop it prioritizes
    getting filled at all; for a take-profit it trades a little profit for fill certainty.
    """
    buffer = trigger_price * (buffer_pct / 100)
    return trigger_price - buffer if delta_side == "buy" else trigger_price + buffer


def place_order(symbol: str, side: str, quantity: int, order_type: str = None,
                 limit_price: float = None,
                 stop_loss_price: float = None, take_profit_price: float = None) -> dict:
    """
    side: "BUY" or "SELL" — map LONG->BUY, SHORT->SELL before calling this.
    quantity: number of contracts (Delta calls this "size").
    symbol: Delta's product_symbol (e.g. "BTCUSD" for the perpetual — crypto
            symbols line up with the indicator's ticker; gold contracts don't
            necessarily, so double-check before confirming).
    limit_price: only used when order_type="limit_order" — otherwise ignored. Not used
    by auto_place_order() as of the current design (see below); kept available for
    manual/future use.
    stop_loss_price / take_profit_price: optional absolute prices, attached as flat
    bracket_* fields on THIS SAME call. ⚠️ auto_place_order() no longer uses this
    parameter pair — attaching bracket fields directly to the entry order was tried
    twice (once with order_type="market_order", once with "limit_order") and BOTH
    times the entry succeeded while the SL/TP legs silently never attached. It now
    places a plain entry here, then calls place_bracket() as a SEPARATE follow-up call
    via Delta's dedicated bracket endpoint. These parameters are kept on place_order()
    for the (currently unused) case of wanting bracket-on-entry again — if you use them,
    verify independently that the resulting orders actually exist, the same way
    auto_place_order() does via verify_bracket_orders().

    Returns: {"ok": bool, "dry_run": bool, "raw": <api response or None>,
              "error": <str or None>, "summary": <human-readable str>}
    """
    order_type = order_type or os.environ.get("DELTA_ORDER_TYPE", "market_order")
    delta_side = "buy" if side.upper() == "BUY" else "sell"
    sl_slippage_pct = float(os.environ.get("DELTA_BRACKET_SLIPPAGE_PCT", "0.3"))
    trigger_method = os.environ.get("DELTA_BRACKET_TRIGGER", "last_traded_price")

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
    body_obj = {
        "product_symbol": symbol,
        "size": int(quantity),
        "side": delta_side,
        "order_type": order_type,
    }

    if order_type == "limit_order" and limit_price is not None:
        body_obj["limit_price"] = str(limit_price)

    if stop_loss_price is not None:
        sl_limit = _closing_limit_price(stop_loss_price, delta_side, sl_slippage_pct)
        body_obj["bracket_stop_loss_price"] = str(stop_loss_price)
        body_obj["bracket_stop_loss_limit_price"] = str(round(sl_limit, 2))
        body_obj["bracket_stop_trigger_method"] = trigger_method

    if take_profit_price is not None:
        tp_limit = _closing_limit_price(take_profit_price, delta_side, sl_slippage_pct)
        body_obj["bracket_take_profit_price"] = str(take_profit_price)
        body_obj["bracket_take_profit_limit_price"] = str(round(tp_limit, 2))
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


def place_bracket(product_id, delta_side: str, stop_loss_price: float = None,
                   take_profit_price: float = None) -> dict:
    """Attaches a stop-loss and/or take-profit to an EXISTING position via Delta's
    dedicated bracket endpoint (POST /v2/orders/bracket) — as a SEPARATE call after
    the entry, not attached to the entry order itself.

    This replaces the earlier approach of sending bracket_* fields flat on the /v2/orders
    entry call. That was tried twice (first with order_type="market_order", then with
    "limit_order" after Delta's docs suggested brackets are only confirmed on limit
    entries) and BOTH times the entry succeeded while the SL/TP legs silently never
    attached. Rather than guess a third parameter tweak on the same combined-call
    mechanism, this uses the endpoint Delta's docs describe specifically for attaching
    a bracket to a position — a genuinely different code path, not a variation of the
    same one. If this also fails, the raw Delta response is captured (see
    auto_place_order()) so the exact rejection reason is visible instead of guessed at.
    """
    sl_slippage_pct = float(os.environ.get("DELTA_BRACKET_SLIPPAGE_PCT", "0.3"))
    trigger_method = os.environ.get("DELTA_BRACKET_TRIGGER", "last_traded_price")

    body_obj = {"product_id": product_id, "bracket_stop_trigger_method": trigger_method}

    if stop_loss_price is not None:
        sl_limit = _closing_limit_price(stop_loss_price, delta_side, sl_slippage_pct)
        body_obj["stop_loss_order"] = {
            "order_type": "limit_order",
            "stop_price": str(stop_loss_price),
            "limit_price": str(round(sl_limit, 2)),
        }

    if take_profit_price is not None:
        tp_limit = _closing_limit_price(take_profit_price, delta_side, sl_slippage_pct)
        body_obj["take_profit_order"] = {
            "order_type": "limit_order",
            "stop_price": str(take_profit_price),
            "limit_price": str(round(tp_limit, 2)),
        }

    return _post("/v2/orders/bracket", body_obj)


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
        Pine script). Placed via place_bracket() as a SEPARATE call right after the
        entry order confirms — NOT attached to the entry call itself (that approach
        was tried twice, with both market_order and limit_order entries, and both
        times the entry succeeded while the SL/TP legs silently never attached).
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

        # STEP 1: plain entry, no bracket fields attached to it. This part has reliably
        # worked in every test so far (both prior failures were specifically the bracket
        # legs going missing, never the entry itself) — a normal market order.
        result = place_order(symbol=delta_symbol, side=side, quantity=contracts, order_type="market_order")
        prefix = (f"AUTO {side.upper()} {contracts} x {delta_symbol} @ ~${mark_price:.2f} | "
                  f"margin ${margin:.2f} ({CAPITAL_PCT:.0f}% of ${balance:.2f} balance) "
                  f"@ {leverage}x = ${notional:.2f} notional{bracket_desc}. ")
        result["summary"] = prefix + result.get("summary", "")

        if not result["ok"]:
            return result  # entry itself failed — nothing to attach a bracket to

        # STEP 2: attach SL/TP as a SEPARATE call via the dedicated bracket endpoint,
        # now that the position actually exists. See place_bracket()'s docstring for
        # why this replaced the earlier "attach bracket fields to the entry" approach.
        if sl is not None or tp is not None:
            delta_side = "buy" if side.upper() == "BUY" else "sell"
            bracket_error = None
            try:
                bracket_resp = place_bracket(product_id, delta_side, stop_loss_price=sl, take_profit_price=tp)
                if not (isinstance(bracket_resp, dict) and bracket_resp.get("success")):
                    bracket_error = f"bracket call rejected: {bracket_resp}"
            except Exception as e:
                bracket_error = f"bracket call failed: {e}"

            # Don't trust either the bracket call's own success flag OR its absence of an
            # exception — confirm the SL/TP orders actually exist. This is the permanent
            # safety net for exactly what happened twice already: something reports fine
            # while the protection silently isn't there.
            check = verify_bracket_orders(product_id, expect_sl=sl is not None, expect_tp=tp is not None)
            if not check["verified"] or bracket_error:
                reasons = list(check.get("missing") or [])
                if check.get("reason"):
                    reasons.append(check["reason"])
                if bracket_error:
                    reasons.append(bracket_error)
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
