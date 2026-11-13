// 9:16 videos (1080×1920). prepareVideo(spec) builds the whole timeline once and returns
// {fps, duration, coverAt, checks}; frame(t) poses every element for time t. Deterministic,
// so the same spec always renders the same video.
(function () {
  const { esc } = window.KIT;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = x => { x = clamp(x); return 1 - Math.pow(1 - x, 3); };
  const prog = (t, a, b) => ease((t - a) / (b - a));
  const LABEL = "Concept · not a client project";
  let TL = null; // timeline state

  const frameCSS = `
  #v{position:relative;width:1080px;height:1920px;overflow:hidden;background-color:#0B0B0B;
     background-image:linear-gradient(rgba(244,241,234,0.035) 1px,transparent 1px),linear-gradient(90deg,rgba(244,241,234,0.035) 1px,transparent 1px);
     background-size:80px 80px;color:#F4F1EA;font-family:Geist,system-ui,sans-serif}
  #v .vh{position:absolute;left:72px;right:72px;top:96px;display:flex;justify-content:space-between;font-size:26px;letter-spacing:.18em;color:#8A867D;white-space:nowrap}
  #v .bar{position:absolute;left:72px;right:72px;top:146px;height:4px;background:rgba(244,241,234,.12)}
  #v .bar i{display:block;height:4px;background:#EAFF00;width:0}
  #v .layer{position:absolute;left:0;right:0;opacity:0}
  #v .cap{position:absolute;left:72px;right:72px;top:236px;display:flex;flex-direction:column;gap:18px;opacity:0}
  #v .cap .k{font-size:30px;letter-spacing:.18em;color:#EAFF00}
  #v .cap .h{font-size:76px;line-height:1;letter-spacing:-.04em}
  #v .cap .row{display:flex;gap:28px;align-items:flex-start}
  #v .cap .n{font-size:64px;line-height:1;color:#EAFF00;flex:none}
  #v .cap .tt{font-size:56px;font-weight:600;line-height:1.1}
  #v .cap .tb{font-size:38px;line-height:1.3;color:#D9D5CA;margin-top:12px}
  #v .hook{position:absolute;left:72px;right:72px;top:236px}
  #v .hook h1{font-size:96px;line-height:.98;letter-spacing:-.045em}
  #v .hook h1 span{display:inline-block;opacity:0}
  #v .ph{position:absolute;left:50%;top:600px}
  #v .wipe{position:absolute;top:0;bottom:0;width:6px;background:#EAFF00;box-shadow:0 0 24px rgba(234,255,0,.6);z-index:60;opacity:0}
  #v .end{position:absolute;left:72px;right:72px;top:420px;display:flex;flex-direction:column;gap:56px;opacity:0}
  #v .end h2{font-size:96px;line-height:.98;letter-spacing:-.045em}
  #v .end .sub{font-size:40px;line-height:1.3;color:#D9D5CA}
  #v .stage-slide{position:absolute;left:0;top:285px;opacity:0}
  #v .stage-slide .s-head{visibility:hidden}
  #v .stage-slide .slide{background:transparent}`;

  function shell(rightLabel) {
    return `<style>${frameCSS}</style><div id="v"><div class="vh mono"><span>Pryce Digital</span><span>${esc(rightLabel)}</span></div><div class="bar"><i></i></div>`;
  }

  // ---------------- redesign video ----------------
  function buildRedesign(spec) {
    const d = spec.data, S = 1.32;
    const W = Math.round(390 * S), BW = W + 20;
    const nb = d.before.items.length, na = d.after.items.length;
    const T = {}; let t = 0;
    T.hook = [t, t += 2.8];
    T.beforeTitle = [t, t += 1.1];
    T.before = d.before.items.map(() => [t, t += 1.6]);
    T.wipe = [t, t += 0.8];
    T.afterTitle = [t, t += 1.1];
    T.after = d.after.items.map(() => [t, t += 1.6]);
    T.end = [t, t += 3.2];
    const words = d.hook.split(/\s+/).map(w => `<span>${esc(w)}</span>`).join(" ");
    const cap = (k, n, it) => `<div class="cap" data-cap="${k}"><div class="row"><span class="n mart">${String(n).padStart(2, "0")}</span><div><div class="tt" data-max-lines="2">${esc(it.title)}</div><div class="tb" data-max-lines="2">${esc(it.body)}</div></div></div></div>`;
    const ttl = (k, kicker, title) => `<div class="cap" data-cap="${k}"><span class="k mono">${esc(kicker)}</span><span class="h mart" data-max-lines="2">${esc(title)}</span></div>`;
    const c = typeof d.cta === "object" ? d.cta : window.KIT.CTA[d.cta || "review"];
    const html = shell(LABEL) +
      `<div class="hook"><h1 class="mart" data-max-lines="3">${words}</h1></div>` +
      ttl("bt", "Before", d.before.title) + d.before.items.map((it, i) => cap(`b${i}`, i + 1, it)).join("") +
      ttl("at", "After", d.after.title) + d.after.items.map((it, i) => cap(`a${i}`, i + 1, it)).join("") +
      `<div class="ph" id="phwrap" style="margin-left:${-BW / 2}px;width:${BW}px"><div style="position:relative">
         <div id="lb" style="position:relative;z-index:1">${window.KIT.phone("phb", d.before.screen, S)}</div>
         <div id="la" style="position:absolute;left:0;top:0;z-index:2">${window.KIT.phone("pha", d.after.screen, S)}</div>
         <div class="wipe" id="wipe"></div></div></div>` +
      `<div class="end"><div style="display:flex;flex-direction:column;gap:28px"><span class="kick mono" style="font-size:30px">${esc(c.kicker)}</span><h2 class="mart" data-max-lines="3">${esc(c.headline)}</h2><p class="sub" data-max-lines="2">${esc(c.sub)}</p></div>
         <div class="card"><span class="mono">${esc(c.label)}</span><span class="u mart">${esc(c.url)}</span></div></div></div>`;
    return { html, T, duration: t, coverAt: 2.4, BW };
  }

  function poseRedesign(t) {
    const { T, duration } = TL;
    const q = s => document.querySelector(s);
    q("#v .bar i").style.width = `${(t / duration * 100).toFixed(2)}%`;
    // hook words
    const ws = document.querySelectorAll("#v .hook h1 span");
    ws.forEach((w, i) => { const p = 1; w.style.opacity = p; w.style.transform = `translateY(${(1 - p) * 40}px)`; });
    const hookOut = prog(t, T.hook[1] - 0.3, T.hook[1]);
    q("#v .hook").style.opacity = 1 - hookOut;
    // phone: rises in during hook, fades back at the end
    const ph = q("#phwrap"); const rise = prog(t, 0.1, 1.0); const endP = prog(t, T.end[0], T.end[0] + 0.6);
    ph.style.opacity = (0.15 + 0.85 * rise) * (1 - 0.88 * endP);
    ph.style.transform = `translateY(${(1 - rise) * 260 + endP * 120}px) scale(${1 - endP * 0.08})`;
    // captions
    const show = (sel, [a, b], last) => { const el = q(sel); if (!el) return; const pin = prog(t, a, a + 0.3), pout = last ? 0 : prog(t, b - 0.2, b); el.style.opacity = t < a || t >= b + (last ? 99 : 0) ? 0 : pin * (1 - pout); el.style.transform = `translateY(${(1 - pin) * 24}px)`; };
    show('[data-cap="bt"]', T.beforeTitle); TL.spec.data.before.items.forEach((_, i) => show(`[data-cap="b${i}"]`, T.before[i]));
    show('[data-cap="at"]', T.afterTitle); TL.spec.data.after.items.forEach((_, i) => show(`[data-cap="a${i}"]`, T.after[i]));
    // wipe from before to after
    const w = prog(t, T.wipe[0], T.wipe[1]);
    const la = q("#la"); la.style.clipPath = `inset(0 ${(100 - w * 100).toFixed(2)}% 0 0)`;
    const wipe = q("#wipe"); wipe.style.opacity = w > 0 && w < 1 ? 1 : 0; wipe.style.left = `${w * TL.BW - 3}px`;
    // markers pop with their caption and stay
    const pop = (root, ranges) => root.querySelectorAll(".mk").forEach(m => { const i = +m.textContent - 1; const r = ranges[i]; if (!r) return; const p = clamp((t - r[0]) / 0.25); const s = p < 1 ? 0.4 + 0.6 * ease(p) + Math.sin(p * Math.PI) * 0.15 : 1; m.style.opacity = t >= r[0] ? 1 : 0; m.style.transform = `scale(${s})`; });
    pop(q("#phb"), TL.markIdx.before); pop(q("#pha"), TL.markIdx.after);
    // end card
    const e = prog(t, T.end[0] + 0.2, T.end[0] + 0.8); const end = q("#v .end"); end.style.opacity = e; end.style.transform = `translateY(${(1 - e) * 40}px)`;
  }

  // ---------------- stat video (stat-carousel data, animated) ----------------
  function buildStat(spec) {
    const d = spec.data; const fmt = window.FORMATS["stat-carousel"];
    const T = []; let t = 0;
    d.slides.forEach((sl, i) => { const len = sl.secs || (sl.type === "cta" ? 3.4 : sl.type === "statement" || sl.type === "loading" ? 3.6 : 3.0); T.push([t, t += len]); });
    const html = shell(d.videoLabel || "Research") + d.slides.map((_, i) => `<div class="stage-slide" data-i="${i}">${fmt.slide(d, i + 1)}</div>`).join("") + `</div>`;
    return { html, T, duration: t, coverAt: Math.min(1.8, T[0][1] - 0.2) };
  }
  function poseStat(t) {
    const { T, duration } = TL;
    document.querySelector("#v .bar i").style.width = `${(t / duration * 100).toFixed(2)}%`;
    document.querySelectorAll("#v .stage-slide").forEach(el => {
      const i = +el.dataset.i, [a, b] = T[i], last = i === T.length - 1;
      const pin = i === 0 ? 1 : prog(t, a, a + 0.35), pout = last ? 0 : prog(t, b - 0.25, b);
      const vis = t >= a && (t < b || last);
      el.style.opacity = vis ? pin * (1 - pout) : 0;
      el.style.transform = `translateY(${(1 - pin) * 40}px)`;
      const lt = t - a;
      el.querySelectorAll('[data-anim="grow"]').forEach((g, k) => { g.style.transformOrigin = "0 50%"; g.style.transform = `scaleX(${ease((lt - 0.3 - k * 0.15) / 0.9)})`; });
      el.querySelectorAll('[data-anim="count"]').forEach(c => {
        const raw = c.dataset.v, m = raw.match(/^([^\d]*)([\d,]*\.?\d+)(.*)$/); if (!m) return;
        const target = parseFloat(m[2].replace(/,/g, "")), dec = (m[2].split(".")[1] || "").length;
        const v = i === 0 ? target : target * ease((lt - 0.15) / 1.0);
        let s = v.toFixed(dec); if (m[2].includes(",")) s = Number(s).toLocaleString("en-AU", { minimumFractionDigits: dec, maximumFractionDigits: dec });
        c.textContent = m[1] + s + m[3];
      });
      const dots = [...el.querySelectorAll('[data-anim="dot"]')];
      dots.forEach((dt, k) => { const on = dt.dataset.on === "1" && lt > 0.4 + k * 0.06; dt.style.background = on ? "var(--acc)" : "rgba(244,241,234,.12)"; });
    });
  }

  window.prepareVideo = async function (spec) {
    const checks = []; window.__checks = checks;
    const stage = document.getElementById("stage");
    let built;
    if (spec.format === "redesign-video") built = buildRedesign(spec);
    else if (spec.format === "stat-video") built = buildStat(spec);
    else return { checks: [{ level: "error", msg: `Unknown video format ${spec.format}` }], fps: 30, duration: 0 };
    stage.innerHTML = built.html;
    await window.KIT.checkFonts(checks);
    await window.KIT.waitImages(checks);
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    TL = { ...built, spec, markIdx: { before: [], after: [] } };
    if (spec.format === "redesign-video") {
      window.KIT.placeMarkers({ phb: spec.data.before.items, pha: spec.data.after.items }, checks);
      TL.markIdx.before = built.T.before; TL.markIdx.after = built.T.after;
      document.querySelectorAll("#v .mk").forEach(m => { m.style.opacity = 0; });
    }
    // layout checks on every caption (they exist in the DOM even while hidden)
    document.querySelectorAll("#v [data-max-lines]").forEach(el => {
      const cs = getComputedStyle(el), lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
      const n = Math.round(el.getBoundingClientRect().height / lh), max = +el.dataset.maxLines;
      if (n > max) checks.push({ level: "error", msg: `Too long for video (${n} lines, max ${max}): "${el.textContent.trim().slice(0, 60)}"` });
    });
    if (spec.format === "redesign-video" && !document.getElementById("v").textContent.toLowerCase().includes("not a client project"))
      checks.push({ level: "error", msg: "Missing the 'not a client project' label" });
    window.frame(0);
    return { fps: 30, duration: Math.round(built.duration * 30) / 30, coverAt: built.coverAt, checks };
  };

  window.frame = function (t) {
    if (!TL) return;
    if (TL.spec.format === "redesign-video") poseRedesign(t); else poseStat(t);
  };
})();
