# 接入真实课程视频

官网的课程视频**不在代码里写死**，而是存在 `videos.url` 字段。播放器会根据这个
URL 自动选择播放方式，所以**换视频源不需要改前端代码**，只要在后台改数据。

## 两种视频源都支持

### 1. 自托管直链（推荐，最可控）

把视频放在自己的对象存储 / CDN 上，拿到直链即可：

- `https://cdn.example.com/lesson-1.mp4`（或 `.webm` / `.ogg`）
- `https://cdn.example.com/lesson-1.m3u8`（HLS，适合大课 / 自适应码率）

播放器判定规则：

| URL 特征 | 播放方式 |
|---|---|
| 以 `.m3u8` 结尾 / 含 `.m3u8?` | HLS 播放（Safari / iOS 原生；Chrome 需页面在 https 下且有原生支持） |
| 以 `.mp4` / `.webm` / `.ogg` / `.mov` / `.m4v` 结尾 | 原生 `<video>` 播放 |
| 其他 | 当作**嵌入页**，用 `<iframe>` 加载 |

> 自托管的注意点：大文件建议用 HLS 分片 + CDN；跨域播放需要视频源允许
> `Range` 请求与 CORS。若要防盗链，用**带签名的短时效 URL**（CDN 普遍支持）。

### 2. 平台播放页嵌入（最省事）

把视频传到 B 站 / 腾讯云点播 / 阿里云 VOD / YouTube 等，直接填**播放页地址**：

- `https://player.bilibili.com/player.html?bvid=...`
- `https://www.youtube.com/embed/...`

播放器会用 `<iframe>` 嵌入。**注意**：填的必须是**可嵌入的播放器页地址**
（通常是平台给出的 `embed` / `player` 地址），而不是普通网页地址，否则平台会
拒绝嵌入。

## 怎么改数据

三种方式，任选：

**A. 运营后台（网页）**：登录官网 → `/admin` → 用管理员令牌加载 → 编辑课程 / 视频。

**B. 管理 API**：

```bash
curl -X PUT https://你的官网/api/v1/admin/videos/lesson-1 \
  -H "Authorization: Bearer $AI_OPS_SITE_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"id":"lesson-1","course_id":"ops-basics","title":"第 1 讲",
       "url":"https://cdn.example.com/lesson-1.mp4","duration_s":1500}'
```

**C. 直接改 seed / 数据库**：`ai_ops_site/seed.py` 的 `VIDEOS` 列表，或更新
`videos` 表的 `url` 列。

## 安全边界（重要）

- **未购买不泄露 URL**：付费课程的视频，接口层对未购买用户**不下发 `url`**
  （只给标题、时长、`locked: true`）。播放器拿到空 URL 会显示"未配置/需购买"，
  不会暴露真实地址。
- 前端只是展示层；**真正的访问控制必须在视频源这一侧也做**。也就是说：如果视频
  放在自家对象存储/CDN，应当用**签名 URL**，让未授权者即便拿到地址也拉不到流。
  「接口不下发 URL」挡住的是顺手拿地址，不等于加密；对高价值内容，请在存储侧加签。
- 免费课程对所有登录用户可见；付费课程购买后解锁，订阅与课程权益相互独立。

## 现状

仓库里的演示数据 `url` 为空，播放器会显示"此课节尚未配置视频地址"。这是**有意为之**：
等你有真实视频后，按上面的方式填进去，播放器就会自动渲染。
