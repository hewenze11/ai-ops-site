# AI Ops 官网 + 会员后台

AI Ops 的**商业侧**：卖两样东西——**教学课程**与 **Skills 包月订阅**，并存放用户账号与权益。
和主服务（`hewenze11/ai-ops`）**刻意分开**：主服务管运维执行，这里管账号、订单与分发。

> 预览阶段（`0.1.0.dev1`）。**支付为模拟实现**，见下文「支付」。

## 它解决什么

```
用户 ──注册/购买──▶ 官网后台（本仓库）
                      │  存用户、订单、权益
                      │  订阅后为账号生成「拉取 Key」
                      ▼
用户的主服务（ai-ops 控制台）──用 Key 拉取──▶ 官网 Skills 分发 API
```

- 买**课程** → 解锁对应视频。
- 买 **Skills 订阅** → 官网为该账号**动态生成一个拉取 Key**；用户把这个 Key 填进自己的主服务，
  主服务用 `Authorization: Bearer <key>` 请求 `/api/v1/skills/repo`，拉取有权访问的 Skills。
- **Key 就是订阅凭证**：到期或吊销后，主服务立刻拉不到新内容。

## 快速开始（本机）

```sh
python -m venv .venv && . .venv/bin/activate
pip install '.[test]'
pytest -q
AI_OPS_SITE_ADMIN_TOKEN=dev-token ai-ops-site --host 127.0.0.1 --port 8090
```

打开 http://127.0.0.1:8090 —— 首次启动会**自动写入演示课程与 Skills**，可以直接注册、下单、看解锁效果。

### Docker

```sh
mkdir -p state secrets && chmod 700 secrets
python3 -c 'import secrets;print(secrets.token_urlsafe(48))' > secrets/admin_token
chmod 600 secrets/admin_token
docker compose up -d --build
# 默认 http://127.0.0.1:8090
```

## 支付

支付**没有直连任何网关**，而是走 `ai_ops_site/payment.py` 里的 `PaymentProvider` 接口：

- 现在只有 `SimulatedProvider`：下单即标记已支付并解锁，用来跑通「注册 → 购买 → 解锁 → 拉取」闭环。
  每条模拟订单都记录 `provider='simulated'`，不会被误当成真实销售。
- 接真实网关（微信支付 / 支付宝 / Stripe）时，**新增一个 provider 类**并实现
  `create_checkout` 与 `confirm_payment`（校验回调签名），再设 `AI_OPS_SITE_PAYMENT_PROVIDER`，其余代码不动。

> 页面上会明确提示当前处于模拟支付状态。

## 主要接口

**公开**
- `GET /api/v1/site/config` 站点配置（品牌、计划、是否模拟支付）
- `GET /api/v1/catalog` 课程目录（未购买的视频只给元数据、**不给 URL**）

**账号**
- `POST /api/v1/auth/register` / `login` / `logout`，`GET /api/v1/auth/me`
- `GET /api/v1/me/entitlements` 我拥有什么
- `GET/POST /api/v1/me/pull-keys`，`DELETE /api/v1/me/pull-keys/{id}` 管理拉取 Key（**明文只返回一次**）

**订单**
- `POST /api/v1/orders` 创建订单（返回支付跳转）
- `POST /api/v1/orders/{id}/simulate-pay` 模拟支付（真实网关用带签名的 webhook 替代）

**Skills 分发（拉取 Key 鉴权）**
- `GET /api/v1/skills/repo` 返回 `{id,name,content,role_ids,enabled}`，正是主服务可直接导入的形状

**运营后台（Bearer admin token）**
- `GET /api/v1/admin/users`，`POST /api/v1/admin/users/{id}/grant`
- `GET/PUT/DELETE /api/v1/admin/skills`，`PUT /api/v1/admin/courses`，`PUT /api/v1/admin/videos`
- `GET /api/v1/admin/audit`

## 安全边界

1. 密码用 PBKDF2-HMAC-SHA256（stdlib），**不存明文**；登录失败对「邮箱不存在」和「密码错误」返回同一信息，不泄露账号是否存在。
2. 会话令牌与**拉取 Key 只存哈希**；拉取 Key 明文**只在生成时返回一次**，数据库里查不到。
3. 未购买的视频接口层**不下发 URL**（不是仅前端隐藏）。
4. 管理接口独立 `admin token`；**未配置 token 时后台整体关闭**（不会出现「空 token 通行」）。
5. 默认只听 `127.0.0.1`；对外请加 TLS 反向代理。生产用 https 时设 `AI_OPS_SITE_COOKIE_SECURE=1`。

## 未完成 / 边界

- **无真实支付**（见上）。
- 无邮箱验证、找回密码、验证码。
- 单实例 SQLite，大流量需换数据库与队列（当前是预览）。
- 视频为占位 URL，需接入真实存储与鉴权播放。

## 许可证

尚未选定；当前 `LICENSE` 为 all-rights-reserved 占位，待项目所有者确定后替换。
