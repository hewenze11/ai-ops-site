"""Seed demo content so the site is not empty on first run.

Idempotent: re-running updates the same rows. Safe to run in any environment;
it only creates catalog/hub rows, never users or entitlements.
"""
from __future__ import annotations

import json
import time

from .db import Store

COURSES = [
    {"id": "ops-basics", "title": "AI 运维入门：从 0 到 1 搭起你的运维助手", "summary":
     "讲清 Agent 辅助运维的边界与做法：执行协议、最小权限、确认模式与未知执行处置。", "price_cents": 9900,
     "cover_url": "", "sort": 10, "published": 1},
    {"id": "ops-advanced", "title": "AI 运维进阶：角色、记忆与编排", "summary":
     "多角色轮次队列、按天分层记忆、定制任务与定时调度，把助手真正用进日常流程。", "price_cents": 19900,
     "cover_url": "", "sort": 20, "published": 1},
    {"id": "ops-free-intro", "title": "免费试看：AI 运维到底解决什么问题", "summary":
     "20 分钟讲清产品定位、适用场景与不适合的场景。", "price_cents": 0,
     "cover_url": "", "sort": 5, "published": 1},
]

VIDEOS = [
    {"id": "intro-1", "course_id": "ops-free-intro", "title": "为什么要自己搭一套 AI 运维",
     "url": "https://example.com/videos/intro-1.mp4", "duration_s": 1200, "sort": 10},
    {"id": "basics-1", "course_id": "ops-basics", "title": "第 1 讲：执行协议与租约",
     "url": "https://example.com/videos/basics-1.mp4", "duration_s": 1500, "sort": 10},
    {"id": "basics-2", "course_id": "ops-basics", "title": "第 2 讲：最小权限与确认模式",
     "url": "https://example.com/videos/basics-2.mp4", "duration_s": 1800, "sort": 20},
    {"id": "adv-1", "course_id": "ops-advanced", "title": "第 1 讲：角色与串行队列",
     "url": "https://example.com/videos/adv-1.mp4", "duration_s": 2100, "sort": 10},
    {"id": "adv-2", "course_id": "ops-advanced", "title": "第 2 讲：记忆与编排",
     "url": "https://example.com/videos/adv-2.mp4", "duration_s": 2400, "sort": 20},
]

# Skill content is plain text (reference material injected into a role), exactly
# like the control service's local skills. These are the real deliverables of a
# subscription: after a subscriber pulls them, the control service injects the
# text into the bound role's context for that role to follow.
#
# `tier`: "standard" is visible to any active subscriber; "premium" is reserved
# for higher plans (kept as a flag so packaging can change without a schema bump).
SKILLS = [
    {"id": "linux-triage", "name": "Linux 故障排查清单", "tier": "standard",
     "role_ids": ["ops"], "content": """# Linux 故障排查清单

目标：在尽量少扰动生产的前提下，快速定位“慢/卡/挂了”。

## 固定顺序（从便宜到昂贵）
1. 负载概况：`uptime`（看 load 与核数关系）、`top -b -n1 | head`。
2. 内核信号：`dmesg -T | tail -50`（OOM、磁盘错、网卡错常在此）。
3. 服务日志：`journalctl -p err -n 100 --no-pager`。
4. 磁盘：`df -h`（满没满）、`df -i`（inode 满了吗）、`iostat -x 1 3`（%util、await）。
5. 内存：`free -m`、`vmstat 1 5`（si/so 非 0 说明在换页，报警）。
6. 进程：`ps aux --sort=-%cpu | head`、`ps aux --sort=-%mem | head`。
7. 网络：`ss -s`（连接数总览）、`ss -tnp state established | wc -l`。

## 护栏
- 分析默认只读。任何重启/下线/改配置都是**写操作**，必须先说清影响面并走确认流程。
- 磁盘/内存告急时，**先止损再查根因**（如清临时文件、把流量摘到其他节点），不要一边查一边让服务挂。
- 报告要分清“实测事实”与“推断”，推断附依据与置信度。
"""},
    {"id": "nginx-triage", "name": "Nginx 常见问题处置", "tier": "standard",
     "role_ids": ["ops"], "content": """# Nginx 常见问题处置

## 第一步总是先验配置
- `nginx -t` — 改任何东西之前先验证语法。
- 平滑重载：`nginx -s reload`（不中断已有连接）。

## 按现象定位
- **502/504**：不是 Nginx 本身的问题，而是上游。看 `error_log` 里的 `upstream` 与 `timed out`；查上游服务是否健康、超时设置是否过短。
- **连接数打满**：`ss -tn state established '( sport = :80 or sport = :443 )' | wc -l`，对照 `worker_connections * worker_processes` 上限。
- **慢**：先分清是 Nginx 慢还是上游慢；看 `$request_time` 与 `$upstream_response_time` 的差异。
- **配置改了不生效**：确认改的是**正在用**的那份配置（`nginx -T` 打印完整生效配置）。

## 护栏
- `nginx -s reload` 前必须先 `nginx -t`；配置错误时 reload 会失败但旧进程仍在跑，不要反复重试。
"""},
    {"id": "resource-profiling", "name": "资源画像与容量估算", "tier": "standard",
     "role_ids": ["ops"], "content": """# 资源画像与容量估算

目标：不凭空预测，用**实测**给出“这台/这套服务适合配多大”。

## 方法（尽量复用用户已有环境，不自建沙箱）
1. **判定服务类型**：看进程/镜像/监听端口/依赖连接，归到 web-api / db / cache / queue / batch / gpu-inference / media-transcode 之一。
2. **采一轮基线**：CPU、RSS、FD、连接数、IO。
3. **受控加压（仅测试环境；生产必须 confirm + 时长上限 + 一键中止）**：阶梯加压，记录 QPS / 延迟 / 错误率与资源曲线。
4. **找临界点**：哪条先拐弯（CPU 打满 / 内存陡升 / 连接耗尽），那个点就是瓶颈。
5. **给安全水位**：以实测临界点的 **60%~70%** 作为推荐运营水位，反推机器规格与副本数。

## 必须说清的三件事
- 哪部分是**实测**（可信），哪部分是**推断**（附依据与置信度）。
- 对**突发型业务**（视频转码 / AI 推理）：不做凭空预测，只给“实测临界点 + 安全水位”。
- **压测端自监控**：确认发压力的机器本身不是瓶颈，否则数据不可信。
"""},
    {"id": "burst-media-diagnosis", "name": "突发型业务“单节点被打满”诊断", "tier": "premium",
     "role_ids": ["ops"], "content": """# 突发型业务“单节点被打满”诊断

现象：多节点集群平时宽松，但**偶尔某个单节点的 pod 被 CPU/内存打满，其余节点却闲着**。
多见于视频转码 / 图片处理 / 大模型推理这类“单请求很重”的业务。

## 先分清三种根因（可并存）
| 根因 | 实测特征 |
|---|---|
| A 会话粘性 | 某副本请求数远高于其他，与它被分到的用户数一致 |
| B 单请求过重 | 各副本请求数相近，但某副本资源远高；内存呈锯齿尖峰 |
| C 缺限流 | 总量无节制上涨、无回落；单用户可无限并发 |

判定动作：把“各副本请求数”和“各副本资源占用”两条线放一起看。
- 请求数悬殊 → 偏 A；请求数接近而资源悬殊 → 偏 B；总量失控 → 偏 C。

## 分层处置（不要只甩给开发）
- **配置层（当天可做）**：负载均衡改按“真实资源权重”分发；重任务单独排队；给容器设 requests/limits。
- **代码层（治标，需开发）**：单用户并发上限；单请求大小硬上限；大任务异步化、入口只收单入队。
- **架构层（治本）**：重活轻活分离，web 层只收请求，转码/推理放独立 worker 集群 + 消息队列削峰。

## 紧急止血（正在出事时）
1. 把被打满的副本从负载均衡摘除；2. 对异常用户/来源临时限流；
3. 已 OOM 则先调 limit 或迁移 pod，先恢复服务，再谈根因。

## 输出固定三块
实测事实（可信）/ 根因判定（推断，附依据+置信度+未验证假设）/ 分层处置建议。
"""},
    {"id": "incident-comms", "name": "线上故障“用人话解释为什么”", "tier": "standard",
     "role_ids": ["ops"], "content": """# 线上故障：用人话解释“为什么”

面向不懂运维的对象（老板、产品、客服），说清三件事：

## 1. 现在是什么状态
- 哪些功能受影响、影响了谁、现在恢复了没有。
- 不要堆指标；先说“现在能不能用”。

## 2. 为什么会这样（打比方）
把技术原因翻译成日常比喻，例如：
- 单个大请求压垮一台机器 → “4 个收银台，来了个一次推一整车的顾客，排到哪个台就堵死哪个台”。
- 连接池耗尽 → “电话线全占着，新电话打不进来”。

## 3. 我们做了什么、接下来做什么
- 已采取的止血措施与效果；下一步计划与时间点。
- 明确哪些是**已确认**、哪些是**还在排查**，不夸大、不猜测地当结论。

## 护栏
- 不报未经证实的原因；不确定就说“还在排查，目前怀疑是……”。
- 不对用户宣泄、不贬低任何一方。
"""},
    {"id": "k8s-basics", "name": "Kubernetes 巡检要点", "tier": "premium",
     "role_ids": ["ops"], "content": """# Kubernetes 巡检要点

## 节点与资源
- `kubectl get nodes -o wide`：看状态、版本、内网 IP。
- `kubectl top nodes`：看节点实际压力，别只看 requests。

## 异常工作负载
- `kubectl get pods -A | grep -v Running`：非 Running 的一网打尽。
- `kubectl describe pod <name> -n <ns>`：看 Events 里的调度失败、OOMKilled、镜像拉取失败。
- `kubectl get events -A --sort-by=.lastTimestamp | tail`：最近发生了什么。

## 常见根因对照
- `OOMKilled`：limits 太小或内存泄漏 —— 先看实际用量与趋势。
- `CrashLoopBackOff`：进程起来就退，看上一轮日志 `kubectl logs --previous`。
- `Pending`：资源不够或亲和性不满足，看 describe 的调度原因。
- 镜像拉取失败：看私有仓库凭据与网络策略。

## 护栏
- 巡检默认只读；`delete`/`drain`/改副本数都是写操作，先确认影响面。
"""},
]


def seed(store: Store) -> dict:
    now = time.time()
    with store.tx() as db:
        for c in COURSES:
            db.execute(
                "INSERT INTO courses(id,title,summary,price_cents,cover_url,sort,published,created_at) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,"
                "summary=excluded.summary,price_cents=excluded.price_cents,cover_url=excluded.cover_url,"
                "sort=excluded.sort,published=excluded.published",
                (c["id"], c["title"], c["summary"], c["price_cents"], c["cover_url"], c["sort"],
                 c["published"], now))
        for v in VIDEOS:
            db.execute(
                "INSERT INTO videos(id,course_id,title,description,url,duration_s,sort) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET course_id=excluded.course_id,"
                "title=excluded.title,url=excluded.url,duration_s=excluded.duration_s,sort=excluded.sort",
                (v["id"], v["course_id"], v["title"], v.get("description", ""), v["url"],
                 v["duration_s"], v["sort"]))
        for s in SKILLS:
            # Only bump the revision when the content actually changes, so
            # re-running the seed (or a no-op restart) does not look like a
            # new bundle to subscribers.
            db.execute(
                "INSERT INTO skills(id,name,content,role_ids,tier,published,revision,updated_at) "
                "VALUES(?,?,?,?,?,1,1,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                "content=excluded.content,role_ids=excluded.role_ids,tier=excluded.tier,"
                "revision=skills.revision + (CASE WHEN skills.content<>excluded.content OR "
                "skills.name<>excluded.name OR skills.role_ids<>excluded.role_ids THEN 1 ELSE 0 END),"
                "updated_at=excluded.updated_at",
                (s["id"], s["name"], s["content"], json.dumps(s["role_ids"]), s["tier"], now))
    return {"courses": len(COURSES), "videos": len(VIDEOS), "skills": len(SKILLS)}
