"""FastAPI application for the AI Ops website.

Routes are grouped:
  /api/v1/auth/*      register, login, logout, me
  /api/v1/catalog     public course catalog
  /api/v1/orders/*    create order (checkout), simulate pay, mark paid
  /api/v1/me/*        my courses, my subscription, my pull keys
  /api/v1/skills/*    the hub the control service pulls from (pull-key auth)
  /api/v1/admin/*     operator surface (separate admin token)

The frontend is served as static files at /.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .db import Store
from .payment import make_provider
from . import security as sec

# ---- configuration ---------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PLAN = "skills-monthly"
SUBSCRIPTION_DAYS = 30


class Settings:
    def __init__(self, **overrides) -> None:
        self.db_path = os.environ.get("AI_OPS_SITE_DB", "state/site.db")
        # Admin token is resolved lazily so a process that never exposes the
        # admin surface (e.g. public-only deploys, tests) can still start. Any
        # admin request without a configured token is rejected.
        self._admin_token: str | None = None
        self.payment_provider = os.environ.get("AI_OPS_SITE_PAYMENT_PROVIDER", "simulated")
        self.public_base_url = os.environ.get("AI_OPS_SITE_PUBLIC_URL", "")
        self.brand = os.environ.get("AI_OPS_SITE_BRAND", "AI Ops")
        self.github_url = os.environ.get("AI_OPS_SITE_GITHUB", "https://github.com/hewenze11/ai-ops")
        self.cookie_secure = os.environ.get("AI_OPS_SITE_COOKIE_SECURE", "0") == "1"
        for key, value in overrides.items():
            setattr(self, key, value)

    @property
    def admin_token(self) -> str:
        if self._admin_token is None:
            self._admin_token = _resolve_admin_token()
        return self._admin_token

    @admin_token.setter
    def admin_token(self, value: str) -> None:
        self._admin_token = value


def _resolve_admin_token() -> str:
    """Admin token from a file (preferred) or env. Never from a command line.

    Returns '' when unset; callers treat an empty token as "admin disabled".
    """
    path = os.environ.get("AI_OPS_SITE_ADMIN_TOKEN_FILE")
    if path and Path(path).exists():
        return Path(path).read_text().strip()
    return os.environ.get("AI_OPS_SITE_ADMIN_TOKEN", "")


# ---- request/response models ----------------------------------------------

class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(course|subscription)$")
    ref: str = Field(min_length=1, max_length=120)


class PullKeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(default="", max_length=80)


class SkillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=200_000)
    role_ids: list[str] = Field(default_factory=list, max_length=100)
    tier: str = Field(default="standard", pattern="^(standard|premium)$")
    published: bool = True


class CourseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2000)
    price_cents: int = Field(ge=0)
    cover_url: str = Field(default="", max_length=500)
    sort: int = 100
    published: bool = True


class VideoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    course_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    url: str = Field(default="", max_length=1000)
    duration_s: int = Field(default=0, ge=0)
    sort: int = 100


class GrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(course|subscription)$")
    ref: str = Field(min_length=1, max_length=120)
    days: int | None = Field(default=None, ge=1, le=3650)


def _norm_email(email: str) -> str:
    return email.strip().lower()


# ---- app factory -----------------------------------------------------------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings.db_path)
    provider = make_provider(settings.payment_provider)

    app = FastAPI(title="AI Ops Site", docs_url="/api/docs", openapi_url="/api/openapi.json",
                  redoc_url=None)
    app.state.settings = settings
    app.state.store = store
    app.state.provider = provider

    # First run on an empty database: load the demo catalog so the site is not
    # blank. Controlled by AI_OPS_SITE_AUTOSEED (default on).
    if os.environ.get("AI_OPS_SITE_AUTOSEED", "1") == "1":
        from .seed import seed as _seed
        with store.tx() as _db:
            empty = _db.execute("SELECT COUNT(*) AS n FROM courses").fetchone()["n"] == 0
        if empty:
            _seed(store)

    # ----- session helpers --------------------------------------------------

    def current_user(request: Request) -> dict:
        token = request.cookies.get("session")
        if not token:
            raise HTTPException(401, "Not signed in")
        th = sec.token_hash(token)
        with store.tx() as db:
            row = db.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>?", (th, sec.now())).fetchone()
            if row is None:
                raise HTTPException(401, "Session expired")
            return dict(row)

    def optional_user(request: Request) -> dict | None:
        try:
            return current_user(request)
        except HTTPException:
            return None

    def require_admin(request: Request) -> None:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        import hmac
        configured = settings.admin_token
        # An unset token disables the admin surface entirely (never "empty == open").
        if not configured or not token or not hmac.compare_digest(token, configured):
            raise HTTPException(403, "Invalid admin credential")

    def user_has_subscription(db, user_id: int) -> bool:
        row = db.execute(
            "SELECT 1 FROM entitlements WHERE user_id=? AND kind='subscription' "
            "AND (expires_at IS NULL OR expires_at>?)", (user_id, sec.now())).fetchone()
        return row is not None

    def grant_entitlement(db, user_id: int, kind: str, ref: str, days: int | None = None) -> None:
        expires = None
        if days is not None:
            # Extend from the later of now or an existing expiry (renewal stacks).
            cur = db.execute(
                "SELECT expires_at FROM entitlements WHERE user_id=? AND kind=? AND ref=?",
                (user_id, kind, ref)).fetchone()
            base = sec.now()
            if cur and cur["expires_at"] and cur["expires_at"] > base:
                base = cur["expires_at"]
            expires = base + days * 86400
        db.execute(
            "INSERT INTO entitlements(user_id,kind,ref,granted_at,expires_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(user_id,kind,ref) DO UPDATE SET expires_at=excluded.expires_at",
            (user_id, kind, ref, sec.now(), expires))

    def serialize_user(u: dict) -> dict:
        return {"id": u["id"], "email": u["email"], "display_name": u["display_name"],
                "created_at": u["created_at"]}

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie("session", token, max_age=sec.SESSION_TTL_SECONDS,
                            httponly=True, samesite="lax", secure=settings.cookie_secure,
                            path="/")

    # ----- auth -------------------------------------------------------------

    @app.post("/api/v1/auth/register", status_code=201)
    def register(body: RegisterIn, response: Response):
        email = _norm_email(body.email)
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(422, "invalid email")
        with store.tx() as db:
            if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                raise HTTPException(409, "email already registered")
            cur = db.execute(
                "INSERT INTO users(email,password_hash,display_name,created_at) VALUES(?,?,?,?)",
                (email, sec.hash_password(body.password), body.display_name.strip(), sec.now()))
            uid = cur.lastrowid
            token = sec.new_session_token()
            db.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                       (sec.token_hash(token), uid, sec.now(), sec.now() + sec.SESSION_TTL_SECONDS))
            store.audit(db, email, "user.registered", str(uid))
            user = dict(db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        set_session_cookie(response, token)
        return serialize_user(user)

    @app.post("/api/v1/auth/login")
    def login(body: LoginIn, response: Response):
        email = _norm_email(body.email)
        with store.tx() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if row is None or not sec.verify_password(body.password, row["password_hash"]):
                # Same message for both cases: do not reveal which emails exist.
                raise HTTPException(401, "email or password is incorrect")
            token = sec.new_session_token()
            db.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                       (sec.token_hash(token), row["id"], sec.now(), sec.now() + sec.SESSION_TTL_SECONDS))
            store.audit(db, email, "user.logged_in", str(row["id"]))
            payload = serialize_user(dict(row))
        set_session_cookie(response, token)
        return payload

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response):
        token = request.cookies.get("session")
        if token:
            with store.tx() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (sec.token_hash(token),))
        response.delete_cookie("session", path="/")
        return {"ok": True}

    @app.get("/api/v1/auth/me")
    def me(user: dict = Depends(current_user)):
        with store.tx() as db:
            subscribed = user_has_subscription(db, user["id"])
        return {**serialize_user(user), "subscribed": subscribed}

    # ----- catalog ----------------------------------------------------------

    @app.get("/api/v1/catalog")
    def catalog(user: dict | None = Depends(optional_user)):
        owned = set()
        subscribed = False
        if user:
            with store.tx() as db:
                owned = {r["ref"] for r in db.execute(
                    "SELECT ref FROM entitlements WHERE user_id=? AND kind='course'", (user["id"],))}
                subscribed = user_has_subscription(db, user["id"])
        with store.tx() as db:
            courses = [dict(r) for r in db.execute(
                "SELECT * FROM courses WHERE published=1 ORDER BY sort, id")]
            videos = [dict(r) for r in db.execute(
                "SELECT id,course_id,title,description,duration_s,sort,url FROM videos ORDER BY sort, id")]
            skill_count = db.execute(
                "SELECT COUNT(*) AS n FROM skills WHERE published=1").fetchone()["n"]
        by_course: dict[str, list] = {}
        free_ids = {c["id"] for c in courses if c["price_cents"] == 0}
        for v in videos:
            if v["course_id"] in owned or v["course_id"] in free_ids:
                by_course.setdefault(v["course_id"], []).append(v)
            else:
                # Locked: expose metadata (so the page can tease) but NOT the url.
                by_course.setdefault(v["course_id"], []).append(
                    {**v, "url": "", "locked": True})
        for c in courses:
            c["owned"] = c["id"] in owned
            c["videos"] = by_course.get(c["id"], [])
        return {"courses": courses, "skill_count": skill_count,
                "subscription": {"plan": DEFAULT_PLAN, "subscribed": subscribed},
                "brand": settings.brand, "github_url": settings.github_url}

    # ----- orders -----------------------------------------------------------

    def _price_for(db, kind: str, ref: str) -> tuple[int, str]:
        if kind == "course":
            row = db.execute("SELECT price_cents,title FROM courses WHERE id=? AND published=1",
                             (ref,)).fetchone()
            if row is None:
                raise HTTPException(404, "course not found")
            return row["price_cents"], row["title"]
        if kind == "subscription":
            if ref != DEFAULT_PLAN:
                raise HTTPException(404, "plan not found")
            return int(os.environ.get("AI_OPS_SITE_PLAN_PRICE_CENTS", "2900")), "Skills 会员（月）"
        raise HTTPException(422, "unknown order kind")

    @app.post("/api/v1/orders", status_code=201)
    def create_order(body: OrderIn, user: dict = Depends(current_user)):
        with store.tx() as db:
            amount, title = _price_for(db, body.kind, body.ref)
            order_id = uuid.uuid4().hex
            checkout = provider.create_checkout(order_id, amount, title)
            db.execute(
                "INSERT INTO orders(id,user_id,kind,ref,amount_cents,state,provider,provider_ref,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (order_id, user["id"], body.kind, body.ref, amount, "created",
                 checkout.provider, checkout.provider_ref, sec.now()))
            store.audit(db, user["email"], "order.created", order_id,
                        {"kind": body.kind, "ref": body.ref, "amount_cents": amount,
                         "provider": checkout.provider})
        return {"order_id": order_id, "amount_cents": amount, "title": title,
                "provider": checkout.provider, "redirect_url": checkout.redirect_url,
                "simulated": checkout.provider == "simulated"}

    def _settle(db, order: dict, actor: str) -> dict:
        if order["state"] == "paid":
            return order
        if not provider.confirm_payment(order["provider_ref"] or ""):
            raise HTTPException(402, "payment not confirmed by provider")
        db.execute("UPDATE orders SET state='paid',paid_at=? WHERE id=?", (sec.now(), order["id"]))
        days = SUBSCRIPTION_DAYS if order["kind"] == "subscription" else None
        grant_entitlement(db, order["user_id"], order["kind"], order["ref"], days=days)
        if order["kind"] == "subscription":
            store.audit(db, actor, "subscription.granted", order["ref"],
                        {"user_id": order["user_id"], "days": SUBSCRIPTION_DAYS})
        store.audit(db, actor, "order.paid", order["id"], {"amount_cents": order["amount_cents"]})
        return dict(db.execute("SELECT * FROM orders WHERE id=?", (order["id"],)).fetchone())

    @app.post("/api/v1/orders/{order_id}/simulate-pay")
    def simulate_pay(order_id: str, user: dict = Depends(current_user)):
        """Stand-in for a gateway callback. Only valid for the simulated provider;
        a real provider would expose a signed webhook instead."""
        with store.tx() as db:
            row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if row is None or row["user_id"] != user["id"]:
                raise HTTPException(404, "order not found")
            if row["provider"] != "simulated":
                raise HTTPException(400, "this order is not simulated; pay via its provider")
            order = _settle(db, dict(row), user["email"])
        return {"order_id": order_id, "state": order["state"]}

    @app.get("/api/v1/orders")
    def my_orders(user: dict = Depends(current_user)):
        with store.tx() as db:
            rows = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
                              (user["id"],)).fetchall()
        return [dict(r) for r in rows]

    # ----- my stuff ---------------------------------------------------------

    @app.get("/api/v1/me/entitlements")
    def my_entitlements(user: dict = Depends(current_user)):
        with store.tx() as db:
            ent = [dict(r) for r in db.execute(
                "SELECT * FROM entitlements WHERE user_id=? ORDER BY granted_at DESC", (user["id"],))]
            subscribed = user_has_subscription(db, user["id"])
        return {"entitlements": ent, "subscribed": subscribed, "plan": DEFAULT_PLAN}

    @app.get("/api/v1/me/pull-keys")
    def list_pull_keys(user: dict = Depends(current_user)):
        with store.tx() as db:
            rows = db.execute(
                "SELECT id,label,created_at,revoked_at,last_used_at FROM pull_keys "
                "WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        return [dict(r) for r in rows]

    @app.post("/api/v1/me/pull-keys", status_code=201)
    def create_pull_key(body: PullKeyIn, user: dict = Depends(current_user)):
        """Mint a Skills pull key. Requires an active subscription."""
        with store.tx() as db:
            if not user_has_subscription(db, user["id"]):
                raise HTTPException(402, "an active Skills subscription is required")
            key = sec.new_pull_key()
            db.execute("INSERT INTO pull_keys(user_id,key_hash,label,created_at) VALUES(?,?,?,?)",
                       (user["id"], sec.token_hash(key), body.label.strip(), sec.now()))
            store.audit(db, user["email"], "pullkey.created", body.label or str(user["id"]))
        # The plaintext key is returned exactly once.
        return {"key": key, "label": body.label.strip(),
                "note": "This key is shown once. Store it in your control service."}

    @app.delete("/api/v1/me/pull-keys/{key_id}")
    def revoke_pull_key(key_id: int, user: dict = Depends(current_user)):
        with store.tx() as db:
            cur = db.execute("UPDATE pull_keys SET revoked_at=? WHERE id=? AND user_id=? AND revoked_at IS NULL",
                             (sec.now(), key_id, user["id"]))
            if not cur.rowcount:
                raise HTTPException(404, "key not found or already revoked")
            store.audit(db, user["email"], "pullkey.revoked", str(key_id))
        return {"revoked": True}

    # ----- skills hub (pull-key auth) --------------------------------------

    def _authenticate_pull_key(request: Request) -> dict:
        header = request.headers.get("authorization", "")
        key = header[7:] if header.lower().startswith("bearer ") else ""
        if not key:
            raise HTTPException(401, "missing pull key")
        kh = sec.token_hash(key)
        with store.tx() as db:
            row = db.execute(
                "SELECT * FROM pull_keys WHERE key_hash=? AND revoked_at IS NULL", (kh,)).fetchone()
            if row is None:
                raise HTTPException(403, "invalid or revoked pull key")
            if not user_has_subscription(db, row["user_id"]):
                raise HTTPException(402, "subscription expired")
            db.execute("UPDATE pull_keys SET last_used_at=? WHERE id=?", (sec.now(), row["id"]))
            return dict(row)

    @app.get("/api/v1/skills/repo")
    def pull_skills(request: Request):
        """The endpoint a subscriber's control service calls.

        Returns skills in exactly the shape the control service imports:
        {id,name,content,role_ids,enabled}, plus a bundle revision.
        """
        pk = _authenticate_pull_key(request)
        with store.tx() as db:
            rows = db.execute(
                "SELECT id,name,content,role_ids,revision FROM skills "
                "WHERE published=1 ORDER BY id").fetchall()
            skills = [{"id": r["id"], "name": r["name"], "content": r["content"],
                       "role_ids": json.loads(r["role_ids"]), "enabled": True,
                       "revision": r["revision"]} for r in rows]
        bundle_rev = max([s["revision"] for s in skills], default=0)
        return {"bundle_revision": bundle_rev, "count": len(skills), "skills": skills,
                "user_id": pk["user_id"]}

    # ----- admin ------------------------------------------------------------

    @app.get("/api/v1/admin/skills", dependencies=[Depends(require_admin)])
    def admin_list_skills():
        with store.tx() as db:
            return [dict(r) for r in db.execute("SELECT * FROM skills ORDER BY id")]

    @app.put("/api/v1/admin/skills/{skill_id}", dependencies=[Depends(require_admin)])
    def admin_upsert_skill(skill_id: str, body: SkillIn):
        if skill_id != body.id:
            raise HTTPException(422, "skill id mismatch")
        with store.tx() as db:
            db.execute(
                "INSERT INTO skills(id,name,content,role_ids,tier,published,revision,updated_at) "
                "VALUES(?,?,?,?,?,?,1,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name,content=excluded.content,"
                "role_ids=excluded.role_ids,tier=excluded.tier,published=excluded.published,"
                "revision=skills.revision+1,updated_at=excluded.updated_at",
                (body.id, body.name, body.content, json.dumps(body.role_ids), body.tier,
                 int(body.published), sec.now()))
            store.audit(db, "admin", "skill.upserted", skill_id, {"tier": body.tier})
            return dict(db.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone())

    @app.delete("/api/v1/admin/skills/{skill_id}", dependencies=[Depends(require_admin)])
    def admin_delete_skill(skill_id: str):
        with store.tx() as db:
            if not db.execute("DELETE FROM skills WHERE id=?", (skill_id,)).rowcount:
                raise HTTPException(404, "skill not found")
            store.audit(db, "admin", "skill.deleted", skill_id)
        return {"deleted": True}

    @app.put("/api/v1/admin/courses/{course_id}", dependencies=[Depends(require_admin)])
    def admin_upsert_course(course_id: str, body: CourseIn):
        if course_id != body.id:
            raise HTTPException(422, "course id mismatch")
        with store.tx() as db:
            db.execute(
                "INSERT INTO courses(id,title,summary,price_cents,cover_url,sort,published,created_at) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,"
                "price_cents=excluded.price_cents,cover_url=excluded.cover_url,sort=excluded.sort,"
                "published=excluded.published",
                (body.id, body.title, body.summary, body.price_cents, body.cover_url, body.sort,
                 int(body.published), sec.now()))
            store.audit(db, "admin", "course.upserted", course_id)
        return {"id": course_id, "ok": True}

    @app.put("/api/v1/admin/videos/{video_id}", dependencies=[Depends(require_admin)])
    def admin_upsert_video(video_id: str, body: VideoIn):
        if video_id != body.id:
            raise HTTPException(422, "video id mismatch")
        with store.tx() as db:
            if db.execute("SELECT 1 FROM courses WHERE id=?", (body.course_id,)).fetchone() is None:
                raise HTTPException(422, "course_id does not exist")
            db.execute(
                "INSERT INTO videos(id,course_id,title,description,url,duration_s,sort) "
                "VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET course_id=excluded.course_id,title=excluded.title,"
                "description=excluded.description,url=excluded.url,duration_s=excluded.duration_s,"
                "sort=excluded.sort",
                (body.id, body.course_id, body.title, body.description, body.url,
                 body.duration_s, body.sort))
            store.audit(db, "admin", "video.upserted", video_id)
        return {"id": video_id, "ok": True}

    @app.get("/api/v1/admin/users", dependencies=[Depends(require_admin)])
    def admin_users():
        with store.tx() as db:
            users = []
            for u in db.execute("SELECT id,email,display_name,created_at FROM users ORDER BY id"):
                ent = [dict(r) for r in db.execute(
                    "SELECT kind,ref,expires_at FROM entitlements WHERE user_id=?", (u["id"],))]
                keys = db.execute("SELECT COUNT(*) AS n FROM pull_keys WHERE user_id=? AND revoked_at IS NULL",
                                  (u["id"],)).fetchone()["n"]
                users.append({**dict(u), "entitlements": ent, "active_pull_keys": keys,
                              "subscribed": any(e["kind"] == "subscription" and
                                                (e["expires_at"] is None or e["expires_at"] > sec.now())
                                                for e in ent)})
        return users

    @app.post("/api/v1/admin/users/{user_id}/grant", dependencies=[Depends(require_admin)])
    def admin_grant(user_id: int, body: GrantIn):
        """Manual grant / fix-up (support, comps, refunds)."""
        with store.tx() as db:
            if db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone() is None:
                raise HTTPException(404, "user not found")
            grant_entitlement(db, user_id, body.kind, body.ref, days=body.days)
            store.audit(db, "admin", "entitlement.granted", f"{body.kind}:{body.ref}",
                        {"user_id": user_id, "days": body.days})
        return {"ok": True}

    @app.get("/api/v1/admin/audit", dependencies=[Depends(require_admin)])
    def admin_audit(limit: int = 100):
        limit = max(1, min(limit, 500))
        with store.tx() as db:
            rows = db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ----- static frontend --------------------------------------------------

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "brand": settings.brand}

    @app.get("/api/v1/site/config")
    def site_config():
        return {"brand": settings.brand, "github_url": settings.github_url,
                "plan": {"id": DEFAULT_PLAN, "days": SUBSCRIPTION_DAYS,
                         "price_cents": int(os.environ.get("AI_OPS_SITE_PLAN_PRICE_CENTS", "2900"))},
                "payment_provider": provider.name,
                "simulated_payments": provider.name == "simulated"}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def static_files(path: str):
        # Serve real files; unknown paths fall back to the SPA shell so client
        # routes like /pricing work on a hard refresh.
        candidate = (STATIC_DIR / path).resolve()
        if STATIC_DIR.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")

    return app
