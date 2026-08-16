# 部署手册：Render (Flask API) + Streamlit Cloud (Frontend)

> 架构：**前后端分离部署**，两个独立服务通过 HTTP 通信。AI Key 只存在 Render 后端，永远不暴露给浏览器。
> 
> 预计时间：30 ~ 60 分钟（含构建等待）

---

## 📋 部署前检查清单

- [ ] GitHub 仓库已推送完整代码（`api/`, `core/`, `ui/`, `config.py`, `wsgi.py`, `requirements.txt`, `.env.example`, `.gitignore` 全部在仓库中可见）
- [ ] 已获取 DeepSeek API Key（https://platform.deepseek.com/）
- [ ] GitHub 账号（Render / Streamlit Cloud 均支持 GitHub OAuth 一键登录）
- [ ] 准备 2 个随机字符串（JWT_SECRET ≥ 32 字符）

---

## 🗺️ 部署总览

```
┌──────────────────────┐      API_BASE_URL       ┌──────────────────────────┐
│   Streamlit Cloud    │ ──────────────────────► │   Render (Flask)         │
│   前端 UI 服务        │                         │   后端 API + 数据库 + AI │
│  你的应用名.streamlit │ ◄────────────────────── │   lakeeval-api.onrender  │
│      .app             │     ALLOWED_ORIGINS    │         .com             │
└──────────────────────┘    (CORS 白名单校验)    └──────────────────────────┘
```

---

## Step 1. Render 部署 Flask 后端 API

### 1.1 注册 + 创建 Web Service

1. 打开 https://render.com → **Sign Up** → 用 GitHub 账号登录（授权 `CAS-Zyh/LakeEval` 仓库访问权限）
2. 登录后点右上角 **New +** → **Web Service**
3. 在仓库列表中找到 **`CAS-Zyh/LakeEval`** → 点 **Connect**

### 1.2 填写服务配置

| 字段 | 值 | 说明 |
|------|----|------|
| **Name** | `lakeeval-api`（或自定义） | 这个名字决定了子域名：`lakeeval-api.onrender.com` |
| **Region** | `Singapore`（或离你最近的） | 影响延迟 |
| **Runtime** | `Python 3` | |
| **Branch** | `main` | |
| **Build Command** | `pip install -r requirements.txt` | |
| **Start Command** | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2` | wsgi.py 是 Render 专用入口 |
| **Instance Type** | `Free`（演示用，15 分钟休眠）或 **Starter**（$7/月，永不休眠） | 免费层首次访问需 30s 冷启动 |

### 1.3 添加 Environment Variables（核心！）

滚动到 **Environment** 区块 → **Add Environment Variable** 逐个添加：

| Key | Value Example | 必填 | 说明 |
|-----|--------------|------|------|
| `DEEPSEEK_API_KEY` | `sk-xxxxxxxxxxxxxxxxxxxxxxxx` | ✅ | 从 DeepSeek 控制台获取 |
| `JWT_SECRET` | `a1b2c3d4e5f6...`（≥ 32 位随机） | ✅ | 请自行生成，切勿泄露 |
| `FLASK_HOST` | `0.0.0.0` | ✅ | 允许 Render 外部流量接入 |
| `FLASK_PORT` | `5001` | ✅ | |
| `ALLOWED_ORIGINS` | `https://你的应用名.streamlit.app` | ⚠️ 先空着或填占位符 | **Step 2 拿到 Streamlit 域名后必须回来改！** |
| `KB_ENABLED` | `true` | ✅ | |
| `GUEST_DAILY_CHAT_LIMIT` | `5` | ✅ | 游客每日对话次数 |
| `GUEST_MAX_TOKENS` | `500` | ✅ | 游客单次 token 上限 |
| `USER_DAILY_CHAT_LIMIT` | `10` | 可选 | 普通注册用户每日对话次数 |
| `RATE_LIMIT_PER_MINUTE` | `60` | ✅ | 全局 IP 速率限制 |
| `DATABASE_URI` | `sqlite:///lake_eval.db` | ✅ | SQLite 路径（配持久磁盘后生效） |
| `DEFAULT_ADMIN_USERNAME` | `admin` | 可选 | 默认管理员用户名 |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | 可选 | 默认管理员密码（建议线上改强！） |

### 1.4 添加 Persistent Disk（保护数据库！）

> Render 免费层文件系统**每次重启重置**，不加磁盘会导致：用户注册数据、对话历史、计算记录全部丢失。

滚动到 **Disks** 区块 → **Add Disk**：

| 字段 | 值 |
|------|----|
| **Name** | `lakeeval-data` |
| **Mount Path** | `/opt/render/project/src/instance` |
| **Size** | `1 GB`（免费层额度内） |

> Render SQLite 机制：`sqlite:///lake_eval.db` 会被 Flask-SQLAlchemy 3.x 解析到 `app.instance_path` 目录，也就是 `instance/lake_eval.db`；上面的 Mount Path 正好把持久磁盘挂到这个位置，数据库就持久化了。

### 1.5 部署 + 验证

点 **Create Web Service**，等待 2~3 分钟。

**成功标志**：
- 日志出现 `Listening at: http://0.0.0.0:xxxxx`（或类似 `Booting worker`）
- 浏览器打开 `https://lakeeval-api.onrender.com/api/tli/grades`，**无需鉴权**能看到 JSON：
  ```json
  {"success":true,"data":{"贫营养":[0,30],"中营养":[30,50],...}}
  ```

如果 404，看一下 Name 字段实际是什么，地址就是 `https://<NAME>.onrender.com/api/tli/grades`。

---

## Step 2. Streamlit Cloud 部署前端 UI

### 2.1 创建 App

1. 打开 https://share.streamlit.io → **Sign in with GitHub**（同账号 `CAS-Zyh`）
2. 首次登录会要你授权 `private email` + `repo`，同意即可
3. 点 **New app**

### 2.2 填写配置

| 字段 | 值 |
|------|-----|
| **Repository** | `CAS-Zyh/LakeEval`（下拉选择） |
| **Branch** | `main` |
| **Main file path** | 手动输入：`ui/app.py`（**不是根目录 app.py！**） |
| **App URL（可自定义）** | `lakeeval` → 地址：`https://lakeeval.streamlit.app`（记下这个域名，下一大步要用） |

### 2.3 添加 Secrets（告诉前端后端在哪里！）

点 **Advanced settings...** → **Secrets** → 粘贴：

```toml
# 把 Render 的子域名换成 Step 1 实际分配给你的地址，注意后面必须带 /api
API_BASE_URL = "https://lakeeval-api.onrender.com/api"
```

> ⚠️ **必须以 `/api` 结尾**。填错会导致前端所有按钮报 "无法连接服务器"。

### 2.4 部署 + 验证

点 **Deploy**，等待 1~2 分钟。

**成功标志**：
- 浏览器跳转 `https://你的应用名.streamlit.app`，页面打开，侧边栏顶部显示 **"淮河流域中心生态室"**
- 侧栏显示身份 **"游客（游客）"**，并可展开登录面板

---

## Step 3. 回填 CORS 白名单（必须！否则跨域被拒绝）

1. 回到 **Render 控制台** → `lakeeval-api` 服务 → **Environment** 标签
2. 找到 `ALLOWED_ORIGINS`，把值改为你的 Streamlit 域名，**精确匹配**，多个用逗号分隔：
   ```
   https://lakeeval.streamlit.app
   ```
   > 如果自定义了域名（CNAME），也把那个加上：
   > ```
   > https://lakeeval.streamlit.app,https://你的自定义域名
   > ```
3. 点 **Save Changes** → Render 自动重新部署（约 1 分钟）

---

## Step 4. 端到端功能验证

用**手机流量 / 另一台电脑**访问 `https://你的应用名.streamlit.app`，按顺序测：

| 序号 | 测试项 | 操作 | 预期 |
|-----|--------|------|------|
| 1 | 游客身份 | 直接打开 | 侧栏"游客"，不要求强制登录 |
| 2 | TLI 计算 | 拖侧栏滑条 → 点击"计算" | TLI 数值 + 雷达图更新 |
| 3 | 削减方案 | 输入目标 TLI 50 → 反推 | 限制因子诊断卡 + 差异化比例 + 雷达对比图 |
| 4 | 管理员登录 | 侧栏登录 admin / admin123 | 侧栏变成"管理员（admin）" |
| 5 | AI 对话 | 进入 AI 助手 → 提问"什么是 TLI" | 流式回复文字，页面顶部显示知识库状态栏 |
| 6 | 游客额度限制 | 退出 admin 恢复游客 → 连续提问 6 次 | 第 6 次弹出"今日对话次数已达上限"错误提示 |
| 7 | 历史记录 | 完成几次计算 → 打开记录页 | 类型/TLI/BQI/削减方案可筛选，可删除单条，可导出 CSV |
| 8 | 安全 | 浏览器 F12 → Network → 找 `/chat/message` 请求 → 看 Request Headers | **不应该出现任何 `sk-` 字符串**（Key 只存在后端） |

---

## 🔄 日常更新流程（代码改动后）

**完全自动化**，只需要 push 到 GitHub main 分支即可：

```bash
cd 本地/LakeEval
git add .
git commit -m "fix: 描述改动（例如修正TP削减权重）"
git push
```

然后：
- Render：自动检测到推送 → 重新 `pip install` + 重启（1~2 分钟）
- Streamlit Cloud：自动检测到推送 → Reboot app（30 秒左右）

刷新网页看到新版本就对了。

> 如果想手动触发：Render 控制台 → Manual Deploy → Clear build cache & deploy。Streamlit 右下角 "..." → Reboot app。

### 知识库更新（特殊）
放新的 `.txt/.md` 文件到 `knowledge_base/` 目录，推送 GitHub：
```bash
git add knowledge_base/我的新文档.md
git commit -m "docs: 添加2025年淮河流域生态报告"
git push
```
Render 自动重启后加载新文档，无需重新配置。

---

## 🩺 常见故障排查

### ❌ Streamlit 打开一片红 "无法连接服务器"
**原因**：前端 API_BASE_URL 没配对，或 Render 后端还没启动好。
**修**：
1. 测后端：浏览器单独开 `https://你的render子域名.onrender.com/api/tli/grades`，能看到 JSON 才算后端活了
2. 打开 Streamlit → 右上角 "☰" → **Settings** → **Secrets**，确认 `API_BASE_URL` 值是 `https://你的render子域名.onrender.com/api`（末尾有 `/api`）
3. Secrects 改完 Streamlit 会自动 Reboot

### ❌ 点击 AI 对话没反应 / 空回复
**原因**：`DEEPSEEK_API_KEY` 没配 / CORS 白名单没填对 / 游客额度用完
**修**：
1. Render 控制台 → Environment → 检查 `DEEPSEEK_API_KEY` 真实值前后没有空格
2. 用管理员账号登录再测（admin 无限额度）
3. 浏览器 F12 → Console 报错包含 `CORS` / `Access-Control-Allow-Origin` → 回到 Render 把 `ALLOWED_ORIGINS` 改成 `https://你的前端域名`，**末尾不要加 `/`**

### ❌ 注册的用户第二天登录不存在 / 计算记录都没了
**原因**：没加 Persistent Disk，Render 重启把数据库重置了
**修**：按 **1.4 节**把磁盘挂上（`/opt/render/project/src/instance`，1GB）。⚠️ **注意：第一次挂载磁盘会清掉之前那一次启动的数据**，所以最好一开始就挂上。

### ❌ Render 日志 "unable to open database file" （SQLite 写入报错）
**原因**：实例目录没写权限，或者 Persistent Disk Mount Path 写错
**修**：检查 Mount Path 必须是 **`/opt/render/project/src/instance`**（注意是 `/opt` 不是 `/app`）。

### ❌ AI 回答不引用本地知识库
**原因**：`KB_ENABLED=false`、文档未放入正确目录、或文档内容与问题不相关
**修**：
1. 调 API `/api/chat/kb_status` 看返回的 `indexed_chunks` 是否 > 0
2. 确认文件后缀是 `.txt` 或 `.md`、编码 UTF-8
3. 降低 `KB_MIN_SCORE`（如 0.08）或提高 `KB_TOP_K`（如 5）

### ❌ 冷启动太慢（免费层通病）
Render Free 实例 15 分钟无访问会休眠，下一次访问要 20~40s 冷启动。
**缓解**：
- 自己用 UptimeRobot（免费）每 10 分钟 GET 一次 `https://lakeeval-api.onrender.com/api/tli/grades`，保持实例热乎
- 或者升级到 Render **Starter** 实例（$7/月，永不休眠）

---

## 💰 费用预估（纯免费可跑）

| 组件 | 方案 | 费用 |
|------|------|------|
| Render（API） | Free 实例 + 1GB Persistent Disk | ¥0 |
| Streamlit Cloud | Free（公开） | ¥0 |
| DeepSeek API | 按 token 消耗（看使用强度） | ~¥5~50 / 月 |
| 合计 | | **¥5 / 月起** |

如果用户量起来需要升级，Render Starter 实例 $7/月（~¥50）支持 512MB 内存 + 永不休眠。

---

## 📚 附录 A：Environment Variables 完整参考

（同 `.env.example`，线上用 Render Environment UI 填即可）

| 变量 | 默认 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | - | （必填） DeepSeek API Key，仅后端使用，前端不可见 |
| `JWT_SECRET` | - | （必填） JWT 签名密钥，请填 ≥ 32 位随机串 |
| `FLASK_PORT` | 5001 | Flask 监听端口（Render 自动注入 $PORT，此变量可能被覆盖） |
| `FLASK_HOST` | 127.0.0.1 | Render 必须设 0.0.0.0 |
| `STREAMLIT_PORT` | 8501 | Streamlit Cloud 自动控制，本地用 |
| `DATABASE_URI` | sqlite:///lake_eval.db | 数据库连接串，SQLite 用相对路径 |
| `DEFAULT_ADMIN_USERNAME` | admin | 首次启动创建 |
| `DEFAULT_ADMIN_PASSWORD` | admin123 | 线上务必改强！ |
| `GUEST_DAILY_CHAT_LIMIT` | 5 | 游客每日对话上限（按 IP） |
| `GUEST_MAX_TOKENS` | 500 | 游客单次 token 上限 |
| `GUEST_TOKEN_EXPIRY_HOURS` | 2 | 游客 JWT 有效期 |
| `USER_DAILY_CHAT_LIMIT` | 10 | 普通注册用户每日对话上限（admin 无限） |
| `ALLOWED_ORIGINS` | http://localhost:8501,... | 前端域名白名单，逗号分隔 |
| `RATE_LIMIT_PER_MINUTE` | 60 | 全局 IP 请求速率限制 |
| `KB_ENABLED` | true | 启用本地知识库 RAG |
| `KB_DIR` | knowledge_base | 知识库目录（相对项目根） |
| `KB_CHUNK_SIZE` | 600 | 切块字符数 |
| `KB_CHUNK_OVERLAP` | 80 | 重叠字符 |
| `KB_TOP_K` | 3 | 检索 TopK 块 |
| `KB_MIN_SCORE` | 0.12 | 最低相似度阈值（低于不注入） |

---

部署遇到问题，把 Render/Streamlit 的报错日志截图发出来，对照"常见故障排查"一节定位。
