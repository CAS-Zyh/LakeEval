"""一次性脚本：从 Excel 导出底栖动物耐污值 JSON 种子文件。

源文件：C:\\Users\\Administrator\\Desktop\\地表水优良水体评估\\中国淡水大型底栖无脊椎动物耐污值（试行）.xlsx
输出：data/benthic_tolerance.json

用法:
    python scripts/import_benthic_tolerance.py

JSON 结构（每行一个分类单元）:
{
  "version": "2024-试行",
  "source": "中国淡水大型底栖无脊椎动物耐污值（试行）",
  "count": 1576,
  "records": [
    {
      "phylum_zh": "扁形动物门", "phylum_en": "Platyhelminthes",
      "class_zh": "涡虫纲", "class_en": "Turbellaria",
      "order_zh": "三肠目", "order_en": "Tricladida",
      "family_zh": "三角涡虫科", "family_en": "Dugesiidae",
      "genus_zh": "三角涡虫属", "genus_en": "Dugesia",
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

COLUMN_MAP = {
    "门": "phylum_zh",
    "Phylum": "phylum_en",
    "纲": "class_zh",
    "Class": "class_en",
    "目": "order_zh",
    "Order": "order_en",
    "科": "family_zh",
    "Family": "family_en",
    "属": "genus_zh",
    "Genus": "genus_en",
    "耐污值": "tolerance_value",
}


def main() -> int:
    if not EXCEL_SOURCE.exists():
        print(f"[error] 源文件不存在: {EXCEL_SOURCE}")
        return 1

    print(f"[1/3] 读取 Excel: {EXCEL_SOURCE.name}")
    df = pd.read_excel(EXCEL_SOURCE, sheet_name=0)
    print(f"     原始形状: {df.shape}")

    df = df.rename(columns=COLUMN_MAP)
    df = df[list(COLUMN_MAP.values())]

    df = df.fillna("")

    df["tolerance_value"] = pd.to_numeric(df["tolerance_value"], errors="coerce").round(2)
    df = df.dropna(subset=["tolerance_value"])
    df["tolerance_value"] = df["tolerance_value"].astype(float)

    records = df.to_dict(orient="records")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "2024-试行",
        "source": "中国淡水大型底栖无脊椎动物耐污值（试行）",
        "count": len(records),
        "records": records,
    }

    print(f"[2/3] 写入 JSON: {OUTPUT_JSON.relative_to(PROJECT_ROOT)}")
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3/3] 完成 — 共 {len(records)} 条记录")
    print(f"     耐污值范围: {df['tolerance_value'].min():.2f} ~ {df['tolerance_value'].max():.2f}")
    print(f"     涉及门数: {df[df['phylum_zh'] != '']['phylum_zh'].nunique()}")

    by_genus = df[(df["genus_zh"] != "") | (df["genus_en"] != "")]
    print(f"     含属级条目: {len(by_genus)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
