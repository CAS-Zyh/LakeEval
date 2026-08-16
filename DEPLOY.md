# 部署手册 · 淮河流域中心生态室 — LakeEval

> 架构：**前后端分离部署**，两个独立服务通过 HTTPS 通信。
> - **Render**：托管 Flask 后端 API + 计算 + AI + 数据
> - **Streamlit Cloud**：托管 Streamlit 前端 UI（多页面应用）
> - AI Key 只保存在 Render 后端，**永远不会被发送到用户浏览器**。

预计部署时间：30 ~ 60 分钟（含平台构建等待）。

---

## 0. 部署前检查清单

- [ ] GitHub 仓库 `CAS-Zyh/LakeEval` 的 `main` 分支已包含：`api/`、`core/`、`ui/`、`config.py`、`wsgi.py`、`requirements.txt`、`.gitignore`
- [ ] 已注册 **Render**（render.com）账号（支持 GitHub OAuth 登录）
- [ ] 已注册 **Streamlit Cloud**（share.streamlit.io）账号（支持 GitHub OAuth 登录）
- [ ] 准备 ≥ 2 条随机字符串：1 条 ≥ 32 字符（JWT 密钥）、1 条 AI 平台 API Key（可选，不填 AI 助手页面仅关闭对话功能）

---

## 1. 架构总览

```
用户浏览器 ──────► Streamlit Cloud (前端 UI)
                        │
                        │ HTTP (带 /api 前缀)
                        ▼
                   Render (Flask API)
                    ├─ TLI / BQI / 削减方案 计算
                    ├─ 注册/登录/额度/JWT
                    ├─ AI 对话 (调用上游平台)
                    └─ 知识库 RAG (纯内存索引)

                   [可选持久化] Render Persistent Disk
                    └─ /opt/render/project/src/instance/
                         └─ lake_eval.db   ← SQLite
```

两种运行模式：

| 模式 | 费用 | 持久化 | 推荐场景 |
|------|------|--------|---------|
| **A. 临时演示（免费无盘）** | ¥0 | ❌ 重启后注册用户/记录/历史全部清空 | 演示 / 临时评审 / 短时间展示 |
| **B. 正式运行（1GB 磁盘）** | ~¥7–15 / 月 | ✅ | 长期稳定使用 |

---

## 2. Step A · Render 部署 Flask 后端（含临时演示模式）

### 2.1 创建 Web Service

1. 打开 <https://render.com> → 用 **GitHub 账号**登录（授权 `CAS-Zyh/LakeEval` 仓库访问权限）
2. 点击右上角 **New +** → **Web Service**
3. 在仓库列表中找到 **`CAS-Zyh/LakeEval`** → 点 **Connect**

### 2.2 基础配置

| 字段 | 值 | 说明 |
|------|----|------|
| **Name** | `lakeeval-api`（或自定义） | 这个名字决定子域名：`https://<NAME>.onrender.com` |
| **Region** | `Singapore`（或离你最近的） | 影响请求延迟 |
| **Runtime** | `Python 3` | |
| **Branch** | `main` | |
| **Build Command** | `pip install -r requirements.txt` | |
| **Start Command** | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2` | |
| **Instance Type** | 免费选 `Free`（演示 15 分钟休眠）；长期运行选 `Starter`（$7/月） | Free 首次访问会冷启动 20~40s |

### 2.3 Environment Variables（必填）

滚动到 **Environment** 区块 → **Add Environment Variable** 逐个添加：

> ⚠️ **变量名区分大小写**，建议直接复制下列 Key。

| Key | 示例 Value | 说明 |
|-----|-----------|------|
| `FLASK_HOST` | `0.0.0.0` | ✅ Render 必须允许外部流量接入 |
| `FLASK_PORT` | `5001` | ✅ 本地用，线上会被 Render `$PORT` 覆盖 |
| `JWT_SECRET` | `≥32 位随机字符串` | ✅ 请自行生成并妥善保存 |
| `DEEPSEEK_API_KEY` 或对应供应商 Key | 从 AI 平台获取 | 不填则 AI 助手不工作，但 TLI/BQI/削减方案等核心功能仍然可用 |
| `ALLOWED_ORIGINS` | `http://localhost:8501,https://<你的Streamlit域名>.streamlit.app` | 先占位，拿到 Streamlit 域名后 **务必回填** |
| `RATE_LIMIT_PER_MINUTE` | `60` | 全局每分钟速率限制 |
| `KB_ENABLED` | `true` | 启用本地知识库 |

下面两项用来控制运行模式（二选一）：

#### A.1 · 临时演示模式（免费无盘）✅ 推荐第一次部署用

```
DATABASE_URI   =  sqlite:///:memory:
```
- 默认就是这个值（不填也行）
- 所有计算正常工作，AI 对话可用
- **每次 Render 重启 → 数据库重置为空白**，注册用户/记录/历史全部丢失
- UI 顶部会自动显示 ⚠️ **临时演示模式**条幅，明确告诉用户

#### A.2 · 正式运行模式（持久化）

先做下一步 2.4 挂载磁盘 → 再设置：
```
DATABASE_URI   =  sqlite:///instance/lake_eval.db
```

### 2.4 （正式模式必填）挂载 Persistent Disk

> 这是把数据库「永久保存」的唯一方法，否则 Render 每次冷启动/重启都会把磁盘清空。

滚动到 **Disks** → 点击 **Add Disk**：

| 字段 | 值 |
|------|----|
| Name | `lakeeval-db` |
| Mount Path | **`/opt/render/project/src/instance`** （必须完全一致，不能多斜杠/少斜杠） |
| Size | `1 GB`（对于 SQLite 绰绰有余） |

> **为什么是这个路径？** `sqlite:///instance/lake_eval.db` 是 Flask-SQLAlchemy 的「相对于 app.instance_path」写法；在 Render + gunicorn + wsgi.py 下，`app.instance_path` 就是项目根下的 `instance/` 目录，即 `/opt/render/project/src/instance`。

### 2.5 点击 Create Web Service，等待构建

构建成功标志：
- 日志最后出现类似 `Booting gunicorn worker with pid: ...` 或 `Listening at: http://0.0.0.0:xxxxx`
- 浏览器打开 `https://<你的NAME>.onrender.com/api/status`，返回 JSON：
  ```json
  {"success":true,"data":{"ok":true,"db_ephemeral":true,"db_uri_masked":"sqlite:///:memory:","server_time":"...Z"}}
  ```
- （正式模式）`db_ephemeral` 会是 `false`，`db_uri_masked` 会显示 `sqlite:///instance/...`

记下这个 API 根地址（例子：`https://lakeeval-api.onrender.com`），下一步 Streamlit 要用到。

---

## 3. Step B · Streamlit Cloud 部署前端 UI

### 3.1 创建 App

1. 打开 <https://share.streamlit.io> → **Sign in with GitHub**（同账号 `CAS-Zyh`）
2. 首次登录同意授权 `repo` + `private email`
3. 点击 **New app**

### 3.2 填写配置

| 字段 | 值 |
|------|-----|
| Repository | `CAS-Zyh/LakeEval`（下拉选择） |
| Branch | `main` |
| Main file path | **手动输入 `ui/app.py`**（⚠️ 不是根目录！Streamlit 多页面根是这个文件所在目录） |
| App URL（可自定义） | 比如 `huaihe-lakeeval`，最终地址是 `https://huaihe-lakeeval.streamlit.app`（记下这个） |

### 3.3 告诉前端「后端在哪里」（Secrets）

> ⚠️ 这是部署最容易出错的一步：**前端是另一个独立服务**，它必须知道后端 Render 的 API 地址。

点 **Advanced settings...** → 找到 **Secrets** 输入框 → 粘贴下面内容（替换成你自己的 Render 域名）：

```toml
# 注意：域名后必须带 /api，且末尾没有 /
API_BASE_URL = "https://lakeeval-api.onrender.com/api"
```

### 3.4 点击 Deploy

成功标志：
- 自动跳转到 `https://huaihe-lakeeval.streamlit.app` 页面
- 侧边栏顶部显示 **「淮河流域中心生态室」**
- 如果后端还是临时演示模式，首页会有 ⚠️ 黄色条幅
- 侧栏显示 **「游客」** 身份（或可展开登录面板）

---

## 4. Step C · 回填 CORS 白名单（必须）

前端域名现在确定了（比如 `https://huaihe-lakeeval.streamlit.app`），要告诉 Render 后端只允许这个域名跨域调用：

1. 回到 Render 控制台 → `lakeeval-api` 服务 → **Environment**
2. 找到 `ALLOWED_ORIGINS`，把值替换为：
   ```
   http://localhost:8501,https://huaihe-lakeeval.streamlit.app
   ```
   （如果有自定义 CNAME 域名，也一并加到逗号后面）
3. 点 **Save Changes** → Render 会自动重新部署 1 分钟

> 不填会怎样？浏览器 F12 → Console 会报红色 `CORS` / `Access-Control-Allow-Origin` 错误 → 所有需要鉴权的功能（计算记录保存、AI 对话、登录注册等）失败。

---

## 5. Step D · 功能验证清单

打开 Streamlit 前端域名，按顺序测试：

| # | 项目 | 操作 | 预期 |
|---|------|------|------|
| 1 | 游客身份 | 直接打开 | 侧栏显示「游客」，不强制登录 |
| 2 | TLI 计算 | 拖动侧栏滑条 → 点击计算 | 数值更新 + 雷达图/贡献条 |
| 3 | TLI 双向同步 | 改滑条 → 数字框同值；改数字框 → 滑条同位置 | 实时同步 |
| 4 | BQI 计算 | 填 3 种底栖 → 点击计算 | 输出 BQI 值 + 等级徽章 |
| 5 | 削减方案 | 目标 TLI 60 → 智能反推 | 限制因子诊断卡 + 方案 + 对比雷达 |
| 6 | 演示模式提示 | 首页顶部 | 临时模式 ⚠️ 条幅；正式模式无 |
| 7 | 计算记录导出 | 做几次计算 → 历史页 → 导出 CSV | CSV 下载成功 |
| 8 | AI 助手 | 提问「什么是 TLI」 | 流式回复；必要时引用本地知识库 |
| 9 | 安全 | F12 → 搜索 `sk-` 或 API Key 字符串 | **任何请求和响应都不应出现明文 Key** |

---

## 6. 日常更新流程

代码改动 → **推送到 GitHub main 即可**，两边都是自动重新部署：

```bash
cd 本地/LakeEval
git add .
git commit -m "fix: 调整削减方案中TP权重"
git push -u origin main
```

- Render：自动检测 push → 重新 `pip install` + 重启（1~3 分钟）
- Streamlit：自动 Reboot app（20~60s）

刷新网页确认版本变化。

### 知识库更新

把新的 `.txt/.md` 放进 `knowledge_base/` 目录 → 提交推送：
```bash
git add knowledge_base/我的新文档.md
git commit -m "docs: 新增淮河流域2025生态报告"
git push
```
Render 重启后自动索引，无需手动操作。

---

## 7. 常见故障排查

### ❌ Streamlit 页面一片红「无法连接服务器」
**原因**：前端 `API_BASE_URL` 填错 / 后端还在冷启动  
**修**：
1. 单独打开 `https://你的Render子域名.onrender.com/api/status`，确认返回 JSON（先等后端完成冷启动）
2. Streamlit 控制台 → Settings → Secrets → 检查 `API_BASE_URL` 必须是 `https://你的Render子域名.onrender.com/api`（**结尾有 `/api`，无尾斜杠 `/`**）
3. 保存 → Streamlit 自动 Reboot

### ❌ AI 助手回复 503「DeepSeek API Key 未配置」
**原因**：Render 环境变量 `DEEPSEEK_API_KEY` 没填、或者值前后有空格  
**修**：Render Environment 粘贴 Key 时确认没有换行或引号 → Save Changes → 重新部署后再测

### ❌ 登录 / 保存记录报错「数据保存失败（临时模式）」
**原因**：你运行在**临时演示模式**（`DATABASE_URI = sqlite:///:memory:`），DB 写操作被故意降级了，避免崩溃  
**修**：
- 临时模式就是这样的（正常的保护），**纯计算功能依然 100% 可用**；
- 需要持久化 → 跳到 2.4 挂载 Persistent Disk → 升级 `DATABASE_URI` 为 `sqlite:///instance/lake_eval.db`

### ❌ 冷启动太慢（免费层通病）
Render Free 15 分钟无流量会休眠，首次访问 20~40s。  
**缓解**：
- 用 UptimeRobot 等免费服务，每 10 分钟 GET 一次 `https://<api>/api/status`，保持实例热乎
- 或者升级到 Starter 实例（$7/月，永不休眠）

### ❌ 正式模式：注册的用户第二天不存在
**原因**：Persistent Disk 的 Mount Path 填错，数据库文件其实还是在临时文件系统里  
**修**：Mount Path 必须完全是 **`/opt/render/project/src/instance`**，同时 `DATABASE_URI = sqlite:///instance/lake_eval.db`

---

## 8. Environment Variables 完整参考

（Render 控制台 Environment 面板中填写，敏感变量永远不要写进仓库）

| Key | 默认值 | 说明 |
|-----|--------|------|
| `DATABASE_URI` | `sqlite:///:memory:` | `sqlite:///instance/lake_eval.db` 启用持久化 |
| `FLASK_HOST` | `127.0.0.1` | Render 必须设 `0.0.0.0` |
| `FLASK_PORT` | `5001` | Render 用 `$PORT` 覆盖 |
| `JWT_SECRET` | — | ≥ 32 位随机串（线上必填） |
| `DEEPSEEK_API_KEY` | — | AI 平台 Key（不填则 AI 助手降级） |
| `ALLOWED_ORIGINS` | 本地 + Streamlit 域名 | 逗号分隔，**CORS 白名单** |
| `RATE_LIMIT_PER_MINUTE` | `60` | 全局 IP 速率 |
| `GUEST_DAILY_CHAT_LIMIT` | `5` | 游客每日对话上限（按 IP 分组） |
| `USER_DAILY_CHAT_LIMIT` | `10` | 普通注册用户每日对话上限 |
| `GUEST_MAX_TOKENS` | `500` | 游客单次 token 上限 |
| `GUEST_TOKEN_EXPIRY_HOURS` | `2` | 游客 JWT 有效期 |
| `KB_ENABLED` | `true` | 启用知识库 |
| `KB_DIR` | `knowledge_base` | 知识库目录（相对项目根） |
| `KB_CHUNK_SIZE` | `600` | 切块字符 |
| `KB_CHUNK_OVERLAP` | `80` | 重叠字符 |
| `KB_TOP_K` | `3` | 检索块数 |
| `KB_MIN_SCORE` | `0.12` | 相似度阈值 |
| `DEFAULT_ADMIN_USERNAME` | （可填） | 首次启动创建的管理员用户名 |
| `DEFAULT_ADMIN_PASSWORD` | （可填） | 首次启动创建的管理员密码（线上务必为强密码） |

---

部署过程中遇到问题，把对应平台（Render / Streamlit）**最后 20 行构建/运行日志**或**错误截图**贴出来，对照第 7 节即可定位。
