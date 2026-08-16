# 淮河流域中心生态室 — 湖库富营养化动态评价与决策辅助系统

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](https://streamlit.io/)
[![Flask](https://img.shields.io/badge/API-Flask-000000)](https://flask.palletsprojects.com/)
[![Memory Mode](https://img.shields.io/badge/Deployment-Stateless%20Ready-22c55e)](#部署)
[![License](https://img.shields.io/badge/License-Internal%20Use-green)](#许可)

**淮河流域中心生态室** 内部使用的湖库富营养化综合分析平台，集营养状态评价、底栖状况评价、协同削减模拟及 AI 智能决策辅助于一体。代码针对**无状态免费云端环境**（无持久化磁盘、重启文件重置）做了适配，核心功能在内存模式下仍能正常运行。

---

## ✨ 功能特性

| 模块 | 说明 |
|------|------|
| 🔍 **富营养化指数 (TLI)** | 国标 5 参数（Chl-a / TP / TN / SD / CODMn）正算与分级；侧栏滑条与数字输入框实时双向同步；雷达图 / 贡献条 / 函数曲线可视化 |
| 🐌 **底栖状况指数 (BQI)** | 底栖动物耐污值加权评价，判断水体清洁/污染程度；支持 30+ 种常见物种与分级标准查询 |
| 🎯 **协同削减方案** | 设置目标 TLI → 智能反推 TN/TP/Chl-a 等削减比例；**两步分级营养限制因子诊断**（OECD 绝对浓度阈值 + N:P 比值）；差异化削减权重（过饱和/氮限制/磷限制/协同）；OECD Chl-a 响应函数自动推算 |
| 📜 **历史记录** | TLI/BQI/削减方案 计算记录查询、删除、按类型筛选与导出 |
| 💬 **AI 智能助手** | 流式对话 + 本地知识库 RAG（TF-IDF 稀疏向量 + 余弦相似度，**无需向量数据库**）；三级角色额度控制 |
| 🧠 **本地知识库 RAG** | `.txt / .md` 文件自动索引，随仓库提交；AI 回答前自动检索并引用本地专业知识 |

---

## 🏗️ 系统架构

```
LakeEval/
├── run.py                  ← 本地开发入口：同时启动 Flask(API) + Streamlit(UI)
├── wsgi.py                 ← 线上部署入口：仅启动 Flask（Render / gunicorn 用）
├── config.py               ← 配置中心（环境变量覆盖，默认内存数据库）
│
├── core/                   ← 纯算法层（无 DB/网络依赖，最易测试和迁移）
│   ├── tli_model.py        TLI 国标计算 / 反推 / 分级
│   ├── bqi_model.py        BQI 底栖指数（含 30+ 物种耐污值表）
│   ├── reduction.py        削减方案（二分法 + 限制因子 + Chl-a 响应）
│   └── thresholds.py       分级标准 + 策略建议文案
│
├── api/                    ← Flask 后端（REST API）
│   ├── __init__.py         Flask 初始化 + CORS 白名单 + 安全降级
│   ├── extensions.py       SQLAlchemy 扩展
│   ├── safe_db.py          DB 写入安全封装（无状态环境下写失败不崩）
│   ├── models.py           数据库模型
│   ├── auth.py             JWT 鉴权 + 游客 Token + 角色装饰器
│   ├── routes/             Blueprint 路由
│   │   ├── auth.py         注册 / 登录 / 游客 Token / 用量
│   │   ├── tli.py          TLI 正算 / 反算 / 分级
│   │   ├── bqi.py          BQI 计算 / 物种 / 分级
│   │   ├── reduction.py    限制因子诊断 / 智能削减 / 协同削减
│   │   ├── records.py      记录查询 / 删除 / 导出
│   │   ├── chat.py         AI 对话 / 历史 / 知识库状态
│   │   └── admin.py        管理员（用户管理 / 额度 / 统计）
│   └── services/           业务服务
│       ├── deepseek.py     AI HTTP 客户端（流式 SSE）
│       ├── usage.py        用户/游客用量限制（DB 失败 → 进程内存兜底）
│       └── kb.py           本地知识库 RAG（TF-IDF + 余弦相似度，纯内存索引）
│
├── ui/                     ← Streamlit 前端（多页面应用）
│   ├── app.py              主入口（机构标题 / 仪表盘 / 额度 / 无状态提醒）
│   ├── theme.py            主题 + 自定义 CSS
│   ├── auth.py             前端登录态
│   ├── api_client.py       Flask API 封装（支持 API_BASE_URL 环境变量）
│   ├── pages/              功能页（文件名即侧栏菜单）
│   │   ├── 1_🔍_TLI评价.py
│   │   ├── 2_🐌_BQI评价.py
│   │   ├── 3_🎯_削减方案.py
│   │   ├── 4_📜_历史记录.py
│   │   └── 5_💬_AI助手.py
│   └── components/         UI 组件库
│       ├── sidebar.py      指标输入面板（滑条 ↔ 数字框双向同步）
│       ├── charts.py       雷达图 / 函数曲线 / 贡献条
│       ├── metric_cards.py 卡片 / 等级徽章 / 提示框
│       └── chat_widget.py  AI 流式对话组件
│
├── knowledge_base/         ← 本地知识库（txt/md，随仓库提交，只读）
│   └── README.md           知识库添加说明
│
├── requirements.txt        ← 完整依赖清单
├── DEPLOY.md               ← 部署手册（Render + Streamlit Cloud）
└── README.md               ← 本文件
```

---

## 🚀 本地快速开始

**环境要求**：Python 3.10+，Windows / Linux / macOS 均可。

```bash
# 1. 克隆仓库
git clone https://github.com/CAS-Zyh/LakeEval.git
cd LakeEval

# 2. 安装依赖
pip install -r requirements.txt

# 3. （可选）配置环境变量
#    复制 .env.example 为 .env，按注释填入即可。
#    不配置也能跑：默认使用内存 SQLite（重启重置），部分功能不启用。

# 4. 一键启动（Flask API + Streamlit UI）
python run.py

# 5. 浏览器打开
#    前端 UI：  http://localhost:8501
#    后端 API： http://localhost:5001/api/status
```

启动成功标志：`/api/status` 返回 JSON 中包含 `db_ephemeral: true`（代表当前运行在内存/无状态模式）。

---

## 📚 本地知识库

AI 回答前会自动从 `knowledge_base/` 目录检索相关文档，注入 prompt。使用方式：

1. **放入文档**：将 `.txt` 或 `.md` 文件（UTF-8 / GBK 编码均可）放入 `knowledge_base/`，支持多级子目录
2. **自动索引**：首次调用 AI 时按文件修改时间自动检测更新，纯内存 TF-IDF 稀疏向量索引，**无需向量数据库**
3. **正常对话**：AI 自动引用本地知识

详细说明见 [knowledge_base/README.md](knowledge_base/README.md)。

---

## 🔧 REST API 一览（二次开发）

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| POST | `/api/auth/guest_token` | 获取游客 JWT（每日额度限制） |
| GET  | `/api/auth/me` | 当前用户信息 |
| GET  | `/api/auth/usage` | 当前用户 AI 用量 / 额度 |

### TLI

| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/tli/calculate` | `{"site_name":"S1","date":"2025-01-01","data":{"tp":0.1,"tn":1.5,"chla":20,"codmn":6,"sd":1.5}}` |
| POST | `/api/tli/back_calculate` | `{"target_tli":60, "known":{...}}` 固定已知指标反推其余 |
| GET  | `/api/tli/grades` | 分级标准（无需鉴权） |

### BQI

| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/bqi/calculate` | `{"data":{"Bellamya aeruginosa":60,"Corbicula fluminea":30,...}}` |
| GET  | `/api/bqi/species` | 支持的物种 & 耐污值表 |
| GET  | `/api/bqi/grades` | 分级标准 |

### 削减方案

| 方法 | 路径 | Body |
|------|------|------|
| POST | `/api/reduction/diagnose` | `{tp,tn,chla,sd,codmn}` → 营养限制因子诊断（两步法） |
| POST | `/api/reduction/smart` | `{base,target_tli,constraints}` → 智能反推削减方案 |
| POST | `/api/reduction/collaborative` | 协同削减（固定权重） |
| POST | `/api/reduction/uniform` | 均匀削减（固定比例） |
| POST | `/api/reduction/function_curve` | 响应函数曲线数据 |

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
| POST | `/api/chat/message` | 流式 SSE：`Accept: text/event-stream`；帧格式 `data: {"role":"assistant","content":"..."}` |
| GET  | `/api/chat/history` | 当前用户对话历史 |
| DELETE | `/api/chat/history` | 清空历史 |
| GET  | `/api/chat/usage` | 用量 / 额度 |
| GET  | `/api/chat/kb_status` | 知识库索引状态（索引块数、路径） |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/status` | 服务状态 + 是否无状态内存模式（无需鉴权） |

---

## 🛠 维护 / 二次开发指南

| 需求 | 修改位置 |
|------|---------|
| 调整 TLI / BQI 公式参数 | `core/tli_model.py` / `core/bqi_model.py` |
| 调整限制因子阈值 / 工程削减上下限 | `core/reduction.py` 顶部常量区 |
| 调整分级标准 / 策略建议文案 | `core/thresholds.py` |
| 调整额度 / 角色 / 速率限制 / CORS | `config.py`（或通过环境变量覆盖） |
| 新增底栖动物耐污种 | `core/bqi_model.py` → `BQI_SPECIES_TOLERANCE` 字典 |
| 新增功能页面 | `ui/pages/` 新建 `X_图标_页面名.py` |
| 新增 API 路由 | `api/routes/` 新建 Blueprint → `api/__init__.py` 注册 |
| 新增数据表 | `api/models.py` 新增 `db.Model` 子类，重启服务自动建表 |
| 更换 AI 模型供应商 | 重写 `api/services/deepseek.py` 客户端 |
| 升级向量检索（Embedding） | 重写 `api/services/kb.py` 的 `build_index / query` |
| 上传本地知识 | `knowledge_base/` 添加 `.txt/.md`，随代码一并提交 |

---

## ☁️ 部署

详见 [DEPLOY.md](DEPLOY.md)：Render（Flask 后端 API） + Streamlit Cloud（Streamlit 前端 UI）分离部署，支持无状态免费环境，也可升级 Persistent Disk 持久化。

---

## 📄 许可

本项目为 **淮河流域中心生态室 内部使用**。如需对外开源或用于其他场景，请联系项目负责人。
