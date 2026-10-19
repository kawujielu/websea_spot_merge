# coding=utf-8
"""近1个月 mongoorders：按成交金额降序输出各交易对 symbol/成交金额/用户数/交易笔数。"""
from datetime import datetime, timedelta

import pandas as pd
import pymysql

# ========== 参数 ==========
MYSQL = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "db": "fund",
    "charset": "utf8",
}
RECENT_DAYS = 30
CSV_PATH = ""  # 非空则写 CSV，如 "spot_symbol_vol_30d.csv"
# ==========================


def main():
    start = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn = pymysql.connect(**MYSQL)
    try:
        # 成交金额 + 笔数（按成交 _id 去重）
        vol = pd.read_sql(
            "SELECT symbol, SUM(ABS(amountQuote)) AS 成交金额, "
            "COUNT(DISTINCT `_id`) AS 交易笔数 "
            "FROM mongoorders WHERE ts >= %s GROUP BY symbol",
            conn, params=[start],
        )
        # 用户数：id + Aid 去重
        users = pd.read_sql(
            "SELECT symbol, COUNT(DISTINCT uid) AS 用户数 FROM ("
            "  SELECT symbol, id AS uid FROM mongoorders WHERE ts >= %s "
            "  UNION "
            "  SELECT symbol, Aid AS uid FROM mongoorders WHERE ts >= %s"
            ") t GROUP BY symbol",
            conn, params=[start, start],
        )
    finally:
        conn.close()

    out = vol.merge(users, on="symbol", how="left").fillna({"用户数": 0})
    out["用户数"] = out["用户数"].astype(int)
    out = out.sort_values("成交金额", ascending=False).reset_index(drop=True)
    out = out[["symbol", "成交金额", "用户数", "交易笔数"]]
    out["成交金额"] = out["成交金额"].round(2)

    print("窗口起点: {}  交易对数: {}".format(start, len(out)))
    print(out.to_string(index=False))
    if CSV_PATH:
        out.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        print("CSV:", CSV_PATH)


if __name__ == "__main__":
    main()
