"""一次性脚本：读取 Excel '印发版' Sheet → 清洗 → 导出 data/tolerance_seed.json。

源文件：中国淡水大型底栖无脊椎动物耐污值（试行）.xlsx → Sheet: 印发版
输出：data/tolerance_seed.json

JSON 结构：
{
  "version": "2024-试行",
  "source": "中国淡水大型底栖无脊椎动物耐污值（试行）",
  "count": 1576,
  "records": [
    {
      "phylum": "扁形动物门",
      "class_name": "涡虫纲",
      "order_name": "三肠目",
      "family": "三角涡虫科",
      "genus": "三角涡虫属",
      "tolerance_value": 2.60
    },
    ...
  ]
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

EXCEL_SOURCE = Path(r"C:\Users\Administrator\Desktop\地表水优良水体评估\中国淡水大型底栖无脊椎动物耐污值（试行）.xlsx")
OUTPUT_JSON = PROJECT_ROOT / "data" / "tolerance_seed.json"
SHEET_NAME = "印发版"

COLUMN_MAP = {
    "门": "phylum",
    "纲": "class_name",
    "目": "order_name",
    "科": "family",
    "属": "genus",
    "耐污值": "tolerance_value",
}


def main() -> int:
    if not EXCEL_SOURCE.exists():
        print(f"[ERROR] 源文件不存在: {EXCEL_SOURCE}")
        return 1

    print(f"[1/4] 读取 Excel: {EXCEL_SOURCE.name} → Sheet: {SHEET_NAME}")
    df = pd.read_excel(EXCEL_SOURCE, sheet_name=SHEET_NAME)
    print(f"      原始形状: {df.shape}")

    # 只保留需要的列
    needed_cols = [c for c in COLUMN_MAP if c in df.columns]
    df = df[needed_cols]
    df = df.rename(columns=COLUMN_MAP)

    # 填充 NaN 为空字符串
    for col in ["phylum", "class_name", "order_name", "family", "genus"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # 耐污值：清洗 + 四舍五入 2 位
    df["tolerance_value"] = pd.to_numeric(df["tolerance_value"], errors="coerce").round(2)
    df = df.dropna(subset=["tolerance_value"])
    df["tolerance_value"] = df["tolerance_value"].astype(float)

    # 过滤无效行（至少要有门）
    df = df[df["phylum"] != ""]

    print(f"[2/4] 清洗后有效记录: {len(df)}")
    print(f"      耐污值范围: {df['tolerance_value'].min():.2f} ~ {df['tolerance_value'].max():.2f}")
    print(f"      门数: {df['phylum'].nunique()}")
    print(f"      含属级条目: {len(df[df['genus'] != ''])}")
    print(f"      含科级条目: {len(df[df['family'] != ''])}")

    records = df.to_dict(orient="records")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "2024-试行",
        "source": "中国淡水大型底栖无脊椎动物耐污值（试行）",
        "count": len(records),
        "records": records,
    }

    print(f"[3/4] 写入 JSON: {OUTPUT_JSON.relative_to(PROJECT_ROOT)}")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 验证
    print(f"[4/4] 验证回读...")
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        verified = json.load(f)
    assert verified["count"] == len(verified["records"]), "记录数不匹配"

    print(f"      完成 — {len(records)} 条记录")
    print(f"      文件大小: {OUTPUT_JSON.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())