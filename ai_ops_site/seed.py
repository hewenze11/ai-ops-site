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
# like the control service's local skills.
SKILLS = [
    {"id": "linux-triage", "name": "Linux 故障排查清单", "tier": "standard",
     "role_ids": [], "content":
     "# Linux 故障排查\n1. 先看 dmesg 与 journalctl -p err\n2. 磁盘: df -h / iostat\n"
     "3. 内存: free -m / vmstat\n4. 进程: ps aux --sort=-%cpu | head\n"
     "5. 网络: ss -s / ip a\n不要在生产上直接重启服务，先确认影响面。"},
    {"id": "nginx-triage", "name": "Nginx 常见问题处置", "tier": "standard",
     "role_ids": [], "content":
     "# Nginx 处置\n- 配置检查: nginx -t\n- 平滑重载: nginx -s reload\n"
     "- 502/504: 先看 upstream 健康与超时\n- 连接数: ss -tn state established | wc -l"},
    {"id": "k8s-basics", "name": "Kubernetes 巡检要点", "tier": "premium",
     "role_ids": [], "content":
     "# K8s 巡检\n- 节点: kubectl get nodes -o wide\n- 异常 Pod: kubectl get pods -A | grep -v Running\n"
     "- 事件: kubectl get events --sort-by=.lastTimestamp\n- 资源: kubectl top nodes / pods"},
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
            db.execute(
                "INSERT INTO skills(id,name,content,role_ids,tier,published,revision,updated_at) "
                "VALUES(?,?,?,?,?,1,1,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                "content=excluded.content,tier=excluded.tier,updated_at=excluded.updated_at",
                (s["id"], s["name"], s["content"], json.dumps(s["role_ids"]), s["tier"], now))
    return {"courses": len(COURSES), "videos": len(VIDEOS), "skills": len(SKILLS)}
