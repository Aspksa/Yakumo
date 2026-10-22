"use strict";

// «Вселенная Yakumo» на вкладке «Карта»: в центре живой мозг, вокруг ваш мир звёздами, разложенными по
// галактикам жизни (семья, друзья, работа…). От нейронов мозга к звёздам тянутся нити; когда Yakumo узнаёт
// новое или вы говорите о ком-то в чате, по нити летит искра. Приближение колесом: издали видны галактики,
// ближе звёзды, совсем близко — факты, документы и обещания вокруг звезды. Есть 3D-режим с вращением и
// экскурсия, в которой Yakumo сама облетает ваш мир. Мозг показывает window.YakumoUniverse.mount(...).
(() => {
  const SVG = "http://www.w3.org/2000/svg";
  const AREA_HUE = { family: "#f0b45a", friends: "#7fd1c7", work: "#8fa8ff", home: "#f59ac0", places: "#9be07f",
                     health: "#ff8a7a", hobby: "#c79bff", other: "#c9c2b0" };
  const F = 900;            // «фокусное расстояние» для перспективы в 3D
  const FAR = 0.8;          // дальше этого (от масштаба «весь мир в окне») — видны только галактики
  const NEAR = 2.3;         // ближе — вокруг звёзд факты, документы и обещания
  const camera = { x: 0, y: 0, k: 0.9, yaw: 0, pitch: 0, d3: false, fit: true, sy: 1 };
  let base = 0.9;           // масштаб, при котором весь мир помещается в окно
  const moved = {};         // звёзды, которые вы передвинули (до перезагрузки страницы)
  const born = new Set();   // чьё рождение уже показано
  let current = null;       // смонтированная вселенная
  let seenFacts = null;     // факты, известные с прошлого показа, — по новым летят искры
  const heard = [];         // о чём говорили в чате, пока карта была закрыта: искры полетят, когда её откроют

  const el = (tag, attrs = {}, parent) => {
    const x = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) x.setAttribute(k, v);
    if (parent) parent.append(x);
    return x;
  };
  const html = (tag, cls, text) => {
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text != null) x.textContent = text;
    return x;
  };

  function rng(seed) {
    return () => {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  const hash = (s) => [...s].reduce((a, c) => Math.imul(a ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261);

  function brainPoints(n, w, hgt) {
    const inside = (x, y) => {
      const e = (cx, cy, rx, ry) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1;
      return (e(-0.24, -0.06, 0.66, 0.78) || e(0.24, -0.06, 0.66, 0.78) || e(0.5, 0.55, 0.3, 0.24)) && Math.abs(x) > 0.03;
    };
    const rand = rng(17), pts = [];
    while (pts.length < n) {
      const x = rand() * 2 - 1, y = rand() * 2 - 1;
      if (inside(x, y)) pts.push({ x: x * w * 0.42, y: y * hgt * 0.45, z: (rand() - 0.5) * 60 });
    }
    return pts;
  }

  // --- Мир: галактики, звёзды, спутники ---

  function build(m) {
    const now = Date.now() / 1000;
    const facts = m.facts.filter((f) => !f.archived);
    const about = {};
    for (const f of facts) for (const id of f.about || []) (about[id] ||= []).push(f);
    const ents = m.entities.filter((e) => (about[e.id] || []).length || e.keep);
    const areas = [...new Set(ents.map((e) => e.area || "other"))]
      .sort((a, b) => m.areas.indexOf(a) - m.areas.indexOf(b));
    const ring = 300 + areas.length * 18;
    const galaxies = areas.map((id, i) => {
      const a = -Math.PI / 2 + i / Math.max(1, areas.length) * Math.PI * 2;
      const members = ents.filter((e) => (e.area || "other") === id);
      return { id, name: m.texts.areas[id] || id, color: AREA_HUE[id] || AREA_HUE.other, members,
               x: Math.cos(a) * ring, y: Math.sin(a) * ring * 0.78, z: (i % 2 ? 1 : -1) * 140,
               r: 90 + Math.sqrt(members.length) * 38 };
    });
    const stars = [];
    for (const g of galaxies) {
      g.members.sort((a, b) => (about[b.id] || []).length - (about[a.id] || []).length);
      g.members.forEach((e, i) => {
        const list = about[e.id] || [];
        const last = Math.max(e.created || 0, ...list.map((f) => f.updated || f.created || 0));
        const first = Math.min(...list.map((f) => f.created || now), e.created || now);
        const age = (now - last) / 86400;
        // Золотая спираль вокруг центра галактики: самые «тяжёлые» звёзды ближе к центру.
        const a = i * 2.39996, d = 26 + Math.sqrt(i) * 46;
        const rand = rng(hash(e.id));
        const s = { id: e.id, e, g, facts: list, x: g.x + Math.cos(a) * d, y: g.y + Math.sin(a) * d * 0.85,
                    z: g.z + (rand() - 0.5) * 140, r: 5 + Math.min(13, Math.sqrt(list.length) * 3.6),
                    heat: age < 14 ? "hot" : age < 60 ? "warm" : "cold", fresh: now - first < 3 * 86400 };
        [s.x0, s.y0] = [s.x, s.y];
        if (moved[e.id]) [s.x, s.y] = moved[e.id];
        stars.push(s);
      });
    }
    const byId = Object.fromEntries(stars.map((s) => [s.id, s]));
    const named = stars.filter((s) => s.e.name.length >= 3).map((s) => [s, s.e.name.toLowerCase()]);
    const mentions = (text) => named.filter(([, n]) => text.toLowerCase().includes(n)).map(([s]) => s);
    // Спутники: обещания (по связи или по имени в тексте) и документы (из фактов и найденные на Диске).
    for (const s of stars) {
      s.promises = m.promises.filter((p) => !p.done && ((p.about || []).includes(s.id) || mentions(p.text).includes(s)));
      const files = new Set(s.facts.flatMap((f) => f.files || []));
      for (const p of m.docs[s.id] || []) files.add(p);
      s.docs = [...files].slice(0, 6);
    }
    // Связи между звёздами: общий факт.
    const links = [], seen = new Set();
    for (const f of facts) {
      const ids = (f.about || []).filter((id) => byId[id]);
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const key = [ids[i], ids[j]].sort().join("|");
        if (!seen.has(key)) { seen.add(key); links.push([byId[ids[i]], byId[ids[j]]]); }
      }
    }
    const neurons = brainPoints(Math.max(24, Math.min(170, m.brain.neurons || 0)), 300, 200);
    for (const s of stars) s.neuron = neurons[hash(s.id) % neurons.length];
    return { galaxies, stars, byId, links, neurons, mentions };
  }

  // --- Проекция: 2D или 3D с вращением ---

  function project(p, W, H) {
    let { x, y, z } = p;
    if (camera.d3) {
      const cy = Math.cos(camera.yaw), sy = Math.sin(camera.yaw), cp = Math.cos(camera.pitch), sp = Math.sin(camera.pitch);
      [x, z] = [x * cy + z * sy, -x * sy + z * cy];
      [y, z] = [y * cp - z * sp, y * sp + z * cp];
    } else z = 0;
    const s = F / (F + z) * camera.k;
    return { x: W / 2 + camera.x + x * s, y: H / 2 + camera.y + y * s * camera.sy, s, z };
  }

  // --- Монтирование ---

  function mount(host, m, api) {
    if (current) current.stop();
    const world = build(m);
    const T = m.texts;
    const wrap = html("div", "un-wrap");
    const svg = el("svg", { class: "un-svg", role: "img", "aria-label": T.title });
    wrap.append(svg);
    const W = () => wrap.clientWidth || 800, H = () => wrap.clientHeight || 560;
    const sky = el("g", { class: "un-sky" }, svg);
    const rand = rng(5);
    const skyStars = Array.from({ length: 160 }, () => ({ x: (rand() - 0.5) * 2600, y: (rand() - 0.5) * 2000, z: (rand() - 0.5) * 1400,
                                                          r: 0.4 + rand() * 1.1, el: null }));
    for (const s of skyStars) { s.el = el("circle", { r: s.r }, sky); s.el.style.animationDelay = `${(rand() * 6).toFixed(2)}s`; }
    const nebulae = el("g", { class: "un-nebulae" }, svg);
    for (const g of world.galaxies) {
      g.el = el("circle", { class: "un-nebula", fill: g.color }, nebulae);
      g.label = el("text", { class: "un-galaxy", fill: g.color }, nebulae);
      g.label.textContent = g.name;
    }
    const threads = el("g", { class: "un-threads" }, svg);
    for (const s of world.stars) s.thread = el("path", { stroke: s.g.color }, threads);
    const linkG = el("g", { class: "un-links" }, svg);
    for (const l of world.links) l.el = el("line", {}, linkG);
    // Мозг: нейроны — точки в мире вокруг (0, 0), связи между ближайшими.
    const brainG = el("g", { class: "un-brain" }, svg);
    const bLinks = [];
    world.neurons.forEach((p, i) => {
      if (!i) return;
      let best = 0, bd = Infinity;
      for (let j = 0; j < i; j++) { const d = Math.hypot(world.neurons[j].x - p.x, world.neurons[j].y - p.y); if (d < bd) { bd = d; best = j; } }
      if (bd < 70) bLinks.push([p, world.neurons[best], el("line", { class: i % 6 === 2 ? "pulse" : "" }, brainG)]);
    });
    for (const [i, p] of world.neurons.entries()) {
      p.el = el("circle", {}, brainG);
      p.el.style.animationDelay = `${(i * 0.29) % 4}s`;
    }
    const sats = el("g", { class: "un-sats" }, svg);
    const starsG = el("g", { class: "un-stars" }, svg);
    const sparksG = el("g", { class: "un-sparks" }, svg);
    for (const s of world.stars) {
      const g = el("g", { class: `un-star ${s.heat}` + (s.fresh && !born.has(s.id) ? " born" : "") + (api.selected === s.id ? " on" : ""),
                          tabindex: 0, role: "button", "aria-label": s.e.name }, starsG);
      born.add(s.id);
      s.halo = el("circle", { class: "halo", fill: s.g.color }, g);
      s.hit = el("circle", { class: "hit" }, g);
      s.core = el("circle", { class: "core" }, g);
      s.label = el("text", { class: "name" }, g);
      s.label.textContent = s.e.name;
      s.sub = el("text", { class: "sub" }, g);
      s.sub.textContent = s.e.relation || "";
      s.el = g;
      // Спутники у звезды: факты (точки с подписью), документы (квадраты), обещания (кружат по орбите).
      // Видны только у одной звезды — выбранной или той, что ближе к центру, — иначе вблизи всё сливается.
      const own = s.satG = el("g", { display: "none" }, sats);
      s.sat = { facts: s.facts.slice(0, 6).map((f) => {
        const t = el("g", { class: "un-fact" }, own);
        el("circle", { r: 2.4 }, t);
        const tx = el("text", {}, t);
        tx.textContent = f.text.length > 46 ? f.text.slice(0, 44) + "…" : f.text;
        el("title", {}, t).textContent = f.text;
        return t;
      }), docs: s.docs.map((p) => {
        const t = el("g", { class: "un-doc", tabindex: 0, role: "link" }, own);
        el("rect", { x: -3.5, y: -4.5, width: 7, height: 9, rx: 1.5 }, t);
        const tx = el("text", {}, t);
        tx.textContent = p.split("/").pop();
        el("title", {}, t).textContent = p;
        t.addEventListener("click", (e) => { e.stopPropagation(); api.openDoc(p); });
        return t;
      }), promises: s.promises.map((p) => {
        const t = el("g", { class: "un-promise" }, own);
        el("circle", { r: 3.2 }, t);
        const tx = el("text", {}, t);
        tx.textContent = p.text.length > 40 ? p.text.slice(0, 38) + "…" : p.text;
        el("title", {}, t).textContent = p.text + (p.due ? ` (${p.due})` : "");
        return t;
      }) };
    }
    const caption = html("div", "un-caption");
    caption.hidden = true;
    wrap.append(caption);

    // --- Кадр ---
    const sparks = [];
    let raf = 0, alive = true, dirty = true;
    const W0 = { w: 0, h: 0 };

    function frame(now) {
      if (!alive) return;
      if (!host.isConnected) { stop(); return; }
      raf = requestAnimationFrame(frame);
      const w = W(), hgt = H();
      if (w !== W0.w || hgt !== W0.h) {
        svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`); W0.w = w; W0.h = hgt; dirty = true;
        camera.sy = Math.max(1, Math.min(1.8, hgt / w * 0.9));  // на узком высоком экране мир вытягивается по высоте
        base = fit(w, hgt);
        if (camera.fit) Object.assign(camera, { x: 0, y: 0, k: base });
      }
      const animating = sparks.length || tour.on || camera.flying || world.stars.some((s) => s.promises.length) && camera.k >= nearK();
      if (!dirty && !animating) return;
      dirty = false;
      if (camera.flying) {
        const f = Math.min(1, (now - camera.flying.start) / camera.flying.ms), e = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
        for (const k of ["x", "y", "k", "yaw", "pitch"]) camera[k] = camera.flying.from[k] + (camera.flying.to[k] - camera.flying.from[k]) * e;
        if (f >= 1) { const done = camera.flying.done; camera.flying = null; done?.(); }
      }
      const P = (p) => project(p, w, hgt);
      for (const s of skyStars) {  // фон двигается медленнее — глубина
        const q = project({ x: s.x, y: s.y, z: s.z }, w, hgt);
        const px = w / 2 + (q.x - w / 2) * 0.35, py = hgt / 2 + (q.y - hgt / 2) * 0.35;
        s.el.setAttribute("cx", px.toFixed(1)); s.el.setAttribute("cy", py.toFixed(1));
      }
      const far = camera.k < base * FAR, near = camera.k >= nearK();
      wrap.dataset.zoom = far ? "far" : near ? "near" : "mid";
      for (const g of world.galaxies) {
        const q = P(g);
        g.el.setAttribute("cx", q.x.toFixed(1)); g.el.setAttribute("cy", q.y.toFixed(1)); g.el.setAttribute("r", (g.r * q.s).toFixed(1));
        g.label.setAttribute("x", q.x.toFixed(1)); g.label.setAttribute("y", (q.y - g.r * q.s * 0.75).toFixed(1));
        g.label.style.fontSize = `${Math.max(12, Math.min(22, 30 * q.s))}px`;
      }
      for (const p of world.neurons) {
        p.q = P(p);
        p.el.setAttribute("cx", p.q.x.toFixed(1)); p.el.setAttribute("cy", p.q.y.toFixed(1));
        p.el.setAttribute("r", Math.max(0.8, 1.9 * p.q.s).toFixed(2));
      }
      for (const [a, b, line] of bLinks) {
        line.setAttribute("x1", a.q.x.toFixed(1)); line.setAttribute("y1", a.q.y.toFixed(1));
        line.setAttribute("x2", b.q.x.toFixed(1)); line.setAttribute("y2", b.q.y.toFixed(1));
      }
      const order = [];
      for (const s of world.stars) {
        const q = s.q = P(s);
        s.el.setAttribute("transform", `translate(${q.x.toFixed(1)} ${q.y.toFixed(1)})`);
        const r = Math.max(2.5, s.r * Math.min(1.6, q.s));
        s.core.setAttribute("r", r.toFixed(1)); s.halo.setAttribute("r", (r * 2.2).toFixed(1)); s.hit.setAttribute("r", (r + 8).toFixed(1));
        s.label.setAttribute("y", (r + 14).toFixed(1)); s.sub.setAttribute("y", (r + 27).toFixed(1));
        s.el.style.opacity = camera.d3 ? Math.max(0.35, Math.min(1, 1.25 - q.z / 900)).toFixed(2) : "";
        const n = s.neuron.q;
        const mx = (n.x + q.x) / 2 + (q.y - n.y) * 0.12, my = (n.y + q.y) / 2 - (q.x - n.x) * 0.12;
        s.thread.setAttribute("d", `M${n.x.toFixed(1)} ${n.y.toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${q.x.toFixed(1)} ${q.y.toFixed(1)}`);
        s.curve = [n, { x: mx, y: my }, q];
        order.push(s);
        // Спутники видны только вблизи.
        const ring = r + 26 * Math.min(1.5, q.s);
        s.sat.facts.forEach((t, i, all) => {
          const a = -Math.PI / 2 + (i + 0.5) / all.length * Math.PI * 1.2 - Math.PI * 0.1;
          t.setAttribute("transform", `translate(${(q.x + Math.cos(a) * ring * 1.6).toFixed(1)} ${(q.y + Math.sin(a) * ring * 1.6).toFixed(1)})`);
        });
        s.sat.docs.forEach((t, i) => {
          const a = Math.PI * 0.75 + i * 0.32;
          t.setAttribute("transform", `translate(${(q.x + Math.cos(a) * ring * 1.15).toFixed(1)} ${(q.y + Math.sin(a) * ring * 1.15).toFixed(1)})`);
        });
        s.sat.promises.forEach((t, i, all) => {
          const a = now / 1000 * 0.6 + i / all.length * Math.PI * 2;
          t.setAttribute("transform", `translate(${(q.x + Math.cos(a) * ring * 0.9).toFixed(1)} ${(q.y + Math.sin(a) * ring * 0.55).toFixed(1)})`);
        });
      }
      const chosen = world.stars.find((s) => s.el.classList.contains("on"));
      let focusStar = chosen && Math.hypot(chosen.q.x - w / 2, chosen.q.y - hgt / 2) < Math.min(w, hgt) / 2 ? chosen : null;
      if (!focusStar && near) {
        let best = Infinity;
        for (const s of world.stars) { const d = Math.hypot(s.q.x - w / 2, s.q.y - hgt / 2); if (d < best) { best = d; focusStar = s; } }
      }
      for (const s of world.stars) s.satG.setAttribute("display", s === focusStar ? "inline" : "none");
      if (camera.d3) {  // дальние звёзды рисуются раньше ближних
        order.sort((a, b) => b.q.z - a.q.z);
        for (const s of order) starsG.append(s.el);
      }
      for (const l of world.links) {
        const [a, b] = l;
        l.el.setAttribute("x1", a.q.x.toFixed(1)); l.el.setAttribute("y1", a.q.y.toFixed(1));
        l.el.setAttribute("x2", b.q.x.toFixed(1)); l.el.setAttribute("y2", b.q.y.toFixed(1));
      }
      // Искры: из нейрона по нити к звезде.
      for (let i = sparks.length - 1; i >= 0; i--) {
        const sp = sparks[i], f = (now - sp.start) / sp.ms;
        if (f < 0) continue;
        if (f >= 1) {
          sp.el.remove();
          sp.star.el.classList.remove("flash"); void sp.star.el.getBBox?.(); sp.star.el.classList.add("flash");
          sparks.splice(i, 1);
          continue;
        }
        const [a, c, b] = sp.star.curve, u = 1 - f;
        sp.el.setAttribute("cx", (u * u * a.x + 2 * u * f * c.x + f * f * b.x).toFixed(1));
        sp.el.setAttribute("cy", (u * u * a.y + 2 * u * f * c.y + f * f * b.y).toFixed(1));
        sp.el.setAttribute("r", (2 + Math.sin(f * Math.PI) * 2.5).toFixed(1));
      }
    }

    function spark(star, delay = 0) {
      if (!star) return;
      sparks.push({ star, start: performance.now() + delay, ms: 1400, el: el("circle", { class: "un-spark", fill: star.g.color }, sparksG) });
      star.thread.classList.add("live");
      setTimeout(() => star.thread.classList.remove("live"), 2600 + delay);
    }

    // --- Управление: колесо, перетаскивание, вращение ---

    const point = (e) => {
      const r = svg.getBoundingClientRect();
      return [e.clientX - r.left, e.clientY - r.top];
    };
    const zoom = (factor, px = W() / 2, py = H() / 2) => {
      const k = Math.max(base * 0.4, Math.min(5, camera.k * factor));
      camera.fit = false;
      const ox = px - W() / 2, oy = py - H() / 2;
      camera.x = ox - (ox - camera.x) * k / camera.k;
      camera.y = oy - (oy - camera.y) * k / camera.k;
      camera.k = k;
      dirty = true;
    };
    svg.addEventListener("wheel", (e) => { e.preventDefault(); stopTour(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, ...point(e)); }, { passive: false });
    svg.addEventListener("pointerdown", (e) => {
      const starEl = e.target.closest?.(".un-star");
      const star = starEl && world.stars.find((s) => s.el === starEl);
      if (e.target.closest?.(".un-doc")) return;
      stopTour();
      svg.setPointerCapture(e.pointerId);
      const [sx, sy] = point(e);
      const start = { ...camera }, sxw = star && star.x, syw = star && star.y;
      let drag = false;
      const move = (ev) => {
        const [x, y] = point(ev);
        if (!drag && Math.hypot(x - sx, y - sy) < 4) return;
        drag = true;
        if (star && !camera.d3) {
          star.x = sxw + (x - sx) / camera.k; star.y = syw + (y - sy) / camera.k / camera.sy;
          moved[star.id] = [star.x, star.y];
        } else if (camera.d3 && !e.shiftKey) {
          camera.yaw = start.yaw + (x - sx) * 0.008;
          camera.pitch = Math.max(-1.3, Math.min(1.3, start.pitch + (y - sy) * 0.008));
        } else {
          camera.x = start.x + x - sx; camera.y = start.y + y - sy;
          camera.fit = false;
        }
        svg.classList.add("grabbing");
        dirty = true;
      };
      const up = () => {
        svg.removeEventListener("pointermove", move);
        svg.classList.remove("grabbing");
        if (!drag && star) pick(star);
      };
      svg.addEventListener("pointermove", move);
      svg.addEventListener("pointerup", up, { once: true });
      svg.addEventListener("pointercancel", () => svg.removeEventListener("pointermove", move), { once: true });
    });
    for (const s of world.stars) {
      s.el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(s); } });
    }

    // Весь мир в окне: галактики с запасом под подписи.
    function fit(w, hgt) {
      let mx = 200, my = 160;
      for (const g of world.galaxies) { mx = Math.max(mx, Math.abs(g.x) + g.r); my = Math.max(my, Math.abs(g.y) + g.r); }
      return Math.max(0.25, Math.min(1.2, w / (mx * 2 + 40), hgt / (my * camera.sy * 2 + 40)));
    }
    function nearK() { return Math.max(1.4, base * NEAR); }

    function fly(to, ms = 1200, done) {
      camera.fit = false;
      camera.flying = { from: { ...camera }, to: { ...camera, ...to }, start: performance.now(), ms, done };
      dirty = true;
    }

    function focus(star, k = 2.6) {
      const w = W(), hgt = H();
      // Где окажется звезда при новом масштабе без сдвига — и сдвигаем так, чтобы она была в центре.
      const saved = { ...camera };
      Object.assign(camera, { x: 0, y: 0, k });
      const q = project(star, w, hgt);
      Object.assign(camera, saved);
      return { x: w / 2 - q.x, y: hgt / 2 - q.y + 30, k };
    }

    function pick(star) {
      for (const s of world.stars) s.el.classList.toggle("on", s === star);
      fly(focus(star, Math.max(camera.k, nearK() * 1.15)));
      spark(star);
      api.onPick(star.id);
    }

    // --- Экскурсия ---

    const tour = { on: false, i: 0, timer: 0 };
    const tourList = () => [...world.stars].sort((a, b) => b.facts.length - a.facts.length).slice(0, 14);

    function showCaption(s) {
      caption.replaceChildren(
        html("div", "un-cap-area", s.g.name),
        html("strong", "", s.e.name + (s.e.relation && s.e.relation.toLowerCase() !== s.e.name.toLowerCase() ? ` — ${s.e.relation}` : "")),
        ...s.facts.slice(0, 3).map((f) => html("p", "", f.text)),
        s.promises.length ? html("p", "un-cap-promise", "⟡ " + s.promises[0].text) : "",
        (() => {
          const bar = html("div", "un-cap-actions");
          const next = html("button", "btn", T.next); next.type = "button"; next.onclick = () => step(1);
          const stop = html("button", "btn", T.stopTour); stop.type = "button"; stop.onclick = stopTour;
          bar.append(next, stop);
          return bar;
        })());
      caption.hidden = false;
    }

    function step(dir = 1) {
      clearTimeout(tour.timer);
      const list = tourList();
      if (!list.length) return stopTour();
      tour.i = (tour.i + dir + list.length) % list.length;
      const s = list[tour.i];
      for (const x of world.stars) x.el.classList.toggle("on", x === s);
      fly(focus(s, nearK() * 1.15), 1600, () => { spark(s); showCaption(s); });
      tour.timer = setTimeout(() => tour.on && step(1), 6500);
    }

    function startTour() {
      tour.on = true; tour.i = -1;
      wrap.classList.add("touring");
      step(1);
      tourBtn.textContent = "■";
    }

    function stopTour() {
      if (!tour.on) return;
      tour.on = false;
      clearTimeout(tour.timer);
      caption.hidden = true;
      wrap.classList.remove("touring");
      tourBtn.textContent = "▶";
      dirty = true;
    }

    // --- Кнопки ---
    const ctl = html("div", "un-ctl");
    const btn = (text, label, fn) => { const b = html("button", "un-btn", text); b.type = "button"; b.title = label; b.setAttribute("aria-label", label); b.onclick = fn; ctl.append(b); return b; };
    btn("+", T.zoomIn, () => { stopTour(); zoom(1.3); });
    btn("−", T.zoomOut, () => { stopTour(); zoom(1 / 1.3); });
    btn("⟲", T.reset, () => { stopTour(); for (const s of world.stars) { delete moved[s.id]; [s.x, s.y] = [s.x0, s.y0]; } fly({ x: 0, y: 0, k: base, yaw: 0, pitch: 0 }); camera.fit = true; });
    const d3 = btn("3D", T.d3, () => {
      camera.d3 = !camera.d3;
      d3.classList.toggle("on", camera.d3);
      fly(camera.d3 ? { yaw: 0.5, pitch: -0.35 } : { yaw: 0, pitch: 0 }, 900);
    });
    d3.classList.toggle("on", camera.d3);
    const tourBtn = btn("▶", T.tour, () => (tour.on ? stopTour() : startTour()));
    wrap.append(ctl);

    const hint = html("p", "row-hint un-hint", T.hint);
    host.replaceChildren(wrap, hint);

    // Новые факты с прошлого раза — искры к их звёздам.
    const ids = new Set(m.facts.map((f) => f.id));
    if (seenFacts) {
      let delay = 300;
      for (const f of m.facts) {
        if (seenFacts.has(f.id)) continue;
        for (const id of f.about || []) { spark(world.byId[id], delay); delay += 350; }
      }
    } else {
      let delay = 600;  // первое открытие: по искре к самым свежим звёздам
      for (const s of world.stars.filter((x) => x.heat === "hot").slice(0, 6)) { spark(s, delay); delay += 400; }
    }
    seenFacts = ids;
    let delay = 500;
    for (const text of heard.splice(0)) for (const s of world.mentions(text).slice(0, 4)) { spark(s, delay); delay += 300; }

    function stop() {
      alive = false;
      cancelAnimationFrame(raf);
      clearTimeout(tour.timer);
      if (current?.stop === stop) current = null;
    }
    raf = requestAnimationFrame(frame);
    current = {
      stop,
      // Живое небо: о ком сейчас разговор — к тому летят искры.
      mention(text) { for (const s of world.mentions(text).slice(0, 4)) spark(s); },
    };
    return current;
  }

  window.YakumoUniverse = {
    mount,
    mention(text) {
      if (!text) return;
      if (current) current.mention(text);
      else if (heard.push(text) > 20) heard.shift();
    },
  };
  document.dispatchEvent(new Event("yakumo-universe"));
})();
