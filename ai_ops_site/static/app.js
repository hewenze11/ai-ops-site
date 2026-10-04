// AI Ops website frontend — a tiny SPA, no build step.
// Routes: / (home), /courses, /skills, /pricing, /login, /register, /account, /admin
(() => {
  const app = document.getElementById("app");
  const navUser = document.getElementById("nav-user");
  let site = { brand: "AI Ops", github_url: "https://github.com/hewenze11/ai-ops",
               plan: { id: "skills-monthly", price_cents: 2900, days: 30 },
               simulated_payments: true };
  let me = null;

  // ---- api ----
  async function api(path, opts = {}) {
    const res = await fetch("/api/v1" + path, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...opts,
    });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || ("请求失败 (" + res.status + ")");
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function yuan(cents) { return "¥" + (cents / 100).toFixed(cents % 100 ? 2 : 0); }
  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function toast(msg, kind = "ok") {
    const el = document.getElementById("toast");
    el.textContent = msg; el.className = "toast " + kind; el.hidden = false;
    clearTimeout(el._t); el._t = setTimeout(() => (el.hidden = true), 3200);
  }
  const simNotice = () => site.simulated_payments
    ? `<div class="notice">⚠️ 当前为<b>模拟支付</b>：点击购买会直接标记已支付并解锁，用于演示完整闭环。接入真实支付网关后自动替换。</div>` : "";

  // ---- nav ----
  function renderNav() {
    document.getElementById("brand-name").textContent = site.brand;
    document.getElementById("brand-name-f").textContent = site.brand;
    document.getElementById("gh-link").href = site.github_url;
    document.getElementById("gh-link-f").href = site.github_url;
    document.getElementById("year").textContent = new Date().getFullYear();
    if (me) {
      navUser.innerHTML = `
        <a class="btn sm ghost" href="/account" data-link>我的</a>
        <button class="btn sm" id="logout">退出</button>`;
      document.getElementById("logout").onclick = async () => {
        await api("/auth/logout", { method: "POST" });
        me = null; toast("已退出"); navigate("/");
      };
    } else {
      navUser.innerHTML = `
        <a class="btn sm ghost" href="/login" data-link>登录</a>
        <a class="btn sm primary" href="/register" data-link>注册</a>`;
    }
  }

  // ---- pages ----
  const pages = {
    home() {
      const gh = esc(site.github_url);
      const demoCmd = `curl -fsSL ${gh.replace('github.com', 'raw.githubusercontent.com')}/main/deploy/install-control.sh | sudo bash`;
      const steps = [
        ["1", "注册账号", `用邮箱注册，免费。不注册也能直接看开源代码与文档。`],
        ["2", "装控制服务", "在服务器上跑一行命令，装好主服务（控制台 + 执行协议）。"],
        ["3", "接入执行端", "每台被管机器装一个 Agent，用普通账号降权运行，命令逐条可确认。"],
        ["4", "开箱即用", "订阅 Skills 库，把 Key 填进主服务，一键同步运维剧本到本地角色。"],
      ];
      const cards = [
        ["🛡️", "最小权限执行", "Agent 以普通账号降权执行，逐条人工确认；未知结果阻塞角色，绝不静默放行。"],
        ["🧠", "有记忆的运维搭子", "角色有长期记忆与上下文，越用越懂你的环境；默认只读，写操作走确认模式。"],
        ["📦", "Skills 持续更新", "把一次次排障沉淀成剧本，订阅后主服务一键拉取；不锁定、不加密、可审计。"],
        ["🔓", "开源可自托管", "主服务与执行端全部开源（AGPL-3.0），数据留在你自己的机器上。"],
      ];
      return `
      <section class="hero"><div class="wrap">
        <div class="hero-badge">AGPL-3.0 开源 · 可自托管 · 预览版</div>
        <h1>把 AI 变成你的运维搭子</h1>
        <p class="sub">开源的 AI 运维工作台：Agent 在你自己的机器上以最小权限执行，配合系统化教学课程与持续更新的 Skills 库。
          一个人，也能撑起一个团队的运维。</p>
        <div class="cta">
          <a class="btn primary lg" href="/register" data-link>免费开始</a>
          <a class="btn lg" href="/courses" data-link>浏览课程</a>
          <a class="btn ghost lg" href="${gh}" target="_blank" rel="noopener">看开源代码 ↗</a>
        </div>
        <div class="cmd" title="点击复制">
          <code id="cmdline">${esc(demoCmd)}</code>
          <button class="btn sm ghost" id="copy-cmd">复制</button>
        </div>
        <p class="muted sm">一行命令装好控制服务；执行端与部署细节见
          <a href="${gh}/blob/main/deploy/README.md" target="_blank" rel="noopener" style="color:var(--accent)">部署文档 ↗</a></p>
      </div></section>

      <section class="section"><div class="wrap">
        <h2 class="center">5 分钟上手</h2>
        <p class="muted center">从注册到让 AI 帮你干活，四步。</p>
        <div class="grid cols-4 mt-lg">
          ${steps.map(([n, t, d]) => `<div class="card step"><div class="step-num">${n}</div><h3>${t}</h3><p class="muted">${d}</p></div>`).join("")}
        </div>
      </div></section>

      <section class="section tight"><div class="wrap">
        <div class="grid cols-4">
          ${cards.map(([i, t, d]) => `<div class="card"><div class="card-icon">${i}</div><h3>${t}</h3><p class="muted">${d}</p></div>`).join("")}
        </div>
      </div></section>

      <section class="section"><div class="wrap center">
        <h2>两种买法，按需选择</h2>
        <p class="muted">课程教你方法，Skills 库让你少写重复剧本。</p>
        <div class="grid cols-2 mt-lg" style="text-align:left">
          <div class="card">
            <h3>教学课程</h3>
            <div class="price">${yuan(9900)}<small> 起</small></div>
            <p class="muted">系统讲解如何用 AI Agent 做运维，购买后永久观看。</p>
            <a class="btn" href="/courses" data-link>浏览课程</a>
          </div>
          <div class="card hl">
            <h3>Skills 会员 <span class="badge">推荐</span></h3>
            <div class="price">${yuan(site.plan.price_cents)}<small>/月</small></div>
            <p class="muted">全库 Skills 拉取权限，动态 Key，可多机、可吊销，到期自动失效。</p>
            <a class="btn primary" href="/skills" data-link>了解 Skills 库</a>
          </div>
        </div>
      </div></section>`;
    },

    async courses() {
      const cat = await api("/catalog");
      site.skill_count = cat.skill_count;
      const cards = cat.courses.map(c => `
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:start;gap:12px">
            <h3>${esc(c.title)}</h3>
            ${c.owned ? '<span class="badge live">已拥有</span>' :
              (c.price_cents === 0 ? '<span class="badge">免费</span>' : '<span class="badge">' + yuan(c.price_cents) + '</span>')}
          </div>
          <p class="muted">${esc(c.summary)}</p>
          <div class="meta muted">${c.videos.length} 节课</div>
          <div class="mt" style="display:flex;gap:8px">
            ${c.owned
              ? `<a class="btn sm primary" href="/courses/${c.id}" data-link>开始学习</a>`
              : (c.price_cents === 0
                  ? `<button class="btn sm primary" data-free="${c.id}">免费获取</button>`
                  : `<button class="btn sm primary" data-buy="${c.id}">购买课程</button>`)}
          </div>
        </div>`).join("");
      return `<section class="section"><div class="wrap">
        <h1>课程</h1><p class="muted">系统讲解如何用 AI Agent 做运维。购买后即可在线观看（占位播放器，接入真实视频后替换）。</p>
        ${simNotice()}
        <div class="grid cols-3 mt-lg">${cards || '<p class="muted">暂无课程</p>'}</div>
      </div></section>`;
    },

    async courseDetail(id) {
      const cat = await api("/catalog");
      const c = cat.courses.find(x => x.id === id);
      if (!c) return `<section class="section"><div class="wrap"><h1>课程不存在</h1><a href="/courses" data-link class="btn mt">返回课程</a></div></section>`;
      const rows = c.videos.map(v => `
        <div class="vrow">
          <div>
            <div>${v.locked ? "🔒 " : '<span class="play">▶</span> '}${esc(v.title)}</div>
            <div class="meta muted">${Math.round(v.duration_s / 60)} 分钟${v.locked ? " · 购买后解锁" : ""}</div>
          </div>
          ${v.locked ? "" : `<span class="badge live">可看</span>`}
        </div>`).join("");
      return `<section class="section"><div class="wrap">
        <a href="/courses" data-link class="muted">← 全部课程</a>
        <h1 class="mt">${esc(c.title)}</h1>
        <p class="muted">${esc(c.summary)}</p>
        ${c.owned ? "" : simNotice()}
        ${c.owned ? "" : `<div class="mt"><button class="btn primary" data-buy="${c.id}">购买后解锁全部 ${c.videos.length} 节（${yuan(c.price_cents)}）</button></div>`}
        <div class="card mt-lg">${rows}</div>
      </div></section>`;
    },

    async skills() {
      const cat = me ? await api("/catalog") : await api("/catalog");
      const subscribed = cat.subscription.subscribed;
      return `<section class="section"><div class="wrap">
        <h1>Skills 库</h1>
        <p class="muted">订阅会员后，官网会为你的账号<b>动态生成一个拉取凭证（Key）</b>；
          在你的主服务里填入该 Key，即可一键把最新 Skills 同步到本地角色。</p>
        ${simNotice()}
        <div class="grid cols-2 mt-lg">
          <div class="card hl">
            <div style="display:flex;justify-content:space-between"><h3>Skills 会员</h3>${subscribed ? '<span class="badge live">已订阅</span>' : ""}</div>
            <div class="price">${yuan(site.plan.price_cents)}<small>/月</small></div>
            <ul class="feature">
              <li>全库 Skills 拉取权限（当前 ${cat.skill_count} 个，持续更新）</li>
              <li>动态生成拉取 Key，可多台机器、可单独吊销</li>
              <li>订阅到期自动失效，不自动续费</li>
            </ul>
            ${subscribed
              ? `<a class="btn primary" href="/account" data-link>去我的账号管理 Key</a>`
              : `<button class="btn primary" data-subscribe>订阅 Skills 库</button>`}
          </div>
          <div class="card">
            <h3>它是怎么工作的</h3>
            <ol class="muted" style="padding-left:20px">
              <li>付费后，官网为你的账号生成一个拉取 Key。</li>
              <li>在你的主服务里配置 Skills 库地址与该 Key。</li>
              <li>主服务用 Key 请求官网 <code>/api/v1/skills/repo</code>。</li>
              <li>官网校验订阅有效后，返回你有权访问的 Skills。</li>
            </ol>
            <p class="muted" style="font-size:14px">Key = 订阅凭证。到期或吊销后，主服务立刻拉不动新内容。</p>
          </div>
        </div>
      </div></section>`;
    },

    pricing() {
      const p = site.plan;
      return `<section class="section"><div class="wrap center">
        <h1>定价</h1><p class="muted">课程单独购买，永久可看；Skills 库按月订阅。</p>
        ${simNotice()}
        <div class="grid cols-2 mt-lg" style="text-align:left">
          <div class="card">
            <h3>教学课程</h3>
            <div class="price">${yuan(9900)}<small> 起</small></div>
            <ul class="feature">
              <li>入门 / 进阶课程，永久观看</li>
              <li>含可复制的部署与运维做法</li>
              <li>免费试看课程</li>
            </ul>
            <a class="btn primary" href="/courses" data-link>浏览课程</a>
          </div>
          <div class="card hl">
            <h3>Skills 会员 <span class="badge">推荐</span></h3>
            <div class="price">${yuan(p.price_cents)}<small>/月</small></div>
            <ul class="feature">
              <li>全库 Skills 拉取权限</li>
              <li>动态拉取 Key，可多机、可吊销</li>
              <li>持续更新，随主服务演进</li>
            </ul>
            <button class="btn primary" data-subscribe ${me && me.subscribed ? "disabled" : ""}>${me && me.subscribed ? "已订阅" : "订阅 Skills 库"}</button>
          </div>
        </div>
      </div></section>`;
    },

    login() {
      return `<section class="section"><div class="wrap">
        <h1 class="center">登录</h1>
        <form class="form card mt-lg" id="f">
          <div class="field"><label>邮箱</label><input name="email" type="email" required autocomplete="email"></div>
          <div class="field"><label>密码</label><input name="password" type="password" required autocomplete="current-password"></div>
          <button class="btn primary" style="width:100%">登录</button>
          <p class="center muted mt">还没有账号？<a href="/register" data-link style="color:var(--accent)">注册</a></p>
        </form>
      </div></section>`;
    },

    register() {
      return `<section class="section"><div class="wrap">
        <h1 class="center">注册</h1>
        <form class="form card mt-lg" id="f">
          <div class="field"><label>昵称</label><input name="display_name" required maxlength="80"></div>
          <div class="field"><label>邮箱</label><input name="email" type="email" required autocomplete="email"></div>
          <div class="field"><label>密码（至少 8 位）</label><input name="password" type="password" required minlength="8" autocomplete="new-password"></div>
          <button class="btn primary" style="width:100%">注册</button>
          <p class="center muted mt">已有账号？<a href="/login" data-link style="color:var(--accent)">登录</a></p>
        </form>
      </div></section>`;
    },

    async account() {
      if (!me) return pages.login();
      const [ent, keys] = await Promise.all([api("/me/entitlements"), api("/me/pull-keys")]);
      const courses = ent.entitlements.filter(e => e.kind === "course").map(e =>
        `<div class="vrow"><div>📚 ${esc(e.ref)}</div><span class="badge live">已拥有</span></div>`).join("");
      const sub = ent.subscribed
        ? `<span class="badge live">有效</span> <span class="muted">到期：${new Date((ent.entitlements.find(e => e.kind === "subscription").expires_at) * 1000).toLocaleDateString()}</span>`
        : `<span class="badge">未订阅</span>`;
      const keyRows = keys.map(k => `
        <div class="vrow">
          <div>
            <div>${esc(k.label || "拉取 Key #" + k.id)} ${k.revoked_at ? '<span class="badge">已吊销</span>' : '<span class="badge live">有效</span>'}</div>
            <div class="meta muted">创建：${new Date(k.created_at * 1000).toLocaleString()}
              ${k.last_used_at ? " · 最近使用：" + new Date(k.last_used_at * 1000).toLocaleString() : ""}</div>
          </div>
          ${k.revoked_at ? "" : `<button class="btn sm danger" data-revoke="${k.id}">吊销</button>`}
        </div>`).join("");
      return `<section class="section"><div class="wrap">
        <h1>我的账号</h1>
        <p class="muted">${esc(me.email)} · ${esc(me.display_name)}</p>
        ${simNotice()}
        <div class="grid cols-2 mt-lg">
          <div class="card">
            <h3>我的课程</h3>
            ${courses || '<p class="muted">还没有购买课程。<a href="/courses" data-link style="color:var(--accent)">去看看</a></p>'}
          </div>
          <div class="card">
            <h3>Skills 会员</h3>
            <p>状态：${sub}</p>
            ${ent.subscribed ? "" : `<button class="btn primary" data-subscribe>订阅 Skills 库</button>`}
          </div>
        </div>
        <div class="card mt-lg">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
            <h3>拉取 Key</h3>
            <div style="display:flex;gap:8px">
              <input id="keylabel" placeholder="备注（如：生产机）" style="width:200px">
              <button class="btn primary" id="newkey" ${ent.subscribed ? "" : "disabled"}>生成新 Key</button>
            </div>
          </div>
          ${ent.subscribed ? `<div id="newkey-out" class="mt"></div>` : '<p class="muted">订阅 Skills 会员后可生成拉取 Key。</p>'}
          <div class="mt">${keyRows || '<p class="muted">还没有 Key。</p>'}</div>
          <p class="muted mt" style="font-size:14px">
            在你的主服务里拉取：
          </p>
          <div class="cmd"><code>python scripts/skills_sync.py --hub ${location.origin}/api/v1/skills/repo --pull-key-file /etc/ai-ops/skills.key --role ops</code></div>
          <p class="muted" style="font-size:14px">
            把上面的 Key 存到主服务机器（例如 <code>/etc/ai-ops/skills.key</code>，权限 600），
            脚本会带 <code>Authorization: Bearer &lt;key&gt;</code> 拉取并导入本地角色。也可用控制台接口
            <code>POST /api/v1/skills/sync</code>。详见主服务仓库 <code>docs/skills-sync.md</code>。
          </p>
        </div>
      </div></section>`;
    },

    async admin() {
      if (!me) return pages.login();
      return `<section class="section"><div class="wrap">
        <h1>运营后台</h1>
        <p class="muted">需要管理员令牌（在下方输入，只存当前页面内存，不落浏览器存储）。</p>
        <div class="field" style="max-width:480px"><label>管理员令牌</label>
          <div style="display:flex;gap:8px"><input id="admintoken" type="password" placeholder="admin token">
          <button class="btn primary" id="adminload">加载</button></div></div>
        <div id="admin-out" class="mt-lg"></div>
      </div></section>`;
    },
  };

  const titles = { "/": "AI Ops · AI 运维工作台", "/courses": "课程 · AI Ops", "/skills": "Skills 库 · AI Ops",
                   "/pricing": "定价 · AI Ops", "/login": "登录 · AI Ops", "/register": "注册 · AI Ops",
                   "/account": "我的 · AI Ops", "/admin": "运营后台 · AI Ops" };

  // ---- router ----
  async function render() {
    const path = location.pathname.replace(/\/+$/, "") || "/";
    renderNav();
    try {
      let html;
      if (path.startsWith("/courses/")) { html = await pages.courseDetail(path.slice("/courses/".length)); document.title = "课程 · AI Ops"; }
      else if (pages[path.slice(1)]) { html = await pages[path.slice(1)](); document.title = titles[path] || "AI Ops"; }
      else { html = await pages.home(); document.title = titles["/"]; }
      app.innerHTML = html;
      bindEvents(path);
    } catch (e) {
      app.innerHTML = `<section class="section"><div class="wrap"><h1>出错了</h1><p class="err">${esc(e.message)}</p></div></section>`;
    }
    window.scrollTo(0, 0);
  }

  function navigate(p) { history.pushState({}, "", p); render(); }
  window.addEventListener("popstate", render);
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-link]");
    if (a) { e.preventDefault(); navigate(a.getAttribute("href")); }
  });

  // ---- event wiring per page ----
  function bindEvents(path) {
    const copyBtn = document.getElementById("copy-cmd");
    if (copyBtn) copyBtn.addEventListener("click", async () => {
      const text = document.getElementById("cmdline").textContent;
      try {
        await navigator.clipboard.writeText(text);
        toast("命令已复制");
      } catch (_) {
        // Clipboard can be blocked (insecure context); select instead.
        const r = document.createRange(); r.selectNodeContents(document.getElementById("cmdline"));
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
        toast("请手动复制选中内容");
      }
    });
    const buy = (el) => el.addEventListener("click", async () => {
      try {
        const o = await api("/orders", { method: "POST", body: JSON.stringify({ kind: "course", ref: el.dataset.buy }) });
        const r = await api(`/orders/${o.order_id}/simulate-pay`, { method: "POST" });
        toast(r.state === "paid" ? "购买成功，已解锁！" : "订单已创建");
        render();
      } catch (e) { toast(e.message, "err"); }
    });
    document.querySelectorAll("[data-buy]").forEach(buy);
    document.querySelectorAll("[data-free]").forEach(el => el.addEventListener("click", async () => {
      try {
        const o = await api("/orders", { method: "POST", body: JSON.stringify({ kind: "course", ref: el.dataset.free }) });
        await api(`/orders/${o.order_id}/simulate-pay`, { method: "POST" });
        toast("已获取，开始学习！"); render();
      } catch (e) { toast(e.message, "err"); }
    }));
    document.querySelectorAll("[data-subscribe]").forEach(el => el.addEventListener("click", async () => {
      if (!me) { navigate("/login"); return; }
      try {
        const o = await api("/orders", { method: "POST", body: JSON.stringify({ kind: "subscription", ref: site.plan.id }) });
        await api(`/orders/${o.order_id}/simulate-pay`, { method: "POST" });
        me.subscribed = true; toast("订阅成功！"); render();
      } catch (e) { toast(e.message, "err"); }
    }));
    document.querySelectorAll("[data-revoke]").forEach(el => el.addEventListener("click", async () => {
      try { await api(`/me/pull-keys/${el.dataset.revoke}`, { method: "DELETE" }); toast("已吊销"); render(); }
      catch (e) { toast(e.message, "err"); }
    }));

    const f = document.getElementById("f");
    if (f) f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(f));
      const isLogin = path === "/login";
      try {
        me = await api(isLogin ? "/auth/login" : "/auth/register", { method: "POST", body: JSON.stringify(data) });
        toast(isLogin ? "登录成功" : "注册成功");
        navigate("/account");
      } catch (err) { toast(err.message, "err"); }
    });

    if (path === "/account") {
      const nk = document.getElementById("newkey");
      if (nk) nk.addEventListener("click", async () => {
        try {
          const label = document.getElementById("keylabel").value || "";
          const r = await api("/me/pull-keys", { method: "POST", body: JSON.stringify({ label }) });
          document.getElementById("newkey-out").innerHTML =
            `<div class="notice">这是你的拉取 Key，<b>只显示这一次</b>，请立刻保存到主服务：</div>
             <div class="keybox">${esc(r.key)}</div>`;
          toast("已生成 Key");
        } catch (e) { toast(e.message, "err"); }
      });
    }

    if (path === "/admin") {
      const btn = document.getElementById("adminload");
      if (btn) btn.addEventListener("click", async () => {
        const token = document.getElementById("admintoken").value;
        try {
          const [users, skills] = await Promise.all([
            fetch("/api/v1/admin/users", { headers: { Authorization: "Bearer " + token } }).then(r => r.json()),
            fetch("/api/v1/admin/skills", { headers: { Authorization: "Bearer " + token } }).then(r => r.json()),
          ]);
          if (!Array.isArray(users)) throw new Error("令牌无效或无权限");
          const urows = users.map(u => `<div class="vrow"><div><div>${esc(u.email)} <span class="muted">#${u.id}</span></div>
            <div class="meta muted">${u.subscribed ? "会员有效" : "无会员"} · Key ${u.active_pull_keys} 个 · 权益 ${u.entitlements.length} 项</div></div></div>`).join("");
          const srows = skills.map(s => `<div class="vrow"><div><div>${esc(s.name)} <span class="badge ${s.tier === 'premium' ? 'premium' : ''}">${s.tier}</span></div>
            <div class="meta muted">${esc(s.id)} · rev ${s.revision}</div></div></div>`).join("");
          document.getElementById("admin-out").innerHTML = `
            <div class="grid cols-2">
              <div class="card"><h3>用户（${users.length}）</h3>${urows || '<p class="muted">暂无</p>'}</div>
              <div class="card"><h3>Skills（${skills.length}）</h3>${srows || '<p class="muted">暂无</p>'}</div>
            </div>`;
        } catch (e) { toast(e.message, "err"); }
      });
    }
  }

  // ---- boot ----
  (async () => {
    try { site = await api("/site/config"); } catch (_) {}
    try { me = await api("/auth/me"); } catch (_) { me = null; }
    if (me && me.subscribed !== undefined) { /* ensure shape */ }
    render();
  })();
})();
