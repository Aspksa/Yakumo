"use strict";

// Главная страница — живые обои: настоящая 3D-галактика на весь экран (WebGL, three.js из vendor/).
// Рукава галактики — области жизни, в ядре — мозг Yakumo, звёзды — люди, места и дела. Звёзды разные:
// близкие — жёлтые солнца, новые — голубые гиганты, давние — красные карлики. Срочные обещания летят
// кометами, забытое кружит у чёрной дыры (её можно вытащить обратно), новые факты падают метеорами.
// Мышь вращает, колесо приближает, WASD и Q/E летают, двойной щелчок — гиперпрыжок к звезде.
(() => {
  const Y = window.Yakumo;
  if (!Y?.setHome) return;
  const AREA_HUE = { family: "#f0b45a", friends: "#7fd1c7", work: "#8fa8ff", home: "#f59ac0", places: "#9be07f",
                     health: "#ff8a7a", hobby: "#c79bff", other: "#c9c2b0" };
  const STAR_HUE = { hot: "#ffd47a", warm: "#fff1d8", cold: "#ff7f5e", fresh: "#9cc8ff" };
  const QUALITY = { low: { dust: 6000, sky: 2500, ratio: 1 }, medium: { dust: 16000, sky: 5000, ratio: 1.5 },
                    high: { dust: 34000, sky: 9000, ratio: 2 } };
  const R = 620;  // радиус галактики в единицах мира
  const TX = {
    ru: { loading: "Галактика загружается…", empty: "Ваша галактика пока пуста. Расскажите Yakumo о близких, делах и местах — здесь зажгутся звёзды.",
          noGl: "Объёмная галактика не запустилась на этой видеокарте.", quality: "Качество",
          q: { auto: "Авто", low: "Низкое", medium: "Среднее", high: "Высокое" }, reset: "К центру", help: "Подсказка",
          hint: "Мышь — вращать, колесо — ближе и дальше, WASD и Q/E — лететь (Shift — быстрее), двойной щелчок по звезде — прыжок к ней.",
          facts: (n) => `Фактов: ${n}`, promises: "Обещания", docs: "Документы", ask: "Спросить Yakumo", open: "Открыть в Мозге",
          close: "Закрыть", forgotten: "Забыто: всё о звезде ушло в архив.", recall: "Вернуть из чёрной дыры",
          dragOut: "Звезду можно вытащить из чёрной дыры мышью.", askAbout: (n) => `Что ты знаешь о «${n}»?`,
          comet: "срок скоро", supernova: "много нового", hole: "Чёрная дыра забытого",
          areas: { family: "Семья", friends: "Друзья", work: "Работа", home: "Дом и питомцы", places: "Места",
                   health: "Здоровье", hobby: "Увлечения", other: "Другое" }, core: "Yakumo" },
    en: { loading: "Loading the galaxy…", empty: "Your galaxy is empty so far. Tell Yakumo about your people, work and places, and stars will light up here.",
          noGl: "The 3D galaxy could not start on this graphics card.", quality: "Quality",
          q: { auto: "Auto", low: "Low", medium: "Medium", high: "High" }, reset: "To the centre", help: "Help",
          hint: "Drag to rotate, wheel to zoom, WASD and Q/E to fly (Shift — faster), double-click a star to jump to it.",
          facts: (n) => `Facts: ${n}`, promises: "Promises", docs: "Documents", ask: "Ask Yakumo", open: "Open in Brain",
          close: "Close", forgotten: "Forgotten: everything about this star is archived.", recall: "Pull out of the black hole",
          dragOut: "You can drag the star out of the black hole.", askAbout: (n) => `What do you know about "${n}"?`,
          comet: "due soon", supernova: "lots of news", hole: "Black hole of forgotten things",
          areas: { family: "Family", friends: "Friends", work: "Work", home: "Home & pets", places: "Places",
                   health: "Health", hobby: "Hobbies", other: "Other" }, core: "Yakumo" },
  };
  const L = new Proxy({}, { get: (_t, k) => (TX[Y.lang()] || TX.ru)[k] });
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* без памяти браузера */ } },
  };
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function rng(seed) {
    return () => {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  const hash = (s) => [...String(s)].reduce((a, c) => Math.imul(a ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261);
  const el = (tag, cls, text) => { const x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; };

  // --- three.js подгружается только для главной ---
  let threeReady = null;
  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    threeReady ||= new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = "/modules/brain/vendor/three.min.js";
      s.onload = () => (window.THREE ? ok(window.THREE) : fail(new Error("three")));
      s.onerror = fail;
      document.head.append(s);
    });
    return threeReady;
  }

  // --- Мир из данных «Мозга» ---
  function buildWorld(d) {
    const now = Date.now() / 1000;
    const about = {}, live = {};
    for (const f of d.facts) for (const id of f.about || []) {
      (about[id] ||= []).push(f);
      if (!f.archived) (live[id] ||= []).push(f);
    }
    const ents = d.entities.filter((e) => (about[e.id] || []).length);
    const forgotten = ents.filter((e) => !(live[e.id] || []).length);
    const shining = ents.filter((e) => (live[e.id] || []).length);
    const order = d.areas || Object.keys(AREA_HUE);
    const areas = [...new Set(shining.map((e) => e.area || "other"))].sort((a, b) => order.indexOf(a) - order.indexOf(b));
    const arms = Math.max(2, areas.length);
    const stars = [];
    areas.forEach((area, ai) => {
      const members = shining.filter((e) => (e.area || "other") === area)
        .sort((a, b) => live[b.id].length - live[a.id].length);
      members.forEach((e, j) => {
        const list = live[e.id];
        const last = Math.max(e.created || 0, ...list.map((f) => f.updated || f.created || 0));
        const first = Math.min(e.created || now, ...list.map((f) => f.created || now));
        const age = (now - last) / 86400;
        const rand = rng(hash(e.id));
        // Логарифмическая спираль: «тяжёлые» звёзды ближе к ядру своего рукава.
        const t = 0.18 + 0.78 * (j + 0.5 + rand() * 0.4) / (members.length + 0.6);
        const r = 110 + t * (R - 110);
        const a = ai / arms * Math.PI * 2 + r * 0.0062 + (rand() - 0.5) * 0.28;
        const recent = list.filter((f) => now - (f.created || 0) < 2 * 86400).length;
        stars.push({
          id: e.id, e, area, facts: list, all: about[e.id],
          pos: [Math.cos(a) * r, (rand() - 0.5) * 34 * (1 - t * 0.5), Math.sin(a) * r],
          kind: now - first < 3 * 86400 ? "fresh" : age < 14 ? "hot" : age < 90 ? "warm" : "cold",
          size: 26 + Math.min(42, Math.sqrt(list.length) * 11),
          nova: recent >= 3,
        });
      });
    });
    // Забытые звёзды кружат вокруг чёрной дыры.
    const hole = [R * 1.45, -40, -R * 0.55];
    const lost = forgotten.map((e, i) => {
      const rand = rng(hash(e.id));
      return { id: e.id, e, area: e.area || "other", facts: [], all: about[e.id], lost: true, kind: "cold", size: 20,
               orbit: { r: 70 + rand() * 70, a: i * 2.4, speed: 0.12 + rand() * 0.1, tilt: (rand() - 0.5) * 0.6 }, pos: [...hole] };
    });
    const byId = Object.fromEntries([...stars, ...lost].map((s) => [s.id, s]));
    const names = stars.filter((s) => s.e.name.length >= 3).map((s) => [s, s.e.name.toLowerCase()]);
    // Срочные обещания — кометы к своей звезде.
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const comets = [];
    for (const p of d.promises || []) {
      if (p.done || !p.due) continue;
      const days = (new Date(p.due + "T12:00") - today) / 86400000;
      if (days > 3 || days < -1) continue;
      const target = (p.about || []).map((id) => byId[id]).find((s) => s && !s.lost)
        || names.find(([, n]) => p.text.toLowerCase().includes(n))?.[0];
      if (target) comets.push({ p, target, seed: hash(p.id || p.text) });
    }
    // Созвездия событий: факт о трёх и больше звёздах соединяет их.
    const constellations = [];
    for (const f of d.facts) {
      if (f.archived) continue;
      const members = [...new Set(f.about || [])].map((id) => byId[id]).filter((s) => s && !s.lost);
      if (members.length >= 3) constellations.push({ f, members });
    }
    constellations.splice(12);
    // Actual pairwise links from facts, capped to avoid drawing dense graphs.
    const edges = [], seenEdges = new Set();
    for (const f of d.facts) {
      if (f.archived || edges.length >= 180) continue;
      const ids = [...new Set(f.about || [])].filter(id => byId[id] && !byId[id].lost).slice(0, 6);
      for (let i = 0; i < ids.length && edges.length < 180; i++)
        for (let j = i + 1; j < ids.length && edges.length < 180; j++) {
          const key = [String(ids[i]), String(ids[j])].sort().join("|");
          if (seenEdges.has(key)) continue;
          seenEdges.add(key);
          edges.push({from: byId[ids[i]], to: byId[ids[j]], created: f.created || 0});
        }
    }
    return { areas, arms, stars, lost, hole, byId, comets, constellations, edges };
  }

  // Project sectors are summaries of real API records, not invented neurons.
  function projectSectors(d) {
    const mind = d.mind || {}, evolution = d.evolution || {};
    const list = [
      {id:"memory",name:"Память",color:"#f2d6a1",count:(d.facts||[]).length,href:"#/brain"},
      {id:"mind",name:"Разум",color:"#c79bff",count:(mind.thoughts||[]).length,href:"#/brain"},
      {id:"growth",name:"Рост",color:"#7cdbb1",count:(d.lessons||[]).length+(d.suggestions||[]).length,href:"#/brain"},
      {id:"skills",name:"Навыки",color:"#f8ca85",count:(d.skills||[]).length+(d.user_tools||[]).length,href:"#/brain"},
      {id:"improve",name:"Улучшения",color:"#ff9c90",count:(d.improvements||[]).length,href:"#/brain"},
      {id:"evolution",name:"Эволюция",color:"#8fb0ff",count:evolution.total_generations||0,href:"#/brain"},
      {id:"code",name:"Код проекта",color:"#75b9ce",count:Array.isArray(d.code?.files)?d.code.files.length:Math.max(0,Number(d.code?.files||d.code?.file_count||0)||0),href:"#/brain"}
    ];
    return list.map((item,i)=>({...item,pos:[Math.cos(i*Math.PI*2/list.length)*980,85,Math.sin(i*Math.PI*2/list.length)*980]}));
  }

  function drawProvenanceLinks(gl,d) {
    const T=gl.THREE, sectors=projectSectors(d), lookup=Object.fromEntries(sectors.map(x=>[x.id,x]));
    const normalize={memory:"memory",mind:"mind",growth:"growth",skill:"skills",
      improvement:"improve",evolution:"evolution"};
    const edges=new Set();
    for(const relation of d.provenance?.links || []){
      const from=normalize[String(relation.source_id||"").split(":")[0]];
      const to=normalize[String(relation.target_id||"").split(":")[0]];
      if(!from||!to||from===to||!lookup[from]||!lookup[to]) continue;
      const key=[from,to].sort().join("|");
      if(edges.has(key)) continue;
      edges.add(key);
      const a=new T.Vector3(...lookup[from].pos),b=new T.Vector3(...lookup[to].pos);
      const mid=a.clone().add(b).multiplyScalar(.5);mid.y+=170;
      const line=new T.Line(new T.BufferGeometry().setFromPoints(
        new T.QuadraticBezierCurve3(a,mid,b).getPoints(32)),
        new T.LineBasicMaterial({color:0xe7c98d,transparent:true,opacity:.56,
          blending:T.AdditiveBlending,depthWrite:false}));
      gl.scene.add(line);
    }
  }

  function drawProjectSectors(gl,d) {
    const T=gl.THREE, group=new T.Group();
    const sectors=projectSectors(d);
    const mat=new T.SpriteMaterial({map:gl.tex.soft,color:0xffffff,transparent:true,
      opacity:.28,blending:T.AdditiveBlending,depthWrite:false});
    for(const item of sectors){
      const color=new T.Color(item.color);
      const material=mat.clone();material.color=color;
      const sprite=new T.Sprite(material);sprite.position.set(...item.pos);
      sprite.scale.set(210,210,1);group.add(sprite);
      const mark=el("button","gx-project-sector",item.name+" · "+item.count);
      mark.type="button";mark.title="Перейти к разделу «"+item.name+"»";
      mark.onclick=()=>{
        const tab={memory:"facts",mind:"mind",growth:"grow",skills:"skills",improve:"improve",
          evolution:"mind",code:"mind"}[item.id]||"facts";
        try{sessionStorage.setItem("yakumo.home.brain.tab",tab)}catch{}
        location.hash=item.href;
      };
      view.labels.append(mark);
      item.tag=mark;
    }
    gl.scene.add(group);gl.projectSectors=sectors;gl.projectGroup=group;
  }

  // --- Сцена ---
  let view = null;  // { host, ... } — одна на всю жизнь страницы
  let data = null, lastLoad = 0;

  function spriteTexture(THREE, kind) {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    if (kind === "flare") {  // четырёхлучевой блик яркой звезды
      const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.15, "rgba(255,255,255,.35)"); grd.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
      g.globalCompositeOperation = "lighter";
      for (const [w, hgt] of [[128, 3], [3, 128]]) {
        const lg = g.createLinearGradient(64 - w / 2, 64 - hgt / 2, 64 + w / 2, 64 + hgt / 2);
        lg.addColorStop(0, "rgba(255,255,255,0)"); lg.addColorStop(0.5, "rgba(255,255,255,.9)"); lg.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = lg; g.fillRect(64 - w / 2, 64 - hgt / 2, w, hgt);
      }
    } else if (kind === "ring") {  // оболочка сверхновой
      g.strokeStyle = "rgba(255,255,255,.9)"; g.lineWidth = 5; g.filter = "blur(3px)";
      g.beginPath(); g.arc(64, 64, 52, 0, Math.PI * 2); g.stroke();
    } else {  // мягкое облако
      const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.35, "rgba(255,255,255,.35)"); grd.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
    }
    const t = new THREE.CanvasTexture(c);
    t.needsUpdate = true;
    return t;
  }

  // Точки с мерцанием: размер в пикселях с учётом расстояния, мягкий круг, сложение света.
  function pointsMaterial(THREE, opacity = 1) {
    return new THREE.ShaderMaterial({
      uniforms: { time: { value: 0 }, ratio: { value: 1 }, opacity: { value: opacity } },
      vertexShader: `
        attribute float size; attribute float phase; attribute vec3 color;
        uniform float time; uniform float ratio; varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          float tw = 1.0 + 0.28 * sin(time * (0.7 + fract(phase * 7.13) * 1.6) + phase * 6.283);
          gl_PointSize = clamp(size * ratio * tw * (420.0 / -mv.z), 0.0, 220.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform float opacity; varying vec3 vColor;
        void main() {
          float d = length(gl_PointCoord - 0.5) * 2.0;
          float a = smoothstep(1.0, 0.0, d);
          gl_FragColor = vec4(vColor * (0.6 + 0.9 * a * a), a * a * opacity);
        }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
  }

  function pointCloud(THREE, items, material) {
    const pos = new Float32Array(items.length * 3), col = new Float32Array(items.length * 3);
    const size = new Float32Array(items.length), phase = new Float32Array(items.length);
    const c = new THREE.Color();
    items.forEach((p, i) => {
      pos.set(p.pos, i * 3);
      c.set(p.color); col.set([c.r * (p.bright ?? 1), c.g * (p.bright ?? 1), c.b * (p.bright ?? 1)], i * 3);
      size[i] = p.size; phase[i] = p.phase ?? Math.random();
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.setAttribute("size", new THREE.BufferAttribute(size, 1));
    g.setAttribute("phase", new THREE.BufferAttribute(phase, 1));
    return new THREE.Points(g, material);
  }

  function quality() {
    const q = store.get("yakumo.galaxy.quality", "auto");
    return q === "auto" ? (store.get("yakumo.galaxy.auto", "medium")) : q;
  }

  function makeView() {
    const host = el("div", "gx");
    const stage = el("div", "gx-stage");
    const labels = el("div", "gx-labels");
    const warp = el("div", "gx-warp");
    const note = el("p", "gx-note", L.loading);
    const card = el("aside", "gx-card gx-float");
    card.hidden = true;
    card.dataset.key = "card";
    const ctl = el("div", "gx-ctl gx-float");
    ctl.dataset.key = "ctl";
    const observatory = el("div", "gx-observatory");
    const history = el("div", "gx-history");
    history.hidden = true;
    const minimap = document.createElement("canvas");
    minimap.className = "gx-minimap"; minimap.width = 160; minimap.height = 110;
    minimap.title = "Мини-карта: выберите область";
    minimap.setAttribute("aria-label", minimap.title);
    minimap.addEventListener("click", e => {
      if (!view?.gl?.world?.stars.length) return;
      const bounds = minimap.getBoundingClientRect();
      const mx = ((e.clientX - bounds.left) / bounds.width - .5) * 1550;
      const mz = ((e.clientY - bounds.top) / bounds.height - .5) * 1065;
      const star = [...view.gl.world.stars].sort((a,b) =>
        (a.pos[0]-mx)**2+(a.pos[2]-mz)**2-( (b.pos[0]-mx)**2+(b.pos[2]-mz)**2 ))[0];
      if (star) jump(star);
    });
    host.append(stage, warp, labels, note, card, ctl, observatory, history, minimap);
    view = { host, stage, labels, warp, note, card, ctl, observatory, history, minimap, alive: false, gl: null, contemplative: false };
    buildControls();
    for (const box of [card, ctl]) floating(box);
    return view;
  }

  // Плашки (карточка звезды и кнопки) можно перетащить за край; место запоминается.
  function floating(box) {
    const key = "yakumo.galaxy.pos." + box.dataset.key;
    const place = () => {
      const p = store.get(key, null);
      if (!p) { box.style.left = box.style.top = ""; return; }
      const w = view.host.clientWidth || innerWidth, hgt = view.host.clientHeight || innerHeight;
      box.style.left = Math.max(0, Math.min(w - box.offsetWidth, p.x * w)) + "px";
      box.style.top = Math.max(0, Math.min(hgt - 40, p.y * hgt)) + "px";
      box.style.right = box.style.bottom = "auto";
    };
    box.place = place;
    box.addEventListener("pointerdown", (e) => {
      if (!e.target.closest(".gx-grip")) return;
      e.preventDefault();
      const r = box.getBoundingClientRect(), hr = view.host.getBoundingClientRect();
      const dx = e.clientX - r.left, dy = e.clientY - r.top;
      const move = (ev) => {
        const x = ev.clientX - hr.left - dx, y = ev.clientY - hr.top - dy;
        store.set(key, { x: x / hr.width, y: y / hr.height });
        place();
      };
      const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
      addEventListener("pointermove", move);
      addEventListener("pointerup", up);
    });
  }

  function buildControls() {
    const { ctl } = view;
    const grip = el("span", "gx-grip", "⋮⋮");
    grip.title = "⇕";
    const sel = el("select", "gx-select");
    sel.setAttribute("aria-label", L.quality);
    for (const k of ["auto", "low", "medium", "high"]) {
      const o = el("option", "", `${L.quality}: ${L.q[k]}`);
      o.value = k;
      sel.append(o);
    }
    sel.value = store.get("yakumo.galaxy.quality", "auto");
    sel.onchange = () => { store.set("yakumo.galaxy.quality", sel.value); rebuild(); };
    const reset = el("button", "gx-btn", "⌂");
    reset.type = "button"; reset.title = L.reset; reset.setAttribute("aria-label", L.reset);
    reset.onclick = () => view.gl && flyTo([0, 0, 0], 900);
    const help = el("button", "gx-btn", "?");
    help.type = "button"; help.title = L.help; help.setAttribute("aria-label", L.help);
    const hint = el("p", "gx-hint", L.hint);
    hint.hidden = store.get("yakumo.galaxy.hintSeen", false);
    help.onclick = () => { hint.hidden = !hint.hidden; store.set("yakumo.galaxy.hintSeen", true); };
    const observe = el("button", "gx-btn", "◉");
    observe.type = "button"; observe.title = "Созерцание: скрыть панели"; observe.setAttribute("aria-label", observe.title);
    observe.onclick = () => {
      view.contemplative = !view.contemplative;
      view.host.classList.toggle("gx-contemplative", view.contemplative);
      observe.title = view.contemplative ? "Вернуть панели" : "Созерцание: скрыть панели";
      observe.setAttribute("aria-label", observe.title);
    };
    const flight = el("button", "gx-btn", "✧");
    flight.type = "button"; flight.title = "Полёт по созвездиям"; flight.setAttribute("aria-label", flight.title);
    flight.onclick = () => {
      const gl = view.gl;
      if (!gl?.world?.stars.length) return;
      const stars = [...gl.world.stars].sort((a,b) => b.facts.length - a.facts.length);
      const links = (gl.world.edges || []).filter(e => e.from === gl.selected || e.to === gl.selected);
      const related = links.map(e => e.from === gl.selected ? e.to : e.from);
      const choices = related.length ? related : stars;
      const next = choices[(gl.tourIndex = ((gl.tourIndex ?? -1) + 1) % choices.length)];
      jump(next);
    };
    const nebula = el("select", "gx-select");
    nebula.title = "Детализация туманностей"; nebula.setAttribute("aria-label", nebula.title);
    for (const [key, name] of [["normal","Туманности"],["low","Лёгкие туманности"]]) {
      const option = el("option", "", name); option.value = key; nebula.append(option);
    }
    nebula.value = store.get("yakumo.galaxy.nebula", "normal");
    nebula.onchange = () => { store.set("yakumo.galaxy.nebula", nebula.value); rebuild(); };
    const history = el("button", "gx-btn", "◷");
    history.type = "button"; history.title = "История наблюдений и изменений";
    history.onclick = () => {
      view.history.hidden = !view.history.hidden;
      renderObservations();
    };
    const weakest = el("button", "gx-btn", "◇");
    weakest.type = "button"; weakest.title = "Наименее заполненная область памяти";
    weakest.onclick = () => {
      const gl = view.gl;
      if (!gl?.world?.stars?.length) return;
      const buckets = new Map();
      for (const star of gl.world.stars)
        buckets.set(star.area, (buckets.get(star.area) || 0) + star.facts.length);
      const least = [...buckets].sort((a,b) => a[1]-b[1])[0]?.[0];
      const target = gl.world.stars.filter(x=>x.area===least).sort((a,b)=>a.facts.length-b.facts.length)[0];
      if (target) jump(target);
    };
    const stats = el("button", "gx-btn", "FPS");
    stats.type = "button"; stats.title = "Показать диагностику кадра";
    stats.onclick = () => view.observatory.classList.toggle("gx-observatory-open");
    ctl.append(grip, reset, sel, nebula, flight, weakest, observe, history, stats, help, hint);
  }

  // --- WebGL ---
  function startGl(THREE) {
    const q = QUALITY[quality()];
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "high-performance" });
    } catch {
      view.note.textContent = L.noGl;
      view.note.hidden = false;
      return null;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, q.ratio));
    renderer.setClearColor(0x05040a, 1);
    view.stage.replaceChildren(renderer.domElement);
    renderer.domElement.addEventListener("webglcontextlost", e => {
      e.preventDefault();
      view.note.textContent = "WebGL-контекст потерян. Ожидаю восстановление…";
      view.note.hidden = false;
      if (view.raf) cancelAnimationFrame(view.raf);
      view.raf = 0;
    });
    renderer.domElement.addEventListener("webglcontextrestored", () => {
      // Renderer owns the newly restored GPU context; rebuild buffers explicitly.
      if (view.gl?.renderer !== renderer) return;
      if (data) populate();
      view.note.hidden = true;
      if (view.alive && !document.hidden && !view.raf) view.raf = requestAnimationFrame(frame);
    });
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, 1, 1, 20000);
    const tex = { soft: spriteTexture(THREE, "soft"), flare: spriteTexture(THREE, "flare"), ring: spriteTexture(THREE, "ring") };
    const gl = { THREE, renderer, scene, camera, tex, q, mats: [], world: null, galaxy: new THREE.Group(),
                 orbit: { yaw: 0.6, pitch: 0.62, dist: 1500, target: new THREE.Vector3() },
                 vel: new THREE.Vector3(), spin: { yaw: 0, pitch: 0 }, keys: new Set(), flight: null,
                 meteors: [], flashes: new Map(), selected: null, frames: [], time: 0 };
    scene.add(gl.galaxy);
    view.gl = gl;
    bindInput();
    return gl;
  }

  function populate() {
    const gl = view.gl, { THREE, scene, galaxy, tex, q } = gl;
    const disposeTree = obj => obj.traverse(child => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) child.material.forEach(m => m.dispose?.());
      else child.material?.dispose?.();
    });
    for (const o of [...galaxy.children]) { disposeTree(o); galaxy.remove(o); }
    for (const o of [...scene.children]) if (o !== galaxy) { disposeTree(o); scene.remove(o); }
    gl.meteors = [];
    gl.flashes.clear();
    gl.comets = [];
    gl.mats.forEach((m) => m.dispose());
    gl.mats = [];
    const w = gl.world = buildWorld(data);
    // One static minimap redraw per graph update, no extra WebGL scene.
    const mini = view.minimap.getContext("2d");
    if (mini) {
      mini.clearRect(0,0,160,110);
      mini.fillStyle = "#09101e"; mini.fillRect(0,0,160,110);
      for (const star of w.stars) {
        const x = 80 + star.pos[0] * .102, y = 55 + star.pos[2] * .102;
        mini.beginPath(); mini.arc(x,y,Math.min(3,1+star.facts.length*.18),0,Math.PI*2);
        mini.fillStyle = AREA_HUE[star.area] || "#e3bd82"; mini.fill();
      }
    }

    const mat = (o) => { const m = pointsMaterial(THREE, o); gl.mats.push(m); return m; };
    const rand = rng(7);
    // Пыль рукавов: цвет своей области жизни, к ядру — тёплое золото.
    const arms = w.areas.length ? w.areas : ["other", "other"];
    const nebulaMultiplier = store.get("yakumo.galaxy.nebula", "normal") === "low" ? .5 : 1;
    const dust = [];
    // Три визуальных слоя в том же бюджете частиц: туманная вуаль,
    // основной спиральный рукав и отдельные яркие нити.
    for (let i = 0; i < q.dust; i++) {
      const arm = i % w.arms, area = arms[arm % arms.length];
      const t = Math.pow(rand(), 0.7);
      const r = 40 + t * R * 1.08;
      const layer = i % 3;
      const spread = (rand() - 0.5) * (layer === 0 ? 0.8 : layer === 1 ? 0.3 : 0.12)
        + (rand() - 0.5) * t * 0.16;
      const a = arm / w.arms * Math.PI * 2 + r * 0.0062 + spread;
      const color = rand() < 0.55 - t * 0.35 ? "#ffe2a8" : rand() < 0.75 ? AREA_HUE[area] : "#ffffff";
      dust.push({ pos: [Math.cos(a) * r + (rand() - 0.5) * 22,
                    (rand() - 0.5) * (layer === 0 ? 80 : layer === 1 ? 26 : 8),
                    Math.sin(a) * r + (rand() - 0.5) * 22],
                  color, size: layer === 0 ? 3.7 + rand() * 3.4 : 1.5 + rand() * 2.2,
                  bright: layer === 0 ? .18 + rand() * .18 : .46 + rand() * .44 });
    }
    // Ядро-мозг: плотный тёплый шар и «нейроны», которые пульсируют сильнее.
    for (let i = 0; i < q.dust / 6; i++) {
      const u = rand() * 2 - 1, ph = rand() * Math.PI * 2, rr = Math.pow(rand(), 2.2) * 120;
      const s = Math.sqrt(1 - u * u);
      dust.push({ pos: [Math.cos(ph) * s * rr, u * rr * 0.55, Math.sin(ph) * s * rr], color: rand() < 0.5 ? "#ffd58a" : "#fff4dc",
                  size: 2 + rand() * 3, bright: 0.5 + rand() * 0.5 });
    }
    galaxy.add(pointCloud(THREE, dust, mat(0.9)));
    const neurons = [];
    const n = Math.max(40, Math.min(220, (data.brain?.[data.brain.length - 1]?.neurons) || 60));
    for (let i = 0; i < n; i++) {
      const u = rand() * 2 - 1, ph = rand() * Math.PI * 2, rr = 25 + rand() * 60, s = Math.sqrt(1 - u * u);
      neurons.push({ pos: [Math.cos(ph) * s * rr, u * rr * 0.6, Math.sin(ph) * s * rr], color: "#ffe7b0", size: 7 + rand() * 6, phase: rand() });
    }
    const neuronPts = pointCloud(THREE, neurons, mat(1));
    galaxy.add(neuronPts);
    const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.soft, color: 0xffcf7a, transparent: true, opacity: 0.9,
                                                                 blending: THREE.AdditiveBlending, depthWrite: false }));
    coreGlow.scale.set(420, 420, 1);
    galaxy.add(coreGlow);
    gl.core = coreGlow;
    for (let i = 0; i < 3; i++) {
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({
        map: tex.soft, color: i === 0 ? 0xffd487 : i === 1 ? 0xffbc68 : 0xa69df1,
        transparent: true, opacity: .16 - i * .035, blending: THREE.AdditiveBlending, depthWrite: false
      }));
      const radius = 520 + i * 220;
      halo.scale.set(radius, radius * .75, 1);
      halo.position.y = -15 * i;
      galaxy.add(halo);
    }
    // Туманности: облака газа вдоль рукавов своих областей.
    w.areas.forEach((area, ai) => {
      for (let k = 0; k < Math.ceil(7 * nebulaMultiplier); k++) {
        const r = 150 + k * 70 + rand() * 40, a = ai / w.arms * Math.PI * 2 + r * 0.0062 + (rand() - 0.5) * 0.2;
        const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.soft, color: AREA_HUE[area], transparent: true,
                                                               opacity: 0.075 + rand() * 0.06, blending: THREE.AdditiveBlending, depthWrite: false }));
        sp.position.set(Math.cos(a) * r, (rand() - 0.5) * 20, Math.sin(a) * r);
        const s = 200 + rand() * 220;
        sp.scale.set(s, s * (0.55 + rand() * 0.3), 1);
        galaxy.add(sp);
      }
    });
    // Звёзды: тип по свежести, свечение подсвечивает соседнюю пыль, у самых ярких — блик.
    const starPts = w.stars.map((s) => ({ pos: s.pos, color: STAR_HUE[s.kind], size: s.kind === "fresh" ? s.size * 1.35 : s.kind === "cold" ? s.size * 0.7 : s.size, phase: hash(s.id) % 1000 / 1000 }));
    gl.starPts = pointCloud(THREE, starPts, mat(1));
    galaxy.add(gl.starPts);
    const bright = [...w.stars].sort((a, b) => b.facts.length - a.facts.length).slice(0, 10);
    for (const s of w.stars) {
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.soft, color: STAR_HUE[s.kind], transparent: true, opacity: s.kind === "cold" ? 0.12 : 0.26,
                                                               blending: THREE.AdditiveBlending, depthWrite: false }));
      halo.position.set(...s.pos);
      const hs = s.size * (s.kind === "cold" ? 2.2 : 3.4);
      halo.scale.set(hs, hs, 1);
      galaxy.add(halo);
      s.halo = halo;
      if (bright.includes(s) && s.kind !== "cold") {
        const fl = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.flare, color: STAR_HUE[s.kind], transparent: true, opacity: 0.4,
                                                               blending: THREE.AdditiveBlending, depthWrite: false }));
        fl.position.set(...s.pos);
        fl.scale.set(s.size * 2.4, s.size * 2.4, 1);
        galaxy.add(fl);
        s.flare = fl;
      }
      if (s.nova) {  // сверхновая: расходящаяся оболочка
        const ring = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.ring, color: 0xbfe0ff, transparent: true, opacity: 0,
                                                                 blending: THREE.AdditiveBlending, depthWrite: false }));
        ring.position.set(...s.pos);
        galaxy.add(ring);
        s.ring = ring;
      }
    }
    // Связи по реальным общим фактам. Изогнутые линии статичны:
    // движущиеся импульсы запускаются только событиями памяти.
    for (const edge of w.edges) {
      const a = new THREE.Vector3(...edge.from.pos), b = new THREE.Vector3(...edge.to.pos);
      const midpoint = a.clone().add(b).multiplyScalar(.5);
      midpoint.y += 35 + Math.min(120, a.distanceTo(b) * .08);
      const curve = new THREE.QuadraticBezierCurve3(a, midpoint, b);
      const mesh = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(curve.getPoints(12)),
        new THREE.LineBasicMaterial({color: 0xe2be7d,transparent:true,
          opacity:.13,depthWrite:false,blending:THREE.AdditiveBlending}));
      galaxy.add(mesh);
    }
    // Созвездия событий — тонкие золотые линии.
    if (w.constellations.length) {
      const pts = [];
      for (const c of w.constellations) {
        for (let i = 0; i < c.members.length; i++) pts.push(...c.members[i].pos, ...c.members[(i + 1) % c.members.length].pos);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
      galaxy.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xffd58a, transparent: true, opacity: 0.32,
                                                                         blending: THREE.AdditiveBlending, depthWrite: false })));
    }
    // Чёрная дыра забытого: тёмный шар, аккреционный диск, забытые звёзды на орбитах.
    const [hx, hy, hz] = w.hole;
    const hole = new THREE.Group();
    hole.position.set(hx, hy, hz);
    hole.rotation.x = 0.35;
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.soft, color: 0xff9a4a, transparent: true, opacity: 0.55,
                                                             blending: THREE.AdditiveBlending, depthWrite: false }));
    glow.scale.set(150, 150, 1);
    hole.add(glow);
    const disk = [];
    for (let i = 0; i < q.dust / 8; i++) {
      const a = rand() * Math.PI * 2, rr = 30 + Math.pow(rand(), 1.6) * 60;
      disk.push({ pos: [Math.cos(a) * rr, (rand() - 0.5) * 3, Math.sin(a) * rr], color: rand() < 0.6 ? "#ffb35c" : "#ffe1b0", size: 1.5 + rand() * 2.5, bright: 0.5 + rand() * 0.5 });
    }
    gl.disk = pointCloud(THREE, disk, mat(1));
    hole.add(gl.disk);
    const dark = new THREE.Mesh(new THREE.SphereGeometry(26, 32, 16), new THREE.MeshBasicMaterial({ color: 0x000000 }));
    hole.add(dark);
    scene.add(hole);
    gl.hole = hole;
    gl.lostPts = null;
    if (w.lost.length) {
      gl.lostPts = pointCloud(THREE, w.lost.map((s) => ({ pos: s.pos, color: "#ff8a6a", size: 16, phase: 0.3 })), mat(0.85));
      scene.add(gl.lostPts);
    }
    // Млечный путь: далёкий фон полосой и несколько дальних галактик.
    const sky = [];
    for (let i = 0; i < q.sky; i++) {
      const u = rand() * 2 - 1, ph = rand() * Math.PI * 2, band = rand() < 0.6;
      const lat = band ? (rand() - 0.5) * 0.35 : u;
      const s = Math.sqrt(1 - lat * lat), rr = 7000 + rand() * 2500;
      sky.push({ pos: [Math.cos(ph) * s * rr, lat * rr, Math.sin(ph) * s * rr],
                 color: rand() < 0.15 ? "#bcd4ff" : rand() < 0.2 ? "#ffd9b0" : "#ffffff", size: 6 + rand() * (band ? 10 : 16), bright: band ? 0.35 + rand() * 0.3 : 0.5 + rand() * 0.5 });
    }
    const skyPts = pointCloud(THREE, sky, mat(1));
    skyPts.rotation.set(0.9, 0, 0.4);
    scene.add(skyPts);
    gl.sky = skyPts;
    for (let i = 0; i < 6; i++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.soft, color: ["#c9b6ff", "#ffd6a8", "#a8d8ff"][i % 3], transparent: true,
                                                             opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
      const a = rand() * Math.PI * 2, b = (rand() - 0.5) * 1.6;
      sp.position.set(Math.cos(a) * Math.cos(b) * 6500, Math.sin(b) * 6500, Math.sin(a) * Math.cos(b) * 6500);
      sp.scale.set(500, 180, 1);
      sp.material.rotation = rand() * Math.PI;
      scene.add(sp);
    }
    // Кометы: голова и хвост из точек, летят к звезде по кругу.
    gl.comets = w.comets.map((c) => {
      const trail = pointCloud(THREE, Array.from({ length: 26 }, (_, i) => ({ pos: [0, 0, 0], color: i ? "#9fdcff" : "#ffffff", size: i ? 14 - i * 0.45 : 26, phase: 0 })), mat(1));
      galaxy.add(trail);
      return { ...c, trail, start: (c.seed % 1000) / 1000 * 9 };
    });
    // Подписи.
    view.labels.replaceChildren();
    for (const s of [...w.stars, ...w.lost]) {
      const tag = el("button", "gx-label" + (s.lost ? " lost" : "") + (s.kind === "fresh" ? " fresh" : ""), s.e.name);
      tag.type = "button";
      if (s.nova) tag.append(el("em", "", " ✦"));
      if (w.comets.some((c) => c.target === s)) tag.append(el("em", "comet", " ☄"));
      tag.onclick = () => select(s);
      tag.ondblclick = () => jump(s);
      view.labels.append(tag);
      s.tag = tag;
    }
    drawProjectSectors(gl,data);
    drawProvenanceLinks(gl,data);
    gl.areaTags = w.areas.map((area, ai) => {
      const r = R * 0.95, a = ai / w.arms * Math.PI * 2 + r * 0.0062;
      const tag = el("span", "gx-area", L.areas[area] || area);
      tag.style.color = AREA_HUE[area];
      view.labels.append(tag);
      return { tag, pos: [Math.cos(a) * r, 0, Math.sin(a) * r] };
    });
    gl.consTags = w.constellations.map((c) => {
      const tag = el("span", "gx-cons", c.f.text.length > 40 ? c.f.text.slice(0, 38) + "…" : c.f.text);
      view.labels.append(tag);
      const m = c.members, pos = [0, 1, 2].map((k) => m.reduce((a, s) => a + s.pos[k], 0) / m.length);
      return { tag, pos };
    });
    const holeTag = el("span", "gx-area hole", L.hole);
    view.labels.append(holeTag);
    gl.holeTag = { tag: holeTag, pos: [hx, hy - 110, hz], world: true };
    const coreTag = el("span", "gx-area core", L.core);
    view.labels.append(coreTag);
    gl.coreTag = { tag: coreTag, pos: [0, -70, 0] };
    view.note.hidden = !!(w.stars.length || w.lost.length);
    view.note.textContent = L.empty;
    meteorsForNews();
    if (gl.selected) select(w.byId[gl.selected.id] || null, false);
  }

  // Новые факты с прошлого визита падают метеорами на свои звёзды.
  function meteorsForNews() {
    const gl = view.gl, w = gl.world;
    const seen = new Set(store.get("yakumo.galaxy.seen", []));
    const ids = data.facts.map((f) => f.id);
    if (seen.size) {
      let delay = 800;
      for (const f of data.facts) {
        if (seen.has(f.id)) continue;
        for (const id of f.about || []) {
          const s = w.byId[id];
          if (s && !s.lost && gl.meteors.length < 24) { meteor(s, delay); delay += 450; }
        }
      }
    }
    store.set("yakumo.galaxy.seen", ids.slice(0, 3000));
  }

  function meteor(star, delay = 0) {
    const gl = view.gl, { THREE } = gl;
    const pts = pointCloud(THREE, Array.from({ length: 14 }, (_, i) => ({ pos: [0, 0, 0], color: i ? "#ffe2a0" : "#ffffff", size: i ? 16 - i : 30, phase: 0 })), pointsMaterial(THREE, 1));
    gl.galaxy.add(pts);
    const r = rng(hash(star.id) + gl.meteors.length);
    const from = [star.pos[0] + (r() - 0.5) * 900, star.pos[1] + 500 + r() * 400, star.pos[2] + (r() - 0.5) * 900];
    gl.meteors.push({ star, pts, from, start: gl.time + delay / 1000, dur: 1.6 });
  }

  // --- Камера ---
  function applyCamera() {
    const gl = view.gl, o = gl.orbit;
    const cp = Math.cos(o.pitch);
    gl.camera.position.set(o.target.x + Math.sin(o.yaw) * cp * o.dist, o.target.y + Math.sin(o.pitch) * o.dist, o.target.z + Math.cos(o.yaw) * cp * o.dist);
    gl.camera.lookAt(o.target);
  }

  function worldPos(s) {
    const gl = view.gl, v = new gl.THREE.Vector3(...s.pos);
    return s.lost ? v : v.applyMatrix4(gl.galaxy.matrixWorld);
  }

  function flyTo(target, dist = 380, ms = 1400, warp = false) {
    const gl = view.gl, o = gl.orbit;
    const to = Array.isArray(target) ? new gl.THREE.Vector3(...target) : target;
    gl.flight = { from: o.target.clone(), to, d0: o.dist, d1: dist, t0: performance.now(), ms, warp };
    if (warp) { view.warp.classList.remove("on"); void view.warp.offsetWidth; view.warp.classList.add("on"); }
  }

  function jump(s) {
    if (!s) return;
    select(s);
    flyTo(worldPos(s), s.lost ? 260 : 230, 1500, true);
  }

  // --- Выбор звезды и карточка ---
  function select(s, open = true) {
    const gl = view.gl;
    gl.selected = s;
    for (const x of [...gl.world.stars, ...gl.world.lost]) x.tag?.classList.toggle("on", x === s);
    const { card } = view;
    if (!s) { card.hidden = true; return; }
    if (!open && card.hidden) return;
    const head = el("div", "gx-card-head");
    head.append(el("span", "gx-grip", "⋮⋮"));
    const title = el("div", "gx-card-title");
    title.append(el("strong", "", s.e.name));
    const sub = [L.areas[s.area] || s.area, s.e.relation].filter(Boolean).join(" · ");
    title.append(el("span", "", sub));
    head.append(title);
    const close = el("button", "gx-btn", "×");
    close.type = "button"; close.setAttribute("aria-label", L.close);
    close.onclick = () => select(null);
    head.append(close);
    const body = [head];
    if (s.lost) {
      body.push(el("p", "gx-lost", L.forgotten), el("p", "gx-muted", L.dragOut));
      const back = el("button", "btn primary", L.recall);
      back.type = "button";
      back.onclick = () => recall(s);
      body.push(back);
    }
    const facts = s.lost ? s.all : s.facts;
    body.push(el("div", "gx-muted", L.facts(facts.length)));
    const ul = el("ul", "gx-facts");
    for (const f of facts.slice(0, 6)) ul.append(el("li", "", f.text));
    body.push(ul);
    const promises = (data.promises || []).filter((p) => !p.done && ((p.about || []).includes(s.id) || p.text.toLowerCase().includes(s.e.name.toLowerCase())));
    if (promises.length) {
      body.push(el("div", "gx-sec", L.promises));
      const pl = el("ul", "gx-facts promises");
      for (const p of promises.slice(0, 4)) pl.append(el("li", "", p.text + (p.due ? ` · ${p.due}` : "")));
      body.push(pl);
    }
    const docs = [...new Set([...facts.flatMap((f) => f.files || []), ...((data.entity_docs || {})[s.id] || [])])].slice(0, 6);
    if (docs.length) {
      body.push(el("div", "gx-sec", L.docs));
      const dl = el("div", "gx-docs");
      for (const p of docs) {
        const a = el("a", "", p.split("/").pop());
        a.href = `/api/disk/file?path=${encodeURIComponent(p)}`;
        a.target = "_blank"; a.rel = "noopener"; a.title = p;
        dl.append(a);
      }
      body.push(dl);
    }
    const bar = el("div", "gx-actions");
    const ask = el("button", "btn", L.ask);
    ask.type = "button";
    ask.onclick = () => Y.ask(L.askAbout(s.e.name));
    const open2 = el("a", "btn", L.open);
    open2.href = "#/brain";
    bar.append(ask, open2);
    body.push(bar);
    card.replaceChildren(...body);
    card.hidden = false;
    card.place();
  }

  async function recall(s) {
    try {
      await Y.postJSON("/api/brain/recall", { id: s.id });
      view.gl.selected = { id: s.id };
      await load(true);
    } catch { /* сервер недоступен — звезда остаётся у чёрной дыры */ }
  }

  // --- Управление: мышь, колесо, клавиши ---
  function bindInput() {
    const gl = view.gl, cv = gl.renderer.domElement;
    cv.tabIndex = 0;
    cv.setAttribute("aria-label", "Galaxy");
    let drag = null;
    cv.addEventListener("pointerdown", (e) => {
      cv.setPointerCapture(e.pointerId);
      const hit = pick(e);
      drag = { x: e.clientX, y: e.clientY, yaw: gl.orbit.yaw, pitch: gl.orbit.pitch, moved: false, lost: hit?.lost ? hit : null, last: performance.now() };
      gl.spin.yaw = gl.spin.pitch = 0;
    });
    cv.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      drag.moved = true;
      cv.classList.add("grabbing");
      if (drag.lost) return;  // тянем забытую звезду — камера стоит
      const ny = drag.yaw - dx * 0.005, np = Math.max(-1.45, Math.min(1.45, drag.pitch + dy * 0.004));
      const dt = Math.max(1, performance.now() - drag.last);
      gl.spin.yaw = (ny - gl.orbit.yaw) / dt * 16; gl.spin.pitch = (np - gl.orbit.pitch) / dt * 16;
      gl.orbit.yaw = ny; gl.orbit.pitch = np; drag.last = performance.now();
    });
    cv.addEventListener("pointerup", (e) => {
      cv.classList.remove("grabbing");
      if (!drag) return;
      const d = drag;
      drag = null;
      if (d.lost && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 120) { recall(d.lost); return; }
      if (!d.moved) select(pick(e));
    });
    cv.addEventListener("dblclick", (e) => jump(pick(e)));
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      gl.orbit.dist = Math.max(60, Math.min(5200, gl.orbit.dist * (e.deltaY > 0 ? 1.12 : 1 / 1.12)));
    }, { passive: false });
    cv.addEventListener("keydown", (e) => { gl.keys.add(e.key.toLowerCase()); if (e.key === "Shift") gl.keys.add("shift"); });
    cv.addEventListener("keyup", (e) => { gl.keys.delete(e.key.toLowerCase()); if (e.key === "Shift") gl.keys.delete("shift"); });
    cv.addEventListener("blur", () => gl.keys.clear());
  }

  function pick(e) {
    const gl = view.gl;
    if (!gl.world) return null;
    const r = gl.renderer.domElement.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    let best = null, bd = 26;
    for (const s of [...gl.world.stars, ...gl.world.lost]) {
      const p = worldPos(s).project(gl.camera);
      if (p.z > 1) continue;
      const d = Math.hypot((p.x + 1) / 2 * r.width - mx, (1 - p.y) / 2 * r.height - my);
      if (d < bd) { bd = d; best = s; }
    }
    return best;
  }

  // --- Кадр ---
  function frame(now) {
    if (!view?.alive) return;
    view.raf = 0;
    if (!view.host.isConnected) { stopScene(); return; }
    if (document.hidden) return;
    const gl = view.gl;
    if (!gl?.world) { view.raf = requestAnimationFrame(frame); return; }
    const interacting = gl.keys.size || gl.flight || Math.abs(gl.spin.yaw) > 0.0002 ||
      Math.abs(gl.spin.pitch) > 0.0002 || gl.meteors.length;
    const limit = interacting ? 30 : 18;
    if (gl.lastPaint && now - gl.lastPaint < 1000 / limit) {
      view.raf = requestAnimationFrame(frame);
      return;
    }
    const dt = Math.min(0.05, (now - (gl.last || now)) / 1000);
    gl.last = now;
    gl.lastPaintGap = gl.lastPaint ? now - gl.lastPaint : 0;
    gl.lastPaint = now;
    gl.time += dt;
    view.raf = requestAnimationFrame(frame);
    const w = view.stage.clientWidth, hgt = view.stage.clientHeight;
    if (w !== gl.w || hgt !== gl.h) {
      gl.renderer.setSize(w, hgt, false);
      gl.camera.aspect = w / Math.max(1, hgt);
      gl.camera.updateProjectionMatrix();
      if (!gl.sized && !gl.flight) gl.orbit.dist = 1500 * Math.max(1, Math.sqrt(0.9 / gl.camera.aspect));  // на узком экране — дальше
      gl.w = w; gl.h = hgt; gl.sized = true;
      view.card.place?.(); view.ctl.place?.();
    }
    for (const m of gl.mats) { m.uniforms.time.value = gl.time; m.uniforms.ratio.value = gl.renderer.getPixelRatio(); }
    // Галактика медленно вращается; ядро дышит.
    if (!reduced) gl.galaxy.rotation.y += dt * 0.012;
    gl.core.material.opacity = 0.75 + Math.sin(gl.time * 1.3) * 0.15;
    if (gl.disk) gl.disk.rotation.y += dt * 0.9;
    // Инерция вращения после отпускания мыши.
    gl.orbit.yaw += gl.spin.yaw; gl.orbit.pitch = Math.max(-1.45, Math.min(1.45, gl.orbit.pitch + gl.spin.pitch));
    gl.spin.yaw *= 0.92; gl.spin.pitch *= 0.92;
    // Полёт клавишами: ускорение и плавное торможение.
    const k = gl.keys, acc = (k.has("shift") ? 2600 : 900) * dt;
    const fwd = new gl.THREE.Vector3(); gl.camera.getWorldDirection(fwd);
    const right = new gl.THREE.Vector3().crossVectors(fwd, gl.camera.up).normalize();
    if (k.has("w") || k.has("ц") || k.has("arrowup")) gl.vel.addScaledVector(fwd, acc);
    if (k.has("s") || k.has("ы") || k.has("arrowdown")) gl.vel.addScaledVector(fwd, -acc);
    if (k.has("d") || k.has("в") || k.has("arrowright")) gl.vel.addScaledVector(right, acc);
    if (k.has("a") || k.has("ф") || k.has("arrowleft")) gl.vel.addScaledVector(right, -acc);
    if (k.has("e") || k.has("у")) gl.vel.y += acc;
    if (k.has("q") || k.has("й")) gl.vel.y -= acc;
    gl.orbit.target.addScaledVector(gl.vel, dt);
    gl.vel.multiplyScalar(Math.pow(0.04, dt));
    if (gl.flight) {
      const f = gl.flight, t = Math.min(1, (now - f.t0) / f.ms), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      gl.orbit.target.lerpVectors(f.from, f.to, e);
      gl.orbit.dist = f.d0 + (f.d1 - f.d0) * e;
      gl.camera.fov = f.warp ? 60 + Math.sin(t * Math.PI) * 38 : 60;
      gl.camera.updateProjectionMatrix();
      if (t >= 1) gl.flight = null;
    }
    applyCamera();
    gl.galaxy.updateMatrixWorld();
    // Сверхновые и кометы.
    for (const s of gl.world.stars) {
      if (s.ring) {
        const p = (gl.time * 0.25 + (hash(s.id) % 100) / 100) % 1;
        s.ring.scale.setScalar(s.size * (1 + p * 9));
        s.ring.material.opacity = (1 - p) * 0.7;
      }
      const fl = gl.flashes.get(s);
      if (fl != null) {
        const p = (gl.time - fl) / 1.2;
        if (p > 1) { gl.flashes.delete(s); s.halo.material.opacity = s.kind === "cold" ? 0.12 : 0.26; }
        else s.halo.material.opacity = 0.26 + (1 - p) * 0.9;
      }
    }
    for (const c of gl.comets) {
      const pos = c.trail.geometry.attributes.position;
      const T = 9, p0 = c.target.pos;
      for (let i = 0; i < pos.count; i++) {
        const t = ((gl.time + c.start - i * 0.035) % T) / T;
        const rr = 520 * (1 - t) + 14, a = t * 5 + c.seed % 7;
        pos.setXYZ(i, p0[0] + Math.cos(a) * rr, p0[1] + 160 * (1 - t) + 6, p0[2] + Math.sin(a) * rr);
      }
      pos.needsUpdate = true;
    }
    // Метеоры новых фактов.
    for (let i = gl.meteors.length - 1; i >= 0; i--) {
      const m = gl.meteors[i], t = (gl.time - m.start) / m.dur;
      const pos = m.pts.geometry.attributes.position;
      if (t < 0) { m.pts.visible = false; continue; }
      m.pts.visible = true;
      if (t >= 1) {
        gl.galaxy.remove(m.pts); m.pts.geometry.dispose(); m.pts.material.dispose();
        gl.meteors.splice(i, 1);
        gl.flashes.set(m.star, gl.time);
        continue;
      }
      for (let j = 0; j < pos.count; j++) {
        const u = Math.max(0, t - j * 0.018), e = u * u;
        pos.setXYZ(j, m.from[0] + (m.star.pos[0] - m.from[0]) * e, m.from[1] + (m.star.pos[1] - m.from[1]) * e, m.from[2] + (m.star.pos[2] - m.from[2]) * e);
      }
      pos.needsUpdate = true;
      m.pts.material.uniforms.time.value = gl.time;
      m.pts.material.uniforms.ratio.value = gl.renderer.getPixelRatio();
    }
    // Забытые звёзды на орбитах чёрной дыры.
    if (gl.lostPts) {
      const pos = gl.lostPts.geometry.attributes.position, [hx, hy, hz] = gl.world.hole;
      gl.world.lost.forEach((s, i) => {
        const o = s.orbit, a = o.a + gl.time * o.speed;
        s.pos = [hx + Math.cos(a) * o.r, hy + Math.sin(a) * o.r * o.tilt, hz + Math.sin(a) * o.r];
        pos.setXYZ(i, ...s.pos);
      });
      pos.needsUpdate = true;
    }
    const renderStarted = performance.now();
    gl.renderer.render(gl.scene, gl.camera);
    const cost = performance.now() - renderStarted;
    autoQuality(cost, now);
    gl.lastRenderMs = cost;
    if (now - (gl.lastStats || 0) >= 1000) {
      gl.lastStats = now;
      const observed = gl.lastPaintGap ? Math.round(1000 / gl.lastPaintGap) : 0;
      view.observatory.textContent = "FPS: " + observed + " · кадр: " +
        cost.toFixed(1) + " мс · качество: " + quality() +
        " · звёзд памяти: " + gl.world.stars.length +
        " · поколений: " + (data?.evolution?.total_generations || 0);
    }
    placeLabels();
  }

  function placeLabels() {
    const gl = view.gl, w = gl.w, hgt = gl.h;
    const show = (tag, p, minScale = 0) => {
      const v = (p.isVector3 ? p : new gl.THREE.Vector3(...p)).project(gl.camera);
      if (v.z > 1 || Math.abs(v.x) > 1.1 || Math.abs(v.y) > 1.1) { tag.style.opacity = 0; tag.style.pointerEvents = "none"; return null; }
      tag.style.transform = `translate(${((v.x + 1) / 2 * w).toFixed(1)}px, ${((1 - v.y) / 2 * hgt).toFixed(1)}px)`;
      return v;
    };
    const dist = gl.orbit.dist;
    for (const s of [...gl.world.stars, ...gl.world.lost]) {
      const wp = worldPos(s);
      const v = show(s.tag, wp);
      if (!v) continue;
      const d = wp.distanceTo(gl.camera.position);
      const vis = s === gl.selected || d < 1700 + s.facts.length * 60 || (s.facts.length >= 4 && d < 3000);
      s.tag.style.opacity = vis ? Math.max(0.35, Math.min(1, 1.6 - d / 1500)).toFixed(2) : 0;
      s.tag.style.pointerEvents = vis ? "auto" : "none";
    }
    for (const p of gl.projectSectors || []) {
      const wp = new gl.THREE.Vector3(...p.pos);
      if (show(p.tag,wp)) p.tag.style.opacity = .87;
    }
    for (const a of gl.areaTags) {
      const wp = new gl.THREE.Vector3(...a.pos).applyMatrix4(gl.galaxy.matrixWorld);
      if (show(a.tag, wp)) a.tag.style.opacity = dist > 900 ? 0.9 : 0;
    }
    for (const c of gl.consTags) {
      const wp = new gl.THREE.Vector3(...c.pos).applyMatrix4(gl.galaxy.matrixWorld);
      if (show(c.tag, wp)) c.tag.style.opacity = wp.distanceTo(gl.camera.position) < 1100 ? 0.85 : 0;
    }
    if (show(gl.holeTag.tag, gl.holeTag.pos)) gl.holeTag.tag.style.opacity = gl.world.lost.length || dist > 1200 ? 0.8 : 0;
    const cw = new gl.THREE.Vector3(...gl.coreTag.pos).applyMatrix4(gl.galaxy.matrixWorld);
    if (show(gl.coreTag.tag, cw)) gl.coreTag.tag.style.opacity = dist < 2400 ? 0.75 : 0;
  }

  // Проверяем фактическую стоимость отрисовки, а не интервалы между
  // специально ограниченными кадрами. Сглаживание и cooldown исключают скачки.
  function autoQuality(renderMs, now) {
    const gl = view?.gl;
    if (!gl || store.get("yakumo.galaxy.quality", "auto") !== "auto") return;
    if (!gl.qSamples) gl.qSamples = [];
    gl.qSamples.push(renderMs);
    if (gl.qSamples.length < 90) return;
    const avg = gl.qSamples.reduce((a,b) => a+b,0) / gl.qSamples.length;
    gl.qSamples.length = 0;
    if (now - (gl.qualityChanged || 0) < 20000) return;
    const cur = store.get("yakumo.galaxy.auto", "medium");
    const next = avg > 18 ? (cur === "high" ? "medium" : cur === "medium" ? "low" : null)
      : avg < 5 ? (cur === "low" ? "medium" : cur === "medium" ? "high" : null) : null;
    if (next && next !== cur) {
      gl.qualityChanged = now;
      store.set("yakumo.galaxy.auto", next);
      rebuild();
    }
  }

  function stopScene() {
    if (!view) return;
    view.alive = false;
    if (view.raf) { cancelAnimationFrame(view.raf); view.raf = 0; }
    const gl = view.gl;
    if (!gl) return;
    gl.scene.traverse(o => {
      o.geometry?.dispose?.();
      if (Array.isArray(o.material)) o.material.forEach(m => m.dispose?.());
      else o.material?.dispose?.();
    });
    Object.values(gl.tex || {}).forEach(t => t.dispose?.());
    gl.renderer.dispose();
    gl.renderer.domElement.remove();
    view.gl = null;
    view.starting = false;
  }

  document.addEventListener("visibilitychange", () => {
    if (!view?.alive) return;
    if (document.hidden) {
      if (view.raf) cancelAnimationFrame(view.raf);
      view.raf = 0;
    } else {
      if (view.gl) { view.gl.last = 0; view.gl.lastPaint = 0; }
      if (!view.raf) view.raf = requestAnimationFrame(frame);
    }
  });

  function rebuild() {
    if (!view?.gl) return;
    const gl = view.gl;
    gl.q = QUALITY[quality()];
    gl.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, gl.q.ratio));
    gl.w = 0;
    if (data) populate();
  }

  // A truthful timeline, not reconstructed snapshots: only observations made
  // since this client started recording are stored. No private fact text persists.
  function recordObservation(d) {
    const history = store.get("yakumo.galaxy.observations", []);
    const items = Array.isArray(history) ? history.slice(-79) : [];
    const factIds = new Set((d.facts || []).map(f => String(f.id)));
    const previous = store.get("yakumo.galaxy.observationIds", []);
    const added = previous.length ? [...factIds].filter(id => !previous.includes(id)).length : 0;
    store.set("yakumo.galaxy.observationIds", [...factIds].slice(-3000));
    const entry = {time: Date.now(), facts: factIds.size,
      entities: (d.entities || []).length, skills: (d.skills || []).length,
      generations: d.evolution?.total_generations || 0, added};
    const last = items[items.length - 1];
    if (!last || [last.facts,last.entities,last.skills,last.generations].some((v,i) =>
      v !== [entry.facts,entry.entities,entry.skills,entry.generations][i])) {
      items.push(entry); store.set("yakumo.galaxy.observations", items.slice(-80));
    }
  }

  function renderObservations() {
    if (!view?.history) return;
    const entries = store.get("yakumo.galaxy.observations", []);
    const panel = view.history;
    panel.replaceChildren(el("strong", "", "История наблюдений Yakumo"));
    panel.append(el("p", "gx-muted",
      "Только реально сохранённые наблюдения. Прошлое до включения этой функции недоступно."));
    if (!Array.isArray(entries) || !entries.length) {
      panel.append(el("p", "", "Пока нет наблюдений.")); return;
    }
    const first = entries[0], last = entries[entries.length - 1];
    panel.append(el("p", "", "Изменение: факты " + (last.facts-first.facts >= 0 ? "+" : "") +
      (last.facts-first.facts) + ", навыки " + (last.skills-first.skills >= 0 ? "+" : "") +
      (last.skills-first.skills) + ", эволюция +" + (last.generations-first.generations)));
    for (const x of [...entries].reverse().slice(0, 12)) {
      const btn = el("button", "gx-history-event",
        new Date(x.time).toLocaleString() + " · факты " + x.facts +
        " · узлы " + x.entities + " · навыки " + x.skills + " · эксперименты " + x.generations);
      btn.type = "button";
      btn.onclick = () => { location.hash = "#/brain"; };
      panel.append(btn);
    }
  }

  // --- Данные и монтирование ---
  async function load(force = false) {
    if (!force && Date.now() - lastLoad < 60000 && data) return;
    lastLoad = Date.now();
    try {
      const d = await Y.getJSON("/api/brain");
      const sig = x => x && JSON.stringify({
        facts:x.facts.map(f=>[f.id,f.updated,f.archived]),entities:x.entities.map(e=>[e.id,e.area]),
        promises:(x.promises||[]).map(p=>[p.id,p.done]),mind:(x.mind?.thoughts||[]).map(t=>[t.id,t.status]),
        lessons:(x.lessons||[]).length,skills:(x.skills||[]).length,
        improvements:(x.improvements||[]).map(v=>[v.id,v.status]),
        generations:x.evolution?.total_generations||0, branches:x.branches
      });
      const changed = !data || sig(d) !== sig(data);
      data = d;
      recordObservation(d);
      if (changed && view.gl) populate();
    } catch {
      view.note.textContent = L.empty;
      view.note.hidden = false;
    }
  }

  async function mount() {
    if (!view) makeView();
    if (!view.alive) { view.alive = true; if (!document.hidden) view.raf = requestAnimationFrame(frame); }
    view.ctl.place?.();
    load();
    if (view.gl || view.starting) return;
    view.starting = true;
    try {
      const THREE = await loadThree();
      if (startGl(THREE) && data) populate();
    } catch {
      view.note.textContent = L.noGl;
      view.note.hidden = false;
    }
  }

  setInterval(() => { if (view?.host.isConnected && !document.hidden) load(); }, 60000);
  Y.setHome(() => {
    if (!view) makeView();
    queueMicrotask(mount);
    return [view.host];
  });
})();
