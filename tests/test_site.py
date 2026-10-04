"""End-to-end tests for the website backend: register -> buy -> unlock ->
subscribe -> mint key -> pull skills."""
import json

import pytest
from fastapi.testclient import TestClient

from ai_ops_site.app import create_app, Settings
from ai_ops_site.seed import seed


def make_client(tmp_path):
    settings = Settings()
    settings.db_path = str(tmp_path / "site.db")
    settings.admin_token = "test-admin-token-not-real"
    settings.payment_provider = "simulated"
    app = create_app(settings)
    seed(app.state.store)
    return TestClient(app)


def register(c, email="u@example.com", pw="password123"):
    r = c.post("/api/v1/auth/register", json={"email": email, "password": pw, "display_name": "Tester"})
    assert r.status_code == 201, r.text
    return r.json()


def test_free_course_is_unlocked_after_claim(tmp_path):
    c = make_client(tmp_path)
    cat = c.get("/api/v1/catalog").json()
    free = next(x for x in cat["courses"] if x["id"] == "ops-free-intro")
    assert free["videos"], "free course should list videos"
    assert all(not v.get("locked") for v in free["videos"]), "free course videos must be visible pre-login"

    register(c)
    o = c.post("/api/v1/orders", json={"kind": "course", "ref": "ops-free-intro"}).json()
    assert o["amount_cents"] == 0 and o["simulated"] is True
    paid = c.post(f"/api/v1/orders/{o['order_id']}/simulate-pay").json()
    assert paid["state"] == "paid"
    cat2 = c.get("/api/v1/catalog").json()
    assert next(x for x in cat2["courses"] if x["id"] == "ops-free-intro")["owned"] is True


def test_paid_course_locks_video_url_until_purchased(tmp_path):
    c = make_client(tmp_path)
    register(c)
    # Give the paid course a real video URL via the admin surface, so this test
    # checks the lock/unlock mechanism itself rather than whatever the seed ships.
    h = {"Authorization": "Bearer test-admin-token-not-real"}
    c.put("/api/v1/admin/videos/basics-1", headers=h, json={
        "id": "basics-1", "course_id": "ops-basics", "title": "第 1 讲",
        "url": "https://cdn.example/lesson-1.mp4", "duration_s": 100})
    cat = c.get("/api/v1/catalog").json()
    basics = next(x for x in cat["courses"] if x["id"] == "ops-basics")
    assert basics["owned"] is False
    assert all(v.get("locked") and v["url"] == "" for v in basics["videos"]), \
        "locked videos must not leak the url"

    o = c.post("/api/v1/orders", json={"kind": "course", "ref": "ops-basics"}).json()
    c.post(f"/api/v1/orders/{o['order_id']}/simulate-pay")
    cat2 = c.get("/api/v1/catalog").json()
    basics2 = next(x for x in cat2["courses"] if x["id"] == "ops-basics")
    assert basics2["owned"] is True
    # Nothing is locked once owned, and the configured video now carries its url.
    assert all(not v.get("locked") for v in basics2["videos"])
    lesson = next(v for v in basics2["videos"] if v["id"] == "basics-1")
    assert lesson["url"] == "https://cdn.example/lesson-1.mp4"


def test_login_and_session(tmp_path):
    c = make_client(tmp_path)
    register(c, email="a@example.com")
    c.post("/api/v1/auth/logout")
    assert c.get("/api/v1/auth/me").status_code == 401
    r = c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 200
    assert c.get("/api/v1/auth/me").json()["email"] == "a@example.com"


def test_duplicate_email_rejected(tmp_path):
    c = make_client(tmp_path)
    register(c, email="dup@example.com")
    r = c.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "password123",
                                              "display_name": "X"})
    assert r.status_code == 409


def test_wrong_password_same_message_as_unknown_email(tmp_path):
    c = make_client(tmp_path)
    register(c, email="b@example.com")
    r1 = c.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "wrongpass1"})
    r2 = c.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrongpass1"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_subscription_gates_pull_key_and_skills(tmp_path):
    c = make_client(tmp_path)
    register(c, email="sub@example.com")

    # No subscription: cannot mint a key, and the hub is closed.
    assert c.post("/api/v1/me/pull-keys", json={"label": "x"}).status_code == 402
    assert c.get("/api/v1/skills/repo", headers={"Authorization": "Bearer nope"}).status_code in (401, 403)

    o = c.post("/api/v1/orders", json={"kind": "subscription", "ref": "skills-monthly"}).json()
    c.post(f"/api/v1/orders/{o['order_id']}/simulate-pay")

    key = c.post("/api/v1/me/pull-keys", json={"label": "prod"}).json()["key"]
    assert key.startswith("aiops-sk-")

    repo = c.get("/api/v1/skills/repo", headers={"Authorization": "Bearer " + key}).json()
    assert repo["count"] >= 3
    for s in repo["skills"]:
        assert set(["id", "name", "content", "role_ids", "enabled"]).issubset(s)

    # Revoke -> hub rejects the key.
    keys = c.get("/api/v1/me/pull-keys").json()
    kid = keys[0]["id"]
    assert c.delete(f"/api/v1/me/pull-keys/{kid}").json()["revoked"] is True
    assert c.get("/api/v1/skills/repo", headers={"Authorization": "Bearer " + key}).status_code == 403


def test_pull_key_only_returned_once_and_stored_hashed(tmp_path):
    c = make_client(tmp_path)
    register(c, email="hash@example.com")
    o = c.post("/api/v1/orders", json={"kind": "subscription", "ref": "skills-monthly"}).json()
    c.post(f"/api/v1/orders/{o['order_id']}/simulate-pay")
    key = c.post("/api/v1/me/pull-keys", json={"label": "a"}).json()["key"]

    listing = c.get("/api/v1/me/pull-keys").json()
    assert all("key" not in row for row in listing), "the plaintext key must never be listed again"

    # The DB must not contain the plaintext key.
    import sqlite3
    raw = open(str(tmp_path / "site.db"), "rb").read()
    assert key.encode() not in raw


def test_admin_requires_token_and_can_list(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/api/v1/admin/users").status_code == 403
    r = c.get("/api/v1/admin/users", headers={"Authorization": "Bearer test-admin-token-not-real"})
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_admin_can_grant_subscription(tmp_path):
    c = make_client(tmp_path)
    register(c, email="grant@example.com")
    h = {"Authorization": "Bearer test-admin-token-not-real"}
    users = c.get("/api/v1/admin/users", headers=h).json()
    uid = users[0]["id"]
    assert c.post(f"/api/v1/admin/users/{uid}/grant",
                  json={"kind": "subscription", "ref": "skills-monthly", "days": 30},
                  headers=h).json()["ok"] is True
    assert c.get("/api/v1/admin/users", headers=h).json()[0]["subscribed"] is True


def test_admin_upsert_skill_shows_up_in_hub(tmp_path):
    c = make_client(tmp_path)
    register(c, email="skill@example.com")
    o = c.post("/api/v1/orders", json={"kind": "subscription", "ref": "skills-monthly"}).json()
    c.post(f"/api/v1/orders/{o['order_id']}/simulate-pay")
    key = c.post("/api/v1/me/pull-keys", json={"label": "x"}).json()["key"]

    h = {"Authorization": "Bearer test-admin-token-not-real"}
    body = {"id": "new-skill", "name": "新技能", "content": "# hi", "role_ids": [], "tier": "premium",
            "published": True}
    assert c.put("/api/v1/admin/skills/new-skill", json=body, headers=h).status_code == 200
    repo = c.get("/api/v1/skills/repo", headers={"Authorization": "Bearer " + key}).json()
    assert any(s["id"] == "new-skill" for s in repo["skills"])


def test_seed_is_idempotent(tmp_path):
    c = make_client(tmp_path)
    first = c.get("/api/v1/catalog").json()
    seed(c.app.state.store)
    second = c.get("/api/v1/catalog").json()
    assert len(first["courses"]) == len(second["courses"])


def test_health_and_site_config(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/healthz").json()["ok"] is True
    cfg = c.get("/api/v1/site/config").json()
    assert cfg["simulated_payments"] is True and "plan" in cfg
