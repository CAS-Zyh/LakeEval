import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from modules.benthic_bqi import normalize_to_wide, BenthicBQICalculator
from modules.db_manager import get_tolerance_dataframe

csv_text = (
    "样点,鉴定单元,物种数量\n"
    "湖心_01,杆丝蚓属,12\n湖心_01,蚌科,5\n湖心_01,锐缘龙虱属,3\n湖心_01,象甲科,4\n湖心_01,泥甲科,8\n"
    "入湖口_02,铁线虫属,18\n入湖口_02,铁线虫纲,6\n入湖口_02,杆丝蚓属,25\n入湖口_02,太平洋牡蛎,2\n"
    "近岸区_03,杆丝蚓属,45\n近岸区_03,水丝蚓属,30\n近岸区_03,某种未鉴定摇蚊,8\n"
    "生态区_04,铜锈环棱螺,22\n生态区_04,河篮蛤,15\n生态区_04,泥甲科,10\n生态区_04,锐缘龙虱属,7\n生态区_04,蚌科,12\n"
)

df = pd.read_csv(io.StringIO(csv_text))
print("原始列:", list(df.columns))
wide = normalize_to_wide(df)
print("透视图列:", list(wide.columns))
print("透视图:")
print(wide.to_string())

calc = BenthicBQICalculator(get_tolerance_dataframe())
res = calc.batch_calculate(wide, site_col="site_name", season="spring")
print("=" * 40)
for s in res["samples"]:
    print(s["site_name"], "BI=", s["bi"], "S=", s["species_count"], "BQI=", s["bqi"], "等级=", s["grade_name"])
print("未匹配:", res["unknown_species"])
