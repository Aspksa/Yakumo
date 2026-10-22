"use strict";

// Эффекты вокруг аватара: частицы на двух холстах, за фигурой и перед ней.
// Координаты в долях размера аватара: фигура занимает [-0.5, 0.5], холст [-0.85, 0.85].

const AvatarFx = (() => {
  const SPAN = 1.7;  // холст больше аватара во столько раз (задано и в app.css: inset -35%)
  const POWER = { low: 0.5, normal: 1, high: 1.8 };
  const rnd = (a, b) => a + Math.random() * (b - a);
  const TAU = Math.PI * 2;

  let host, back, front, bctx, fctx;
  let effects = new Set(), power = 1, frame = 0, last = 0, clock = 0;
  let parts = [];
  let spawned = [];  // частицы, рождённые другими частицами в этом кадре
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  // Мягкое пятно света, нарисованное один раз на цвет: дешевле, чем shadowBlur в каждом кадре.
  const sprites = {};
  function glow(rgb) {
    if (sprites[rgb]) return sprites[rgb];
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, `rgba(${rgb},1)`);
    grad.addColorStop(0.35, `rgba(${rgb},.45)`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
    return (sprites[rgb] = c);
  }
  function dot(ctx, rgb, x, y, r, a) {
    if (a <= 0) return;
    ctx.globalAlpha = Math.min(1, a);
    ctx.drawImage(glow(rgb), x - r, y - r, r * 2, r * 2);
  }

  // --- Виды частиц ---
  // spawn() создаёт частицу, step() двигает её и возвращает false, когда она закончилась.

  const KINDS = {
    sparkles: {
      count: 14,
      spawn() {
        const a = rnd(0, TAU), d = Math.sqrt(Math.random());
        return { x: Math.cos(a) * d * 0.55, y: Math.sin(a) * d * 0.6 - 0.02, t: 0, life: rnd(0.9, 1.9),
                 s: rnd(0.012, 0.028), front: Math.random() < 0.7 };
      },
      step(p, dt) { p.t += dt; return p.t < p.life; },
      draw(ctx, p) {
        const a = Math.sin(Math.PI * p.t / p.life), s = p.s * (0.6 + 0.4 * a);
        dot(ctx, "255,220,140", p.x, p.y, s * 3, a * 0.45);
        star(ctx, p.x, p.y, s, a, "255,244,205");
      },
    },
    burst: {
      count: 0,
      step(p, dt) {
        p.t += dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.94; p.vy *= 0.94;
        return p.t < p.life;
      },
      draw(ctx, p) {
        const a = 1 - p.t / p.life;
        dot(ctx, "255,214,120", p.x, p.y, p.s * 3, a * 0.6);
        star(ctx, p.x, p.y, p.s * (0.5 + a * 0.5), a, "255,248,220");
      },
    },
    foxfire: {
      count: 4,
      spawn(i, n) {
        return { phase: (i / Math.max(n, 1)) * TAU + rnd(-0.3, 0.3), w: rnd(0.22, 0.32), bob: rnd(0, TAU),
                 t: 0, life: Infinity, emit: 0 };
      },
      step(p, dt) {
        p.phase += p.w * dt; p.bob += dt * 1.7; p.t += dt;
        const depth = Math.sin(p.phase);
        p.x = Math.cos(p.phase) * 0.62;
        p.y = 0.12 + depth * 0.18 + Math.sin(p.bob) * 0.025;
        p.front = depth > 0;
        p.k = 0.8 + 0.25 * depth;
        p.emit += dt;
        if (p.emit > 0.12) {  // угольки, поднимающиеся от огонька
          p.emit = 0;
          spawned.push({ kind: "ember", x: p.x + rnd(-0.01, 0.01), y: p.y - 0.02, vy: rnd(-0.12, -0.06),
                       vx: rnd(-0.02, 0.02), t: 0, life: rnd(0.6, 1.1), front: p.front });
        }
        return true;
      },
      draw(ctx, p) {
        const r = 0.032 * p.k, flick = 1 + Math.sin(p.t * 13 + p.bob) * 0.12 + Math.sin(p.t * 7.3) * 0.08;
        dot(ctx, "255,170,70", p.x, p.y, r * 4.2, 0.5);
        ctx.globalAlpha = 0.9;
        const g = ctx.createRadialGradient(p.x, p.y + r * 0.3, 0, p.x, p.y, r * 2.4 * flick);
        g.addColorStop(0, "rgba(255,252,236,1)");
        g.addColorStop(0.35, "rgba(255,218,140,.9)");
        g.addColorStop(1, "rgba(255,150,50,0)");
        ctx.fillStyle = g;
        ctx.beginPath();  // капля огня с языком вверх
        ctx.moveTo(p.x, p.y - r * 2.6 * flick);
        ctx.bezierCurveTo(p.x + r * 0.5, p.y - r * 1.4, p.x + r * 1.1, p.y - r * 0.3, p.x + r, p.y + r * 0.4);
        ctx.arc(p.x, p.y + r * 0.4, r, 0, Math.PI);
        ctx.bezierCurveTo(p.x - r * 1.1, p.y - r * 0.3, p.x - r * 0.5, p.y - r * 1.4, p.x, p.y - r * 2.6 * flick);
        ctx.fill();
      },
    },
    ember: {
      count: 0,
      step(p, dt) { p.t += dt; p.x += p.vx * dt; p.y += p.vy * dt; return p.t < p.life; },
      draw(ctx, p) { dot(ctx, "255,200,110", p.x, p.y, 0.012, (1 - p.t / p.life) * 0.8); },
    },
    petals: {
      count: 14,
      spawn(i, n, first) {
        return { x: rnd(-0.8, 0.8), y: first ? rnd(-0.85, 0.85) : -0.88, vy: rnd(0.07, 0.13), sway: rnd(0.03, 0.07),
                 f: rnd(0.6, 1.3), ph: rnd(0, TAU), rot: rnd(0, TAU), vr: rnd(-1.2, 1.2), spin: rnd(1.5, 3.5),
                 s: rnd(0.016, 0.026), t: 0, front: Math.random() < 0.7, hue: Math.random() };
      },
      step(p, dt) {
        p.t += dt; p.y += p.vy * dt; p.x += Math.sin(p.t * p.f + p.ph) * p.sway * dt * 2; p.rot += p.vr * dt;
        return p.y < 0.9;
      },
      draw(ctx, p) {
        ctx.save();
        ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.scale(Math.cos(p.t * p.spin) * 0.9 + 0.1, 1);
        ctx.globalAlpha = 0.9 * Math.min(1, (0.9 - p.y) * 4);
        ctx.fillStyle = p.hue < 0.6 ? "#f6cfd4" : "#fbe3c4";
        const s = p.s;
        ctx.beginPath();  // лепесток с выемкой на конце
        ctx.moveTo(0, s);
        ctx.bezierCurveTo(s * 1.1, s * 0.4, s * 0.8, -s * 0.9, s * 0.25, -s);
        ctx.lineTo(0, -s * 0.75);
        ctx.lineTo(-s * 0.25, -s);
        ctx.bezierCurveTo(-s * 0.8, -s * 0.9, -s * 1.1, s * 0.4, 0, s);
        ctx.fill();
        ctx.restore();
      },
    },
    dust: {
      count: 36,
      spawn(i, n, first) {
        return { x: rnd(-0.55, 0.55), y: first ? rnd(-0.6, 0.48) : rnd(0.3, 0.5), vy: rnd(-0.1, -0.04),
                 ph: rnd(0, TAU), t: 0, life: rnd(3, 5.5), r: rnd(0.004, 0.009), front: Math.random() < 0.5 };
      },
      step(p, dt) { p.t += dt; p.y += p.vy * dt; p.x += Math.sin(p.t * 1.3 + p.ph) * 0.012 * dt; return p.t < p.life; },
      draw(ctx, p) { dot(ctx, "255,216,120", p.x, p.y, p.r * 3, Math.sin(Math.PI * p.t / p.life) * 0.9); },
    },
    fireflies: {
      count: 9,
      spawn() {
        const a = rnd(0, TAU);
        return { x: Math.cos(a) * 0.6, y: Math.sin(a) * 0.5, vx: 0, vy: 0, ph: rnd(0, TAU), t: 0, life: rnd(8, 16),
                 front: Math.random() < 0.6 };
      },
      step(p, dt) {
        p.t += dt;
        p.vx += (rnd(-1, 1) * 0.25 - p.x * 0.08) * dt;  // бродит и тянется обратно к аватару
        p.vy += (rnd(-1, 1) * 0.25 - p.y * 0.08) * dt;
        p.vx *= 0.985; p.vy *= 0.985;
        p.x += p.vx * dt; p.y += p.vy * dt;
        return p.t < p.life;
      },
      draw(ctx, p) {
        const fade = Math.min(1, p.t, p.life - p.t);
        const a = (0.45 + 0.55 * Math.max(0, Math.sin(p.t * 2.1 + p.ph))) * fade;
        dot(ctx, "232,236,140", p.x, p.y, 0.035, a * 0.55);
        dot(ctx, "255,255,220", p.x, p.y, 0.008, a);
      },
    },
    leaves: {
      count: 7,
      spawn(i, n, first) {
        return { x: rnd(-0.8, 0.8), y: first ? rnd(-0.85, 0.85) : -0.9, vy: rnd(0.06, 0.1), sway: rnd(0.05, 0.1),
                 ph: rnd(0, TAU), rot: rnd(0, TAU), vr: rnd(-1.6, 1.6), s: rnd(0.03, 0.045), t: 0, front: Math.random() < 0.75 };
      },
      step(p, dt) {
        p.t += dt; p.y += p.vy * dt; p.x += Math.sin(p.t * 0.9 + p.ph) * p.sway * dt * 2; p.rot += p.vr * dt;
        return p.y < 0.92;
      },
      draw(ctx, p) {
        ctx.save();
        ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.scale(1, 0.55 + 0.45 * Math.abs(Math.cos(p.t * 1.7 + p.ph)));
        ctx.globalAlpha = 0.95 * Math.min(1, (0.92 - p.y) * 4);
        const s = p.s;
        const g = ctx.createLinearGradient(0, 0, 0, -s);
        g.addColorStop(0, "#c9921f"); g.addColorStop(1, "#f6d77a");
        ctx.fillStyle = g;
        ctx.beginPath();  // веер гинкго с выемкой посередине
        ctx.moveTo(0, 0);
        ctx.lineTo(-s * 0.9, -s * 0.75);
        ctx.quadraticCurveTo(-s * 0.5, -s * 1.15, -s * 0.06, -s * 0.92);
        ctx.lineTo(0, -s * 0.72);
        ctx.lineTo(s * 0.06, -s * 0.92);
        ctx.quadraticCurveTo(s * 0.5, -s * 1.15, s * 0.9, -s * 0.75);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "#b07d18"; ctx.lineWidth = s * 0.08;
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, s * 0.45); ctx.stroke();
        ctx.restore();
      },
    },
    snow: {
      count: 40,
      spawn(i, n, first) {
        return { x: rnd(-0.85, 0.85), y: first ? rnd(-0.85, 0.85) : -0.88, vy: rnd(0.05, 0.12), ph: rnd(0, TAU),
                 r: rnd(0.004, 0.011), t: 0, front: Math.random() < 0.6 };
      },
      step(p, dt) { p.t += dt; p.y += p.vy * dt; p.x += Math.sin(p.t * 1.1 + p.ph) * 0.02 * dt; return p.y < 0.9; },
      draw(ctx, p) { dot(ctx, "255,255,255", p.x, p.y, p.r * 2.4, 0.85 * Math.min(1, (0.9 - p.y) * 5)); },
    },
  };

  function star(ctx, x, y, s, a, rgb) {
    ctx.globalAlpha = Math.max(0, Math.min(1, a));
    ctx.fillStyle = `rgb(${rgb})`;
    ctx.beginPath();  // четырёхлучевая искра
    ctx.moveTo(x, y - s);
    ctx.quadraticCurveTo(x, y, x + s, y);
    ctx.quadraticCurveTo(x, y, x, y + s);
    ctx.quadraticCurveTo(x, y, x - s, y);
    ctx.quadraticCurveTo(x, y, x, y - s);
    ctx.fill();
  }

  // --- Неподвижные рисунки за фигурой ---

  function drawRays(ctx) {
    const cx = 0, cy = -0.08, n = 12, turn = clock * 0.06;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const g = ctx.createRadialGradient(cx, cy, 0.05, cx, cy, 0.85);
    g.addColorStop(0, "rgba(255,206,110,.34)");
    g.addColorStop(1, "rgba(255,206,110,0)");
    ctx.fillStyle = g;
    for (let i = 0; i < n; i++) {
      const a = turn + (i / n) * TAU, w = 0.07 + 0.03 * Math.sin(clock * 0.7 + i);
      ctx.globalAlpha = 0.55 + 0.45 * Math.sin(clock * 0.9 + i * 1.7);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, 0.85, a - w, a + w);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  function drawCircle(ctx) {
    const turn = clock * 0.25, pulse = 0.75 + 0.25 * Math.sin(clock * 1.6);
    ctx.save();
    ctx.translate(0, 0.43);
    ctx.scale(1, 0.24);  // круг на полу в перспективе
    dot(ctx, "255,200,90", 0, 0, 0.75, 0.25 * pulse);
    ctx.globalAlpha = 0.75 * pulse;
    ctx.strokeStyle = "rgb(255,214,120)";
    ctx.lineWidth = 0.008;
    for (const r of [0.6, 0.52, 0.32]) { ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU); ctx.stroke(); }
    ctx.lineWidth = 0.006;
    ctx.save(); ctx.rotate(turn);  // знаки между кольцами
    for (let i = 0; i < 28; i++) {
      ctx.rotate(TAU / 28);
      ctx.beginPath();
      if (i % 3 === 0) { ctx.arc(0.56, 0, 0.012, 0, TAU); } else { ctx.moveTo(0.54, -0.01); ctx.lineTo(0.58, 0.01); }
      ctx.stroke();
    }
    ctx.restore();
    ctx.save(); ctx.rotate(-turn * 0.7);  // звезда из двух треугольников
    for (const off of [0, Math.PI]) {
      ctx.beginPath();
      for (let k = 0; k < 3; k++) {
        const a = off + k * TAU / 3 - Math.PI / 2;
        ctx[k ? "lineTo" : "moveTo"](Math.cos(a) * 0.5, Math.sin(a) * 0.5);
      }
      ctx.closePath(); ctx.stroke();
    }
    ctx.restore();
    ctx.restore();
  }

  // --- Цикл ---

  function fill(first = false) {
    for (const kind of effects) {
      const def = KINDS[kind];
      if (!def?.count) continue;
      const want = Math.max(kind === "foxfire" ? 2 : 1, Math.round(def.count * power));
      const have = parts.filter((p) => p.kind === kind);
      for (let i = have.length; i < want; i++) parts.push({ kind, ...def.spawn(i, want, first) });
      if (have.length > want) {
        const extra = new Set(have.slice(want));
        parts = parts.filter((p) => !extra.has(p));
      }
    }
  }

  function tick(now) {
    frame = 0;
    const dt = Math.min(0.05, (now - (last || now)) / 1000);
    last = now;
    clock += dt;
    parts = parts.filter((p) => KINDS[p.kind].step(p, dt) && (p.kind === "ember" || p.kind === "burst" || effects.has(p.kind)))
      .concat(spawned);
    spawned = [];
    fill();
    for (const [ctx, isFront] of [[bctx, false], [fctx, true]]) {
      const w = ctx.canvas.width;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, w, w);
      ctx.setTransform(w / SPAN, 0, 0, w / SPAN, w / 2, w / 2);
      if (!isFront) {
        if (effects.has("rays")) drawRays(ctx);
        if (effects.has("circle")) drawCircle(ctx);
      }
      for (const p of parts) if (!!p.front === isFront) KINDS[p.kind].draw(ctx, p);
      ctx.globalAlpha = 1;
    }
    if (running()) frame = requestAnimationFrame(tick);
    else clear();
  }

  function running() {
    return !document.hidden && !reduced.matches && host && !host.hidden && (effects.size > 0 || parts.length > 0);
  }

  function clear() {
    for (const ctx of [bctx, fctx]) ctx?.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  }

  function kick() {
    if (!frame && running()) { last = 0; frame = requestAnimationFrame(tick); }
  }

  return {
    init(avatar) {
      host = avatar;
      back = avatar.querySelector(".fx-back");
      front = avatar.querySelector(".fx-front");
      bctx = back.getContext("2d");
      fctx = front.getContext("2d");
      document.addEventListener("visibilitychange", kick);
      reduced.addEventListener?.("change", kick);
    },
    // Размер холстов в настоящих точках экрана: zoom — масштаб страницы.
    resize(zoom = 1) {
      if (!host) return;
      const px = Math.min(1800, Math.round(host.offsetWidth * SPAN * zoom * (devicePixelRatio || 1)));
      for (const c of [back, front]) if (c.width !== px) { c.width = px; c.height = px; }
      kick();
    },
    set(list, strength) {
      const first = effects.size === 0;
      effects = new Set(list.filter((k) => KINDS[k] || k === "rays" || k === "circle"));
      power = POWER[strength] || 1;
      fill(first);
      kick();
    },
    // Россыпь искр при нажатии на аватар.
    burst() {
      if (reduced.matches) return;
      for (let i = 0; i < 18; i++) {
        const a = (i / 18) * TAU + rnd(-0.15, 0.15), v = rnd(0.35, 0.6);
        parts.push({ kind: "burst", x: 0, y: -0.05, vx: Math.cos(a) * v, vy: Math.sin(a) * v, t: 0, life: rnd(0.6, 0.9),
                     s: rnd(0.014, 0.024), front: true });
      }
      kick();
    },
    kick,
  };
})();
