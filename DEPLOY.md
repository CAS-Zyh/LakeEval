# 部署手册 · 淮河流域中心生态室 — LakeEval

> 2026-08 版本，**0 成本、无需 VISA 信用卡**。
>
> 架构：**Streamlit Cloud 单体部署**（前后端共用一个免费实例容器）
> - 前端：Streamlit UI（多页面应用，用户直接访问）
> - 后端：Flask API（作为 UI 子进程在 `127.0.0.1:5001` 启动，不对外暴露，更安全）
> - AI Key 只保存在容器内部，通过 Secrets 注入，**永远不会被发送到用户浏览器**。
>
> 如果未来有 VISA / 想做大规模稳定部署，再参考文末「附录：切换到 Render + Streamlit 分离部署」即可。

预计部署时间：20 分钟（含平台构建等待）。

---

## 0. 部署前检查清单

- [ ] GitHub 仓库 `CAS-Zyh/LakeEval` 的 `main` 分支已包含：`api/`、`core/`、`ui/`、`ui/flask_bootstrap.py`、`config.py`、`wsgi.py`、`requirements.txt`、`.gitignore`
- [ ] 已注册 **Streamlit Cloud** 账号（share.streamlit.io，支持 GitHub OAuth 登录，**不需要信用卡**）
- [ ] 准备 ≥ 1 条 ≥ 32 字符的随机字符串（JWT 密钥）；以及 AI 平台的 API Key（可选，不填 AI 助手只降级关闭对话功能，核心计算仍可使用）

---

## 1. 架构总览

```
 外部浏览器 (用户)          Streamlit Cloud 免费容器 (1 CPU / 1 GB RAM)
 ────────────────────       ──────────────────────────────────────────
 │  share.streamlit.io  │──▶│  Streamlit 进程 (前端 UI, 8501)          │
 │  (https://xxx.)      │   │    ├─ Sidebar / Pages / Components       │
 │                      │   │    ├─ 机构标题 / 演示模式横幅             │
 │                      │   │    └─ UI -> localhost:5001 (内部回环)     │
 │                      │   │                                          │
 │                      │   │       Flask 子进程 (后端 API, 127.0.0.1)  │
 │                      │   │        ├─ TLI / BQI / 削减计算            │
 │                      │   │        ├─ JWT / 额度 / 游客 Token         │
 │                      │   │        ├─ AI 助手 (调用上游平台)           │
 │                      │   │        ├─ 知识库 RAG (纯内存 TF-IDF)       │
 │                      │   │        └─ 内存 SQLite (重启重置)           │
 ────────────────────       ──────────────────────────────────────────
```

| 模式 | 费用 | 持久化 | 推荐场景 |
|------|------|--------|---------|
| **临时演示（免费）** | ¥0 / 月 | ❌ 容器休眠/重启 → 注册用户/记录/历史清空（约 7 天闲置会休眠） | 演示 / 临时评审 / 短时间展示 — **默认模式** |

> ⚠️ Streamlit Cloud 免费实例**不提供持久化磁盘**。如果需要保存注册用户和计算记录，只有两条路：
> （a）购买一台国内轻量云服务器，把 SQLite DB 文件挂载到持久盘；
> （b）切换到「附录：Render + Streamlit 分离部署」（Render 需要信用卡，最便宜 Starter + 1GB 磁盘 ~$14/月）。

---

## 2. Streamlit Cloud 单体部署（0 成本，无需 VISA）

### 2.1 登录 / 创建 App

1. 打开 <https://share.streamlit.io> → 点击 **Sign in with GitHub**（授权 CAS-Zyh 账号）
2. 同意两次授权：**GitHub 访问权限 + 读取邮箱**
3. 登录后进入 **Apps** 面板 → 点击右上角 **「New app」** 按钮

### 2.2 配置 App

按下方表格逐项填写（这是最核心的一步）：

| 字段 | 你要填的值 |
|---|---|
| **Repository** | 下拉选择：`CAS-Zyh/LakeEval` |
| **Branch** | 下拉选择：`main` |
| **Main file path** | ⚠️ **手动输入：`ui/app.py`**（不要选根目录文件！Streamlit 多页面系统的根是这个文件所在目录，否则 pages/ 侧边栏会无法显示）|
| **Advanced settings...** | 点击展开（下一步 Secrets 就在这里） |
| **Python version** | 选 `3.11` 或 `3.12` 都可以（`3.11` 兼容性更好）|

### 2.3 填入 Secrets（可选但强烈建议 3 条）

在 Advanced settings → **Secrets** 输入框里，粘贴下面内容，然后**替换等号右边的值**：

```toml
# ============================================================
# LakeEval Secrets — 单体部署模式下最低只要配置 jwt_secret
# AI Key 是可选项，不填也完全可以：TLI/BQI/削减方案/知识库/记录功能照常使用
# ============================================================

# 1. [必填] JWT 密钥：请你自己编一段 ≥ 32 字符的随机字符串（不要写在 README 里）
jwt_secret = "把这替换成≥32字符随机字符串比如我随手写的8861a1b6c09d1c8fe1c2f1a3a0b5c8d6e9f0a1b2c3d4e5f6"

# 2. [可选] AI 平台 Key — 想让 AI 助手真正对话就填；否则 AI 助手会提示未配置
#    例：deepseek_api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# deepseek_api_key = "在这填入你的Key"

# 3. [可选] 每日 AI 对话额度限制（如果你怕烧太快）— 以下都是默认值，按需改
# guest_daily_chat_limit = "5"   # 游客（未登录）每日对话次数
# user_daily_chat_limit = "10"   # 注册普通用户每日对话次数
# guest_max_tokens = "500"       # 游客每次对话 token 上限

# 4. [不用动] 以下在单体模式下保持默认值即可
# database_uri = "sqlite:///:memory:"   # 单体模式只支持内存 DB
```

> **说明**：为什么不用填 `api_base_url`？  
> 因为在**单体部署**模式下，前后端运行在同一个容器里，Flask 由 `ui/flask_bootstrap.py` 自动在 `127.0.0.1:5001` 启动，UI 直接本机回环请求 → 不需要配置外部 API 地址、不需要配置 CORS 源、不需要第二个平台账号。✅

### 2.4 点击 **「Deploy」**，等 2~5 分钟

首次构建会下载 streamlit/flask/numpy 等依赖，耐心等待。

成功标志：
- 浏览器自动跳转到 `https://<你的应用名>.streamlit.app` 页面
- 侧栏顶部显示 **「淮河流域中心生态室」** 蓝字
- 首页顶部会有 ⚠️ **「当前为临时演示模式（单体部署）」** 黄色条幅（正常现象）
- 侧栏显示「游客（游客）」身份

### 2.5 自定义域名（可选）

在 Apps 列表里 → 你这个 App 右侧点 **⋯** → **Settings** → **Custom domain** → 按提示在 DNS 服务商（如阿里云/Cloudflare）添加 CNAME 记录，然后填你的域名，Streamlit Cloud 会自动签发 HTTPS 证书。

---

## 3. 功能验证清单（部署完必跑）

| # | 项目 | 操作 | 预期 |
|---|------|------|------|
| 1 | 游客身份 | 直接打开域名 | 侧栏显示「游客」，不强制登录 |
| 2 | 无状态横幅 | 首页顶部 | ⚠️ 黄色「临时演示模式（单体部署）」提示 |
| 3 | TLI 计算 | 拖动侧栏 5 个指标滑条 → 点「计算 TLI」 | 右侧显示数值 + 雷达图 + 等级徽章 |
| 4 | 双向同步 | 先改滑条位置 → 再看右边数字框；清空数字框手动输入 → 看滑条 | 两者实时一致 |
| 5 | BQI 计算 | 下拉物种 3 种 + 填写密度 → 点计算 | BQI 值 + 分级 |
| 6 | 削减方案 | 切到「目标 TLI → 智能反推」→ 目标 60 → 开始模拟 | 限制因子（两步法诊断卡片）+ 方案表 + 对比雷达图 |
| 7 | 历史记录 | 做 2~3 次 TLI 计算 → 切到历史记录 | 列表里能看到，可导出 CSV |
| 8 | AI 助手（已填 Key） | 提问：「两步法营养限制诊断是什么」 | 流式回复 → 回复中引用了本地知识库 00_湖库富营养化专业知识 文档 |
| 9 | AI 助手（未填 Key） | 提问任何问题 | 返回「DeepSeek API Key 未配置」提示，不崩不 500 |
| 10 | 游客用量 | 连续 6 次 AI 对话（已填 Key 情况下） | 第 6 次提示「今日游客额度已用完」，不泄露 Key |

---

## 4. 日常更新流程

代码改动 → **推送到 GitHub main 即可**，Streamlit Cloud 自动 Reboot：

```bash
cd 本地/LakeEval
git add -A
git commit -m "fix: 调整TP削减权重至0.79"
git push -u origin main
```

刷新网页确认功能变化即可（Reboot 通常 30~60s 内完成，期间页面显示 reboot banner）。

### 更新知识库

把新的 `.txt/.md` 放进 `knowledge_base/` → 提交推送 → **不需要额外操作**，容器 Reboot 后 Flask 自动重新索引。

---

## 5. 常见故障排查

### ❌ 首屏红色「后端服务启动失败（单体部署模式）」
**原因**：Streamlit Cloud 容器内存不足、或第一次启动 Flask 子进程超时 30s  
**修**：
1. 右上角 **☰ → Settings → Redeploy this app**，强制重启一次
2. 如果反复失败，看错误详情（点 ☰ → **Manage app** → 看 Build logs / Runtime logs 最后 20 行贴出来）
3. 极少概率：Streamlit 免费实例的 CPU 跑满被节流，等几分钟再 Reboot 就好

### ❌ AI 助手返回「DeepSeek API Key 未配置」
**原因**：Secrets 里没填 `deepseek_api_key`，或者值前后有空格/换行  
**修**：Apps → 你的 app → **Settings → Secrets → Edit**，检查：
```toml
deepseek_api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```
（注意引号前后不要多空格，等号前后空格可选；`sk-` 后 **别**有换行）→ Save 后会自动 Reboot。

### ❌ 滑条数字框不同步（老版本遗留 bug，新版已修，但你看到）
**修**：`git push -f` 把最新代码推上去，再手动 **Redeploy this app**。

### ❌ 冷启动太慢
Streamlit Cloud 免费实例闲置约 7 天休眠（不是 15 分钟，是大约 7 天），首次访问 20~60s 冷启动，正常现象。  
**缓解**：用 UptimeRobot 等免费服务，每 3 天 GET 一次你的 `https://xxx.streamlit.app`，保持热度。

### ❌ 想保留用户注册数据和计算历史
Streamlit Cloud **不支持**持久化磁盘（免费/付费实例都无此功能），只能迁移架构：
- 方案 1：阿里云 / 腾讯云轻量云服务器（国内访问快，2核/2G 约 ¥30/月），部署 SQLite 到磁盘
- 方案 2：Render + Persistent Disk（需 VISA，约 $14/月，见附录）

### ❌ Runtime logs 里看到 `Flask 子进程未在 30s 内就绪`
首次启动 `pip install` + Flask 初始化超过 30s，导致 ui/flask_bootstrap.py 的等待超时。  
**修**：直接点击 **Redeploy this app** 重开一次即可，第二次启动所有依赖已被 Streamlit 缓存，启动速度会快很多。

---

## 6. Secrets 完整参考（Streamlit Cloud → Settings → Secrets 中写）

> 全部都是「可选」，单体模式只写 `jwt_secret` 就能跑起来。

| Secrets Key（Toml 里的字段名） | 说明 | 默认值 |
|---|---|---|
| `jwt_secret` | JWT 签名密钥（**建议必填，≥ 32 字符**） | 内置开发占位密钥 |
| `deepseek_api_key` | AI 平台 Key | 空 → AI 助手未配置模式 |
| `deepseek_base_url` | 更换 AI 供应商 Base URL | `https://api.deepseek.com` |
| `deepseek_model` | 更换模型名 | `deepseek-chat` |
| `guest_daily_chat_limit` | 游客每日 AI 对话次数上限（按 IP 分组） | `5` |
| `guest_max_tokens` | 游客单次 AI 请求最大 token | `500` |
| `user_daily_chat_limit` | 注册用户每日 AI 对话次数 | `10` |
| `database_uri` | **单体模式不要动**。要持久化需换服务器 | `sqlite:///:memory:` |
| `rate_limit_per_minute` | 全局 IP 速率 | `60` |
| `kb_enabled` | 启用知识库 | `true` |
| `allowed_origins` | CORS 白名单（逗号分隔）— 单体部署不用填 | 默认已包含 `https://*.streamlit.app` + localhost |
| `api_base_url` | **单体部署不要填**。分离部署才填，见附录 | 空 → `http://127.0.0.1:5001/api` |
| `default_admin_username` | 首次启动时自动创建的管理员用户名 | 可留空 |
| `default_admin_password` | 首次启动时自动创建的管理员密码（务必强密码） | 可留空 |

---

## 附录：切换到 Render + Streamlit 分离部署（需要 VISA，仅未来扩展用）

当出现以下情况时再切到此架构：
1. 单体模式容器资源不足（Streamlit Cloud 免费 1GB RAM 不够同时跑 AI）
2. 需要持久化保存注册用户 / 历史记录
3. 需要自定义域名 CDN / WAF 等高级配置

**步骤（仅简介，完整手册保留旧版）**：

1. **Render 部署 Flask**（需 VISA 身份验证）：
   - Runtime = Python 3，Build = `pip install -r requirements.txt`，Start = `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2`
   - Instance：Free 或 Starter
   - Environment：加 `FLASK_HOST=0.0.0.0`、`DATABASE_URI=sqlite:///:memory:`（或挂磁盘后设 `sqlite:///instance/lake_eval.db`）
   - Disks → 要持久化就 Add Disk：Mount Path = `/opt/render/project/src/instance`，Size 1GB
   - 部署完成后记下 API 地址：`https://lakeeval-api.onrender.com`

2. **Streamlit Cloud Secrets 切到分离模式**（Settings → Secrets）：
   ```toml
   jwt_secret = "和 Render 环境里的 JWT_SECRET 保持完全一致"
   deepseek_api_key = "在 Render 环境里填的话，这里就不用重复填了"
   api_base_url = "https://lakeeval-api.onrender.com/api"
   ```
   （api_base_url 结尾必须有 `/api`，无尾斜杠 `/`）

3. **回填 CORS 白名单**：回到 Render → Environment → `ALLOWED_ORIGINS` → 追加 `https://<你的Streamlit域名>.streamlit.app` → Save 重新部署。

---

部署过程中遇到任何问题，把对应平台（主要是 Streamlit Cloud Runtime Logs 或 Build Logs）**最后 30 行日志**贴出来，对照第 5 节一般都能快速定位；定位不到就发给我看 🔧。
