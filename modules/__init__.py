"""底栖动物 BQI 评价模块。

modules/
├── __init__.py           # 包入口
├── benthic_bqi.py        # 核心算法：BI 生物指数 + 种类数得分 → BQI
└── db_manager.py          # SQLite 数据库管理：种子导入、耐污值查询、缓存

数据源：data/tolerance_seed.json（中国淡水大型底栖无脊椎动物耐污值 试行版）
"""