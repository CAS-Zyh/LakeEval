# 湖库富营养化动态评价与决策辅助系统

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](https://streamlit.io/)
[![Flask](https://img.shields.io/badge/API-Flask-000000)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**淮河流域中心生态室** 内部使用的湖库富营养化综合分析平台，集营养状态评价、底栖状况评价、协同削减模拟及 AI 智能决策辅助于一体。

---

## ✨ 功能特性

| 模块 | 说明 |
|------|------|
| 📊 **富营养化指数 TLI** | 国标 5 参数计算（Chl-a/TP/TN/SD/CODMn），支持正算与目标反推，雷达图/函数图/贡献条可视化 |
| 🪱 **底栖状况指数 BQI** | 31 种底栖动物耐污值加权评价，判断水体清洁/污染程度 |
| 🎯 **协同削减方案** | 目标 TLI → 智能反推削减比例；两步分级限制因子诊断（OECD 绝对浓度 + Forsberg N:P 比）；差异化削减权重（过饱和/氮限/磷限/协同）；Chl-a OECD 响应函数自动推算 |
| 📝 **历史记录** | 计算记录 CRUD、CSV 导出、按类型筛选 |
| 💬 **AI 智能助手** | DeepSeek 流式对话 + 本地知识库 RAG（TF-IDF 稀疏检索，零向量数据库依赖）；三级权限与用量限制 |

---

## 🏗️ 架构概览

```
LakeEval/
├── run.py                  ← 本地开发入口：同时启动 Flask(5001) + Streamlit(8501)
├── wsgi.py                 ← 线上部署入口：仅启动 Flask（Render/gunicorn 用）
├── config.py               ← 所有配置集中管理（支持 .env 覆盖）
│
├── core/                   ← 【纯算法层】不依赖数据库/网络，最稳定
│   ├── tli.py              TLI 国标计算 + 反推
│   ├── bqi.py              BQI 底栖指数（31 种耐污值）
│   ├── reduction.py        削减方案（二分法+限制因子+Chl-a响应）
│   ├── thresholds.py       分级标准 + 策略建议文案
│   └── utils.py            共用工具
│
├── api/                    ← 【Flask 后端】对外 REST API
│   ├── __init__.py         Flask 初始化 + CORS 白名单 + IP 速率限制
│   ├── extensions.py       SQLAlchemy 扩展
│   ├── models.py           数据库模型（User/ChatHistory/GuestUsage/CalculationRecord）
│   ├── auth.py             JWT 认证 + 游客 token + 权限装饰器
│   ├── routes/             API 路由（Blueprint）
│   │   ├── auth.py         登录/注册/guest_token/用量查询
│   │   ├── tli.py          TLI 正算/反算/分级
│   │   ├── bqi.py          BQI 计算
│   │   ├── reduction.py    削减方案 + 限制因子诊断
│   │   ├── records.py      记录 CRUD + CSV 导出
│   │   └── chat.py         AI 对话 + 知识库状态
│   └── services/           业务服务
│       ├── deepseek.py     DeepSeek HTTP 客户端（流式 SSE）
│       ├── usage.py        用户/游客用量限制
│       └── kb.py           本地知识库 RAG（TF-IDF + 余弦相似度）
│
├── ui/                     ← 【Streamlit 前端】多页面应用
│   ├── app.py              主页（机构标题 + 仪表盘 + 额度卡片）
│   ├── theme.py            简约专业主题 + 自定义 CSS
│   ├── auth.py             前端登录态管理
│   ├── api_client.py       Flask API 封装（支持 API_BASE_URL 环境变量）
│   ├── pages/              功能页（文件名即侧栏菜单，自动发现）
│   │   ├── 1_📊_富营养化TLI.py
│   │   ├── 2_🪱_底栖状况BQI.py
│   │   ├── 3_🎯_削减方案.py
│   │   ├── 4_📝_历史记录.py
│   │   └── 5_💬_AI助手.py
│   └── components/         可复用 UI 组件
│       ├── sidebar.py      TLI 指标输入（滑块 + 数字框双向同步）
│       ├── tli_chart.py    雷达图/函数图/贡献条
│       └── chat_widget.py  AI 对话流式显示组件
│
├── knowledge_base/         ← 本地知识库（txt/md，自动索引）
│   └── README.md           知识库使用说明
│
├── instance/lake_eval.db   ← SQLite 数据库（首次运行自动创建）
├── .env                    ← 本地敏感配置（已 .gitignore 排除，见 .env.example）
├── .env.example            ← 配置模板
├── requirements.txt        ← 依赖清单
├── DEPLOY.md               ← 部署手册
└── README.md               ← 本文件
```

---

## 🚀 快速开始（本地运行）

### 环境要求
- Python 3.10+
- Windows / Linux / macOS 均可

### 安装与启动

```bash
# 1. 克隆仓库
git clone https://github.com/CAS-Zyh/LakeEval.git
cd LakeEval

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制模板后填入）
cp .env.example .env
# 编辑 .env：
#   - DEEPSEEK_API_KEY：填入真实 Key 以启用 AI 助手
#   - JWT_SECRET：自定义随机字符串
#   - 其他可保持默认

# 4. 启动服务（首次运行会自动：创建 SQLite DB + 建表 + 插入默认管理员）
python run.py

# 5. 打开浏览器
# 前端 UI:   http://localhost:8501
# 后端 API:  http://localhost:5001/api
```

### 默认账号

| 角色 | 用户名 | 密码 | AI 额度 |
|------|--------|------|---------|
| 管理员 | `admin` | `admin123` | 无限 |
| 游客 | 无需登录（按 IP 识别） | - | 5 次/天 |

注册的普通用户默认 10 次/天 AI 额度，可由管理员提升。

---

## 🔒 安全设计

| 层级 | 措施 |
|------|------|
| **网络层** | Flask 默认绑定 `127.0.0.1`，不暴露公网；CORS 白名单 `ALLOWED_ORIGINS` 限制跨域来源；IP 速率限制 `RATE_LIMIT_PER_MINUTE` 请求/分钟 |
| **应用层** | JWT 鉴权 + 三级角色（admin/user/guest）；访客按 IP 独立限额；请求体 2MB 上限 |
| **业务层** | 注册用户与游客分表限额；单次对话 max_tokens 分级（admin: 2048, user: 2048, guest: 500）；AI Key 占位符检测与 503 友好报错 |
| **密钥保护** | `.env` 加入 `.gitignore` 永不入库；线上部署通过环境变量注入，前端/浏览器不可访问 DeepSeek Key |

---

## 📚 本地知识库 RAG

AI 回答前会自动从 `knowledge_base/` 目录检索相关专业知识，注入 system prompt：

1. **放入文档**：将 `.txt` 或 `.md` 文件（UTF-8/GBK 均可）放入 `knowledge_base/`，支持多级子目录
2. **自动索引**：系统按文件 mtime 自动检测更新，TF-IDF 稀疏向量 + 余弦相似度，无需向量数据库
3. **正常对话**：AI 自动引用本地知识；冲突时以本地为准

可调参数（`.env`）：
```env
KB_ENABLED=true
KB_CHUNK_SIZE=600    # 切块大小(字符)
KB_CHUNK_OVERLAP=80  # 重叠字符
KB_TOP_K=3           # 单题检索块数
KB_MIN_SCORE=0.12    # 最低相似度阈值
```

详细说明见 `knowledge_base/README.md`。

---

## 📘 API 一览（供二次开发）

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| POST | `/api/auth/guest_token` | 获取游客 JWT（按 IP） |
| GET  | `/api/auth/usage` | 当前用户 AI 用量与额度 |

### TLI
| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/tli/evaluate` | `{"chla":15,"tp":0.08,"tn":1.2,"sd":1.0,"cod_mn":4}` |
| POST | `/api/tli/back_calculate` | `{"target_tli":50, "known":{...}}` |
| GET  | `/api/tli/grades` | 分级标准字典（无需鉴权） |

### BQI
| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/bqi/evaluate` | `{"species_counts":{"物种名":数量,...}}` |

### 削减方案
| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/reduction/diagnose` | `{chla,tp,tn,sd,cod_mn}` → 限制因子诊断 |
| POST | `/api/reduction/target_to_scheme` | `{values, target_tli, strategy="smart"}` → 反推方案 |
| POST | `/api/reduction/calculate` | `{values, ratios}` → 按比例计算 |

### 记录
| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/records?type=&limit=` | 列表 |
| GET    | `/api/records/<id>` | 详情 |
| DELETE | `/api/records/<id>` | 删除 |
| GET    | `/api/records/export?type=` | CSV 导出 |

### AI 对话
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/message` | 流式 SSE：`Accept: text/event-stream`，body `{"message":"问题"}`，每帧 `data: {"role":"assistant","content":"..."}` |
| GET  | `/api/chat/history` | 当前用户对话历史 |
| DELETE | `/api/chat/history` | 清空历史 |
| GET  | `/api/chat/kb_status` | 知识库索引状态 |

---

## 🛠️ 维护指南

### 改动类型 → 对应文件

| 需求 | 修改位置 |
|------|---------|
| 调整 TLI/BQI 公式参数 | `core/tli.py` / `core/bqi.py` |
| 调整限制因子阈值/工程边界 | `core/reduction.py` 顶部常量（`BASELINE_TP / BASELINE_TN / N_P_RATIO_* / ENGINEERING_LIMITS / CHLA_RESPONSE_*`） |
| 调整策略文案/分级标准 | `core/thresholds.py` |
| 调整游客/用户额度 | `config.py` 或 `.env`（`GUEST_DAILY_CHAT_LIMIT`、`USER_DAILY_CHAT_LIMIT`） |
| 调整 CORS / 速率限制 | `config.py` → `ALLOWED_ORIGINS` / `RATE_LIMIT_PER_MINUTE` |
| 新增底栖动物耐污种 | `core/bqi.py` → `SPECIES_TOLERANCE` 字典 |
| 新增功能页 | `ui/pages/` 新建 `X_图标_页面名.py`；需要后端时在 `api/routes/` 新增 Blueprint 并在 `api/__init__.py` 注册 |
| 新增数据表 | `api/models.py` 新增 `db.Model` 类，重启服务自动 `create_all()` |
| 更换 AI 模型 | 重写 `api/services/deepseek.py` 客户端 |
| 更换向量检索（升级 Embedding） | 重写 `api/services/kb.py` 的 `build_index / search` 方法 |

---

## 📖 部署

详见 [DEPLOY.md](DEPLOY.md)：Render 部署 Flask 后端 + Streamlit Cloud 部署前端，前后端分离、按需冷启动。

---

## 📄 License

本项目内部使用，如需开源请联系项目负责人。
