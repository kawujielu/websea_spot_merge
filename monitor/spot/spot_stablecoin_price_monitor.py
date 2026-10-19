#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Websea 现货稳定币交易对盘口偏离监控（独立脚本）。

公允价格：Redis db=3 外部所买卖一（同 spot_market_maker get_weight_aks_bid），
公允价 = (外部 max 卖一 + 外部 min 买一) / 2；不可用则回退 db=1 加权价。

Websea 盘口买一/卖一 相对公允价偏离超过阈值则 Telegram 报警。

用法（在 monitor 项目根目录）:
  python spot/spot_stablecoin_depth_monitor.py          # 循环监控
  python spot/spot_stablecoin_depth_monitor.py --once   # 单次检查

依赖: pip install aiohttp redis requests
"""
from __future__ import annotations

import argparse
import asyncio
import ssl
import time
import traceback
from typing import Any, Optional

import aiohttp
import requests

# ---------------------------------------------------------------------------
# 配置（可按环境修改）
# ---------------------------------------------------------------------------
SPOT_HOST = "https://exqv.websea.work"

# 监控的稳定币交易对；留空则自动探测「有盘口」的稳定币对
STABLECOIN_SYMBOLS: list[str] = [
    # "EURR-USDT",
    # "USDR-USDT",
    "USDC-USDT",
    "USDQ-USDT",
    "EURQ-USDT",
]

# 稳定币 base 货币（用于自动探测）
STABLECOIN_BASES = frozenset({"EURR", "USDR", "USDQ", "EURQ", "USDC"})

DEVIATION_THRESHOLD = 0.05  # 5%
CHECK_INTERVAL_SEC = 60
PRICE_MAX_AGE_SEC = 120  # db=1 兜底加权价过期秒数
# 与 abclibs.config.MAX_SPOST_ASK_BID_VALID_TIME 一致
ASK_BID_VALID_TIME_SEC = 15 * 60

_REDIS_COMMON = {
    "host": "market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com",
    "port": 6379,
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA",
    "ssl": True,
}

# 公允价主路径：外部买卖一（abclibs RS_CONF_ASKBID_PRICE，db=3）
REDIS_ASKBID_PRICE = {**_REDIS_COMMON, "db": 3}

# 汇率换算与兜底加权价（abclibs RS_CONF_MARKET_PRICE，db=1）
REDIS_MARKET_PRICE = {**_REDIS_COMMON, "db": 1}

BASE_SYMBOLS_RATE_FORWARD = frozenset({
    ("BTC", "AQ"), ("ETH", "AQ"), ("USDT", "AQ"), ("OT", "AQ"),
    ("USDT", "USDC"), ("USDT", "USD"), ("USDT", "EUR"),
})

# 与 abclibs.config.weighting 一致
EXCHANGE_WEIGHTING: dict[str, float] = {
    "okex": 1,
    "okex_depth": 2,
    "hb": 3,
    "hb_depth": 2,
    "bitfinex": 3,
    "bitfinex_depth": 2,
    "gate": 3,
    "gate_depth": 2,
    "bn": 3,
    "bn_depth": 2,
    "bkex": 2,
    "bkex_depth": 2,
    "mxc": 2,
    "mxc_depth": 2,
    "bitget": 2,
    "bitget_depth": 2,
    "kraken": 2,
    "kraken_depth": 2,
    "lbank": 2,
    "lbank_depth": 2,
    "abc": 2,
    "abc_depth": 8,
    "custom": 2,
    "custom_depth": 2,
}

# 对标基础货币，稳定币一般为 USDT；无映射时用交易对 quote
SYMBOL_BASE_MAPPER: dict[str, str] = {
    "EURR": "USDT",
    "USDR": "USDT",
    "USDQ": "USDT",
    "EURQ": "USDT",
    "USDC": "USDT",
}

# Telegram（与 spot_kline_monitor.py 相同，可改）
TELEGRAM_TOKEN = "6431006677:AAFPjHsu3ZiowA8vyKYPmK8-b-XSPnBUu3Q"
TELEGRAM_CHAT_ID = "-5146526727"

BLACKLIST_SYMBOLS = frozenset({"MULTI-USDT"})


async def _close_redis(client: Any) -> None:
    """兼容 redis-py 3.x/4.x（close）与 5.x（aclose）。"""
    close_fn = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close_fn is None:
        return
    result = close_fn()
    if asyncio.iscoroutine(result):
        await result


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("ALL")
    return ctx


async def fetch_websea_depth(session: aiohttp.ClientSession, symbol: str) -> Optional[dict[str, Any]]:
    url = f"{SPOT_HOST}/openApi/market/depth"
    try:
        async with session.get(url, params={"symbol": symbol}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("errno") != 0:
        return None
    return data.get("result")


def parse_bid1_ask1(depth: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    bids = depth.get("bids") or []
    asks = depth.get("asks") or []
    if not bids or not asks:
        return None, None
    try:
        bid1 = float(bids[0][0])
        ask1 = float(asks[0][0])
    except (TypeError, ValueError, IndexError):
        return None, None
    return bid1, ask1


async def _redis_weighted_price(r, symbol: str) -> tuple[Optional[float], Optional[float]]:
    """从 Redis hash 取加权价，返回 (price, newest_update_ts)。"""
    raw = await r.hgetall(symbol)
    if not raw:
        return None, None
    now = time.time()
    sum_w = 0.0
    sum_price = 0.0
    newest_update = 0.0
    for source, val in raw.items():
        if "_update" in source:
            ts = float(val)
            if ts > newest_update:
                newest_update = ts
            continue
        w = EXCHANGE_WEIGHTING.get(source, 0)
        if not w:
            continue
        upd_key = f"{source}_update"
        upd_ts = float(raw.get(upd_key, 0) or 0)
        if upd_ts > newest_update:
            newest_update = upd_ts
        if "_depth" not in source and upd_ts and now - upd_ts > 60 * 15:
            w *= 0.2
        sum_price += w * float(val)
        sum_w += w
    if sum_w <= 0:
        return None, newest_update or None
    return sum_price / sum_w, newest_update or None


async def _redis_rate(r_market, base: str, quote: str) -> Optional[float]:
    sym = f"{base}-{quote}"
    price, _ = await _redis_weighted_price(r_market, sym)
    return price


def _apply_rate(ask: float, bid: float, base_broker: str, quote: str, rate: float) -> tuple[float, float]:
    if (base_broker, quote) in BASE_SYMBOLS_RATE_FORWARD:
        return ask * rate, bid * rate
    return ask / rate, bid / rate


async def _redis_external_ask_bid(r_askbid, symbol: str) -> tuple[Optional[float], Optional[float], str]:
    """
    复现 abclibs price_async._rs_get_ask_bid_price：
    各所卖一取 max、买一取 min（在有效时间内）。
    """
    data = await r_askbid.hgetall(symbol)
    if not data:
        return None, None, "redis_db3_empty"

    now_s = time.time()
    asks = []
    bids = []
    for k, v in data.items():
        if "_update" in k:
            continue
        parts = k.split("_", 1)
        if len(parts) != 2:
            continue
        source, side = parts[0], parts[1]
        upd_ts = float(data.get(f"{source}_update", 0) or 0)
        if now_s - upd_ts >= ASK_BID_VALID_TIME_SEC:
            continue
        if side == "ask":
            asks.append(float(v))
        elif side == "bid":
            bids.append(float(v))

    if not asks or not bids:
        return None, None, "redis_db3_incomplete"

    return max(asks), min(bids), "redis_db3"


async def get_fair_price(r_askbid, r_market, symbol: str) -> tuple[Optional[float], str, Optional[float], Optional[float]]:
    """
    公允价：优先 db=3 get_weight_aks_bid → (ask+bid)/2；失败则 db=1 加权价兜底。
    返回 (fair_price, source_label, external_ask, external_bid)。
    """
    parts = symbol.split("-")
    if len(parts) != 2:
        return None, "invalid_symbol", None, None
    currency, quote = parts[0], parts[1]

    if symbol == "USDT-AQ":
        p, ts = await _redis_weighted_price(r_market, symbol)
        if p is None:
            return None, "redis_db1_empty", None, None
        if ts and time.time() - ts > PRICE_MAX_AGE_SEC:
            return None, "redis_db1_stale", None, None
        return p, "redis_db1", p, p

    base_broker = SYMBOL_BASE_MAPPER.get(currency, quote)
    base_symbol = f"{currency}-{base_broker}"

    ext_ask, ext_bid, tag = await _redis_external_ask_bid(r_askbid, base_symbol)
    if ext_ask is not None and ext_bid is not None:
        if base_broker != quote:
            rate = await _redis_rate(r_market, base_broker, quote)
            if rate is None or rate <= 0:
                return None, "rate_missing", ext_ask, ext_bid
            ext_ask, ext_bid = _apply_rate(ext_ask, ext_bid, base_broker, quote, rate)
        fair = (ext_ask + ext_bid) / 2
        return fair, tag, ext_ask, ext_bid

    # 兜底：db=1 加权价（同 strategy_base get_weight_price 回退）
    base_price, ts = await _redis_weighted_price(r_market, base_symbol)
    if base_price is None:
        return None, "redis_db3_empty_db1_empty", None, None
    if ts and time.time() - ts > PRICE_MAX_AGE_SEC:
        return None, "redis_db1_stale", None, None

    if base_broker == quote:
        return base_price, "redis_db1_fallback", None, None

    rate = await _redis_rate(r_market, base_broker, quote)
    if rate is None or rate <= 0:
        return None, "rate_missing", None, None
    if (base_broker, quote) in BASE_SYMBOLS_RATE_FORWARD:
        fair = base_price * rate
    else:
        fair = base_price / rate
    return fair, "redis_db1_fallback", None, None


def deviation_ratio(price: float, ref: float) -> float:
    return abs(price - ref) / ref


def format_depeg_alert(symbol: str, fair_price: float, bid1: float, ask1: float) -> str:
    """Telegram 脱锚报警文案。"""
    return (
        f"{symbol}现货稳定币交易对脱锚警报："
        f"公允价格={fair_price:.8f}，买一={bid1:.8f}， 卖一={ask1:.8f}"
    )


async def discover_running_stable_symbols(session: aiohttp.ClientSession) -> list[str]:
    url = f"{SPOT_HOST}/openApi/market/symbols"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json(content_type=None)
    except Exception:
        return list(STABLECOIN_SYMBOLS)
    if not isinstance(data, dict) or data.get("errno") != 0:
        return list(STABLECOIN_SYMBOLS)

    symbols = [i["symbol"] for i in data.get("result", []) if isinstance(i, dict)]
    candidates = []
    for s in symbols:
        if s in BLACKLIST_SYMBOLS:
            continue
        base = s.split("-")[0]
        if base not in STABLECOIN_BASES:
            continue
        candidates.append(s)

    running = []
    for s in candidates:
        depth = await fetch_websea_depth(session, s)
        bid1, ask1 = parse_bid1_ask1(depth) if depth else (None, None)
        if bid1 is not None and ask1 is not None:
            running.append(s)
        await asyncio.sleep(0.05)
    return running or list(STABLECOIN_SYMBOLS)


async def check_symbol(
    session: aiohttp.ClientSession,
    r_askbid,
    r_market,
    symbol: str,
) -> list[str]:
    alerts: list[str] = []
    depth = await fetch_websea_depth(session, symbol)
    if not depth:
        print(f"[SKIP] {symbol}: 无法获取 Websea 盘口")
        return alerts

    bid1, ask1 = parse_bid1_ask1(depth)
    if bid1 is None or ask1 is None:
        print(f"[SKIP] {symbol}: 盘口为空")
        return alerts

    fair_price, fair_src, _, _ = await get_fair_price(r_askbid, r_market, symbol)
    if fair_price is None or fair_price <= 0:
        print(f"[SKIP] {symbol}: 公允价格不可用({fair_src})")
        return alerts

    bid_dev = deviation_ratio(bid1, fair_price)
    ask_dev = deviation_ratio(ask1, fair_price)

    if bid_dev > DEVIATION_THRESHOLD or ask_dev > DEVIATION_THRESHOLD:
        line = format_depeg_alert(symbol, fair_price, bid1, ask1)
        alerts.append(line)
        print(
            f"[ALERT] {line} "
            f"(买一偏={bid_dev * 100:.3f}% 卖一偏={ask_dev * 100:.3f}% 来源={fair_src})"
        )
    else:
        print(
            f"[OK] {symbol} Websea买一={bid1:.6f} 卖一={ask1:.6f} "
            f"公允价={fair_price:.6f}({fair_src}) "
            f"买一偏={bid_dev * 100:.3f}% 卖一偏={ask_dev * 100:.3f}%"
        )
    return alerts


def send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未配置 TELEGRAM，跳过发送:\n", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=15,
        )
        print("TG:", res.json())
    except Exception as exc:
        print(f"TG 发送失败: {exc}")


async def run_once(symbols: Optional[list[str]] = None) -> bool:
    """返回 True 表示有报警。"""
    try:
        import redis.asyncio as aioredis
    except ImportError as exc:
        raise SystemExit("缺少 redis，请执行: pip install redis") from exc

    def _make_redis(conf: dict[str, Any]):
        kw: dict[str, Any] = dict(
            host=conf["host"],
            port=int(conf["port"]),
            password=conf["password"],
            db=int(conf["db"]),
            decode_responses=True,
        )
        if conf.get("ssl"):
            kw["ssl"] = _ssl_context()
        return aioredis.Redis(**kw)

    r_askbid = _make_redis(REDIS_ASKBID_PRICE)
    r_market = _make_redis(REDIS_MARKET_PRICE)

    connector = aiohttp.TCPConnector(ssl=_ssl_context())
    all_alerts: list[str] = []
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            target = symbols
            if not target:
                if STABLECOIN_SYMBOLS:
                    target = list(STABLECOIN_SYMBOLS)
                else:
                    print("自动探测稳定币交易对...")
                    target = await discover_running_stable_symbols(session)
            print(f"监控 {len(target)} 个交易对（公允价=Redis db3 外部买卖一）: {target}")

            for sym in target:
                all_alerts.extend(await check_symbol(session, r_askbid, r_market, sym))
                await asyncio.sleep(0.1)
    finally:
        await _close_redis(r_askbid)
        await _close_redis(r_market)

    if all_alerts:
        body = "\n".join(all_alerts)
        print(body)
        send_telegram(body)
        return True

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"【现货稳定币盘口】{ts} 全部正常（阈值 {DEVIATION_THRESHOLD * 100:.0f}%）")
    return False


async def main_loop(once: bool, symbols: Optional[list[str]]) -> None:
    while True:
        try:
            await run_once(symbols)
        except Exception:
            err = traceback.format_exc()
            print(err)
            send_telegram(f"【现货稳定币盘口监控异常】\n{err[:3500]}")
        if once:
            break
        await asyncio.sleep(CHECK_INTERVAL_SEC)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Websea 稳定币盘口偏离监控")
    p.add_argument("--once", action="store_true", help="只执行一次")
    p.add_argument(
        "--symbols",
        type=str,
        default="",
        help="逗号分隔交易对，如 EURR-USDT,USDR-USDT；默认用脚本内 STABLECOIN_SYMBOLS",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=f"偏离阈值，默认 {DEVIATION_THRESHOLD}",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=None,
        help=f"循环间隔秒，默认 {CHECK_INTERVAL_SEC}",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.threshold is not None:
        DEVIATION_THRESHOLD = args.threshold
    if args.interval is not None:
        CHECK_INTERVAL_SEC = args.interval
    sym_list = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    asyncio.run(main_loop(once=args.once, symbols=sym_list))

