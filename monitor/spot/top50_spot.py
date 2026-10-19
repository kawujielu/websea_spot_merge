# coding=utf-8
"""
按日 K 统计现货交易对「最近 N 天成交金额（成交额 vol）日均值」，输出排名靠前的交易对。
使用 exchange.restful_api.abc_spot.AApi。（K 线字段 vol 为计价货币成交额，即成交金额。）

注意：abc_spot.AApi 在每次 request 后会 close ClientSession，但缓存字典未清理，
同一实例上第二次请求会复用已关闭的 session（RuntimeError: Session is closed）。
因此本脚本对每一次 REST 调用都新建 AApi 实例，不修改 abc_spot.py。

在 monitor 项目根目录执行:
    python spot/top50_spot.py

对 Top 结果会再拉盘口 depth，展示：中间价 ±band 范围内买卖盘计价深度合计、买一卖一价差相对中间价的百分比。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_credentials(account_name: Optional[str]) -> Tuple[str, str]:
    token = os.environ.get("SPOT_API_TOKEN", "").strip()
    secret = os.environ.get("SPOT_API_SECRET", "").strip()
    if token and secret:
        return token, secret

    from config import infor

    if account_name:
        acc = infor.spot_account.get(account_name)
        if not acc:
            raise SystemExit(f"未找到 spot_account 键: {account_name}")
        apikey = acc.get("apikey") or {}
        token = (apikey.get("token") or "").strip()
        secret = (apikey.get("sk") or "").strip()
        if not token or not secret:
            raise SystemExit(f"账户 {account_name} 缺少 token/sk")
        return token, secret

    for _name, acc in infor.spot_account.items():
        apikey = acc.get("apikey") or {}
        token = (apikey.get("token") or "").strip()
        secret = (apikey.get("sk") or "").strip()
        if token and secret:
            return token, secret

    raise SystemExit(
        "未配置 API：请设置 SPOT_API_TOKEN / SPOT_API_SECRET，"
        "或使用 --account 指定 spot_account 中的账户名"
    )


def _parse_kline_volume(res: Any, metric: str) -> Optional[Tuple[float, int]]:
    if not isinstance(res, dict):
        return None
    if "code" in res and "errno" not in res:
        return None
    if res.get("errno") != 0:
        return None
    body = res.get("result")
    if not isinstance(body, dict):
        return None
    rows = body.get("data") or []
    if not rows:
        return None
    values: List[float] = []
    for bar in rows:
        if not isinstance(bar, dict):
            continue
        if metric not in bar:
            continue
        try:
            values.append(float(bar[metric]))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    avg = sum(values) / len(values)
    return avg, len(values)


def _parse_depth_spread_and_band_notional(
    res: Any, band: float
) -> Optional[Tuple[float, float]]:
    """
    解析 depth 接口结果。
    返回 (盘口价差百分比, 买卖盘在「中间价±band」内的深度金额(计价货币))。
    价差% = (卖一 - 买一) / 中间价 * 100；中间价 = (买一+卖一)/2。
    深度：bid 侧 price >= mid*(1-band)，ask 侧 price <= mid*(1+band)，各档 price*amount 求和后相加。
    """
    if not isinstance(res, dict):
        return None
    if "code" in res and "errno" not in res:
        return None
    if res.get("errno") != 0:
        return None
    body = res.get("result")
    if not isinstance(body, dict):
        return None
    bids = body.get("bids") or []
    asks = body.get("asks") or []
    if not bids or not asks:
        return None
    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
    except (IndexError, TypeError, ValueError):
        return None
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        return None
    mid = (best_bid + best_ask) / 2.0
    spread_pct = (best_ask - best_bid) / mid * 100.0

    low = mid * (1.0 - band)
    high = mid * (1.0 + band)
    bid_notional = 0.0
    for lv in bids:
        try:
            p, a = float(lv[0]), float(lv[1])
        except (TypeError, ValueError, IndexError):
            continue
        if p >= low:
            bid_notional += p * a
    ask_notional = 0.0
    for lv in asks:
        try:
            p, a = float(lv[0]), float(lv[1])
        except (TypeError, ValueError, IndexError):
            continue
        if p <= high:
            ask_notional += p * a
    depth_quote = bid_notional + ask_notional
    return spread_pct, depth_quote


async def _run(
    *,
    days: int,
    top_n: int,
    metric: str,
    min_bars: int,
    account: Optional[str],
    json_out: Optional[str],
    production_host: bool,
    depth_band: float,
    skip_depth: bool,
) -> None:
    from exchange.restful_api.abc_spot import AApi

    token, secret = _load_credentials(account)
    flag = "prod" if production_host else ""

    def _new_api() -> Any:
        return AApi(token=token, secret_key=secret, flag=flag)

    # 每次 REST 使用新 AApi，避免 abc_spot 内 close 后仍命中 self.session 里已关闭的 ClientSession
    sym_res = await _new_api().symbols()
    if not isinstance(sym_res, dict) or sym_res.get("errno") != 0:
        raise SystemExit(f"symbols 请求失败: {sym_res}")

    symbols_list = [
        x["symbol"]
        for x in (sym_res.get("result") or [])
        if isinstance(x, dict) and x.get("symbol")
    ]
    if not symbols_list:
        raise SystemExit("symbols 结果为空")

    rows_out: List[Dict[str, Any]] = []
    errors = 0

    for sym in symbols_list:
        kl = await _new_api().kline(sym, "1day", days)
        parsed = _parse_kline_volume(kl, metric)
        if parsed is None:
            errors += 1
            continue
        avg, n_bars = parsed
        if n_bars < min_bars:
            continue
        rows_out.append(
            {
                "symbol": sym,
                "avg": avg,
                "bars_used": n_bars,
                "metric": metric,
            }
        )

    rows_out.sort(key=lambda r: r["avg"], reverse=True)
    top = rows_out[:top_n]

    depth_fail = 0
    if not skip_depth:
        for r in top:
            dres = await _new_api().depth(r["symbol"])
            parsed_d = _parse_depth_spread_and_band_notional(dres, depth_band)
            if parsed_d is None:
                r["spread_pct"] = None
                r["depth_band_quote"] = None
                depth_fail += 1
            else:
                sp, dq = parsed_d
                r["spread_pct"] = round(sp, 6)
                r["depth_band_quote"] = dq
    else:
        for r in top:
            r["spread_pct"] = None
            r["depth_band_quote"] = None

    metric_label = (
        "amount(基础币成交量)" if metric == "amount" else "vol(成交金额/计价货币成交额)"
    )
    print(
        f"排名依据: 最近至多 {days} 根日K 的 {metric_label} 算术平均；"
        f"共 {len(symbols_list)} 个交易对，有效 {len(rows_out)}，失败/跳过 {errors}，输出 Top {top_n}"
    )
    if not skip_depth:
        print(
            f"盘口补充: 中间价±{depth_band * 100:.1f}% 内深度(计价)、价差%= (卖一-买一)/中间价*100"
            + (f"；depth 失败 {depth_fail} 条" if depth_fail else "")
        )
    col_avg = "日均成交额" if metric == "vol" else "日均成交量"
    if skip_depth:
        print(f"{'#':<4} {'symbol':<18} {col_avg:>22}")
        for i, r in enumerate(top, 1):
            print(f"{i:<4} {r['symbol']:<18} {r['avg']:>22.8f}")
    else:
        print(
            f"{'#':<4} {'symbol':<16} {col_avg:>18} "
            f"{'价差%':>10} {'深度±%':>18}"
        )
        for i, r in enumerate(top, 1):
            sp = r.get("spread_pct")
            dq = r.get("depth_band_quote")
            sp_s = f"{sp:.4f}" if sp is not None else "-"
            dq_s = f"{dq:,.2f}" if dq is not None else "-"
            print(
                f"{i:<4} {r['symbol']:<16} {r['avg']:>18.8f} "
                f"{sp_s:>10} {dq_s:>18}"
            )

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(top, f, ensure_ascii=False, indent=2)
        print(f"已写入 JSON: {json_out}")


def main() -> None:
    p = argparse.ArgumentParser(description="现货日K成交金额（vol）日均值 TopN")
    p.add_argument("--days", type=int, default=10, help="日K根数（最近几天）")
    p.add_argument("--top-n", type=int, default=100, help="输出前 N 名")
    p.add_argument(
        "--metric",
        choices=("amount", "vol"),
        default="vol",
        help="vol=成交金额(计价货币成交额，默认) amount=基础币成交量",
    )
    p.add_argument(
        "--min-bars",
        type=int,
        default=1,
        help="至少多少根 K 才参与排名（默认有数据就算）",
    )
    p.add_argument(
        "--account",
        type=str,
        default=None,
        help="使用 config.infor.spot_account 中该键名的 API",
    )
    p.add_argument("--json-out", type=str, default=None, help="将 Top 结果写入 JSON 文件")
    p.add_argument(
        "--prod-host",
        action="store_true",
        help="使用正式域名 oapi.websea.com（对应 AApi flag='prod'）",
    )
    p.add_argument(
        "--depth-band",
        type=float,
        default=0.02,
        help="深度统计价格带相对中间价的比例，默认 0.02 即 ±2%%",
    )
    p.add_argument(
        "--skip-depth",
        action="store_true",
        help="不请求盘口 depth（仅按 K 线排名输出）",
    )
    args = p.parse_args()

    if args.days < 1 or args.days > 2000:
        raise SystemExit("--days 应在 1~2000")
    if args.top_n < 1:
        raise SystemExit("--top-n 须 >= 1")
    if args.min_bars < 1 or args.min_bars > args.days:
        raise SystemExit("--min-bars 非法")
    if args.depth_band <= 0 or args.depth_band > 0.5:
        raise SystemExit("--depth-band 建议在 (0, 0.5] 内，例如 0.02 表示 2%")

    asyncio.run(
        _run(
            days=args.days,
            top_n=args.top_n,
            metric=args.metric,
            min_bars=args.min_bars,
            account=args.account,
            json_out=args.json_out,
            production_host=args.prod_host,
            depth_band=args.depth_band,
            skip_depth=args.skip_depth,
        )
    )


if __name__ == "__main__":
    main()

