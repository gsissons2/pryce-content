// Slide frames for each format, marker placement and layout checks.
// boot(spec, params) builds one slide into #stage and resolves with the checks for that slide.
(function () {
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const LABEL = "Concept · not a client project";
  const CTA = {
    review: { kicker: "Is yours doing this?", headline: "We’ll show you what to fix first.", sub: "A free review of your homepage on a phone. Plain English, no obligation.", label: "Book a free review", url: "prycedigital.com/book" },
    redesign: { kicker: "Want one of these?", headline: "We redesign one homepage a week. Free.", sub: "Send us your link. You see it first, before anything gets posted.", label: "Send your link", url: "studio@prycedigital.com" }
  };

  const head = (num, total) => `<div class="s-head mono"><span>Pryce Digital</span><span>${String(num).padStart(2, "0")} / ${String(total).padStart(2, "0")}</span></div>`;
  const foot = (l, r) => `<div class="s-foot"><div class="s-rule"></div><div class="s-foot-row mono"><span>${esc(l)}</span><span>${esc(r)}</span></div></div>`;

  // phone in a bezel, screen scaled by s
  function phone(id, screen, s) {
    const W = Math.round(390 * s), H = Math.round(844 * s), r = Math.round(48 * s);
    return `<div class="bezel" id="${id}" style="width:${W + 20}px;height:${H + 20}px;border-radius:${r + 10}px">
      <div class="scr" style="width:${W}px;height:${H}px;border-radius:${r}px" data-s="${s}">
        <div style="position:absolute;left:0;top:0;transform:scale(${s});transform-origin:0 0">${renderScreen(screen)}</div>
        <div class="island" style="top:${Math.round(11 * s)}px;left:${Math.round((W - 120 * s) / 2)}px;width:${Math.round(120 * s)}px;height:${Math.round(34 * s)}px"></div>
      </div></div>`;
  }

  function callouts(kicker, title, items) {
    return `<div class="col"><div class="col-h"><span class="kick mono">${esc(kicker)}</span><h2 class="mart" data-max-lines="3">${esc(title)}</h2></div>
      <div class="list">${items.map((it, i) => `<div class="item"><span class="n mart">${String(i + 1).padStart(2, "0")}</span><div class="t"><span class="tt" data-max-lines="2">${esc(it.title)}</span><span class="tb" data-max-lines="3">${esc(it.body)}</span></div></div>`).join("")}</div></div>`;
  }

  const FORMATS = {
    "redesign-carousel": {
      count: () => 5,
      slide(d, i) {
        const total = 5;
        if (i === 1) return `<div class="slide start">${head(1, total)}
          <div class="hook"><span class="kick mono">Concept redesign</span><h1 class="mart" data-max-lines="3">${esc(d.hook)}</h1><p class="sub" data-max-lines="2">${esc(d.hookSub)}</p><span class="disc mono">Fictional business · not a client project</span></div>
          <div class="hook-phone">${phone("ph", d.before.screen, 1.1)}</div></div>`;
        if (i === 2 || i === 3) {
          const side = i === 2 ? d.before : d.after;
          return `<div class="slide">${head(i, total)}<div class="mid">${phone("ph", side.screen, 1.1)}${callouts(i === 2 ? "Before" : "After", side.title, side.items)}</div>${foot(LABEL, "Swipe →")}</div>`;
        }
        if (i === 4) return `<div class="slide">${head(4, total)}<div class="sbs">
          <div class="c"><div class="lbl"><span class="mono" style="color:var(--dim)">Before</span><span class="stat">${esc(d.before.stat)}</span></div>${phone("ph0", d.before.screen, 0.95)}</div>
          <div class="c"><div class="lbl"><span class="mono" style="color:var(--acc)">After</span><span class="stat">${esc(d.after.stat)}</span></div>${phone("ph1", d.after.screen, 0.95)}</div>
          </div>${foot(LABEL, "Swipe →")}</div>`;
        const c = typeof d.cta === "object" ? d.cta : CTA[d.cta || "review"];
        return `<div class="slide">${head(5, total)}<div class="cta"><div class="t"><span class="kick mono">${esc(c.kicker)}</span><h2 class="mart" data-max-lines="3">${esc(c.headline)}</h2><p class="sub" data-max-lines="2">${esc(c.sub)}</p></div>
          <div class="card"><span class="mono">${esc(c.label)}</span><span class="u mart">${esc(c.url)}</span></div></div>${foot(LABEL, "prycedigital.com")}</div>`;
      },
      marks(d, i) {
        if (i === 2) return { ph: d.before.items };
        if (i === 3) return { ph: d.after.items };
        return {};
      },
      needsLabel: true
    }
  };

  // ---------- stat carousel (ports of batch 1 posts 1 to 5) ----------
  const big = (v, maxPx) => Math.min(maxPx, Math.floor(900 / (Math.max(String(v).length, 1) * 0.76)));
  const STAT = {
    bignum: d => `<div style="display:flex;flex-direction:column;gap:48px"><span class="kick mono" style="font-size:26px">${esc(d.kicker)}</span>
      <h1 class="mart" style="display:flex;flex-direction:column;gap:8px;line-height:.88;letter-spacing:-.045em"><span data-anim="count" data-v="${esc(d.value)}" data-max-lines="1" style="font-size:${big(d.value, 420)}px;color:var(--acc);white-space:nowrap">${esc(d.value)}</span>${d.unit ? `<span data-max-lines="1" style="font-size:${big(d.unit, 140)}px;white-space:nowrap">${esc(d.unit)}</span>` : ""}</h1>
      <p data-max-lines="4" style="max-width:820px;font-size:48px;line-height:1.25;color:var(--soft);text-wrap:pretty">${esc(d.body)}</p></div>`,
    statement: d => `<div style="display:flex;flex-direction:column;gap:56px"><span class="kick mono" style="font-size:26px">${esc(d.kicker)}</span>
      <h2 class="mart" data-max-lines="5" style="font-size:${d.size || 96}px;line-height:.98;letter-spacing:-.035em">${esc(d.title)}</h2>
      ${d.facts ? `<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:32px">${d.facts.map(f => `<div style="display:flex;flex-direction:column;gap:12px;padding-top:24px;border-top:1px solid var(--rule)"><span class="mono" style="font-size:22px;letter-spacing:.16em;color:var(--dim)">${esc(f.label)}</span><span data-max-lines="3" style="font-size:38px;line-height:1.25;color:var(--soft)">${esc(f.value)}</span></div>`).join("")}</div>` : ""}
      ${d.body ? `<p data-max-lines="4" style="font-size:40px;line-height:1.3;color:var(--soft);text-wrap:pretty">${esc(d.body)}</p>` : ""}</div>`,
    bars: d => {
      const max = d.max || Math.max(...d.bars.map(b => b.value)) * 1.08;
      const mk = d.marker ? `<span style="position:absolute;left:${(d.marker.value / max * 100).toFixed(1)}%;top:-10px;bottom:-10px;border-left:3px dashed var(--fg);z-index:1"></span>` : "";
      return `<div style="display:flex;flex-direction:column;gap:64px"><div style="display:flex;flex-direction:column;gap:24px"><span class="kick mono" style="font-size:26px">${esc(d.kicker)}</span><h2 class="mart" data-max-lines="3" style="font-size:72px;line-height:1;letter-spacing:-.035em">${esc(d.title)}</h2></div>
      <div style="position:relative;display:flex;flex-direction:column;gap:44px">${d.bars.map(b => `<div style="display:flex;flex-direction:column;gap:14px"><div class="mono" style="display:flex;justify-content:space-between;font-size:28px;font-weight:600;letter-spacing:.06em;text-transform:none"><span>${esc(b.label)}</span><span style="color:${b.highlight ? "var(--acc)" : "var(--fg)"}">${esc(b.display ?? b.value + (d.unit || ""))}</span></div>
        <div style="position:relative;height:56px;width:100%;background:rgba(244,241,234,.06)">${mk}<div data-anim="grow" style="height:56px;width:${Math.min(100, b.value / max * 100).toFixed(1)}%;background:${b.highlight ? "var(--acc)" : "var(--soft)"}"></div></div></div>`).join("")}
      ${d.marker ? `<div style="display:flex;align-items:center;gap:20px;padding-top:8px"><span style="width:56px;flex:none;border-top:3px dashed var(--fg)"></span><span data-max-lines="2" style="font-size:32px;line-height:1.3;color:var(--soft)">${esc(d.marker.note)}</span></div>` : ""}</div></div>`;
    },
    percent: d => {
      const total = d.dots || 20, on = Math.round((parseFloat(d.value) / 100) * total);
      return `<div style="display:flex;flex-direction:column;gap:48px"><span class="kick mono" style="font-size:26px">${esc(d.kicker)}</span>
      <h2 class="mart" data-anim="count" data-v="${esc(d.value)}" data-max-lines="1" style="white-space:nowrap;font-size:${big(d.value, 260)}px;line-height:.88;letter-spacing:-.045em">${esc(d.value)}</h2>
      <p data-max-lines="3" style="max-width:860px;font-size:52px;line-height:1.22;color:var(--soft);text-wrap:pretty">${esc(d.body)}</p>
      <div style="display:grid;grid-template-columns:repeat(${total},minmax(0,1fr));gap:10px;max-width:904px">${Array.from({ length: total }, (_, k) => `<span data-anim="dot" data-on="${k < on ? 1 : 0}" style="height:34px;background:${k < on ? "var(--acc)" : "rgba(244,241,234,.12)"}"></span>`).join("")}</div></div>`;
    },
    loading: d => `<div style="display:flex;align-items:center;gap:64px">
      <div style="flex:none;width:340px;height:680px;border:2px solid rgba(244,241,234,.3);border-radius:44px;padding:28px 22px;display:flex;flex-direction:column;gap:18px;background:#121212">
        <span style="align-self:center;width:96px;height:8px;border-radius:4px;background:rgba(244,241,234,.18)"></span><span style="height:220px;border-radius:10px;background:rgba(244,241,234,.08)"></span>
        <span style="height:26px;width:80%;border-radius:6px;background:rgba(244,241,234,.1)"></span><span style="height:26px;width:62%;border-radius:6px;background:rgba(244,241,234,.1)"></span><span style="height:26px;width:70%;border-radius:6px;background:rgba(244,241,234,.1)"></span>
        <span style="flex:1 1 auto"></span><span class="mono" style="height:64px;border:2px dashed rgba(244,241,234,.3);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:600;letter-spacing:.14em;color:var(--dim)">${esc(d.button || "Book now")}</span>
        <span class="mono" style="align-self:center;font-size:18px;letter-spacing:.12em;color:var(--acc);text-transform:none">${esc(d.status || "Still loading · 9.4 s")}</span></div>
      <div style="display:flex;flex-direction:column;gap:40px;min-width:0"><h2 class="mart" data-max-lines="6" style="font-size:${d.size || 56}px;line-height:1;letter-spacing:-.035em">${esc(d.title)}</h2><p data-max-lines="5" style="font-size:34px;line-height:1.3;color:var(--soft)">${esc(d.body)}</p></div></div>`,
    list: d => `<div style="display:flex;flex-direction:column;gap:56px"><div style="display:flex;flex-direction:column;gap:24px"><span class="kick mono" style="font-size:26px">${esc(d.kicker)}</span><h2 class="mart" data-max-lines="3" style="font-size:${d.size || 96}px;line-height:.95;letter-spacing:-.04em">${esc(d.title)}</h2></div>
      <div style="display:flex;flex-direction:column">${d.items.map((it, i) => `<div style="display:grid;grid-template-columns:160px minmax(0,1fr);gap:24px;padding:36px 0;border-top:1px solid var(--rule);${i === d.items.length - 1 ? "border-bottom:1px solid var(--rule)" : ""}"><span class="mart" style="font-size:64px;line-height:1;color:var(--acc)">${String(i + 1).padStart(2, "0")}</span><div style="display:flex;flex-direction:column;gap:10px"><span data-max-lines="2" style="font-size:44px;font-weight:600;line-height:1.15">${esc(it.title)}</span><span data-max-lines="3" style="font-size:32px;line-height:1.3;color:var(--soft)">${esc(it.body)}</span></div></div>`).join("")}</div></div>`
  };
  FORMATS["stat-carousel"] = {
    count: d => d.slides.length,
    slide(d, i) {
      const total = d.slides.length, sl = d.slides[i - 1], last = i === total;
      if (sl.type === "cta") {
        const c = typeof sl.cta === "object" ? sl.cta : CTA[sl.cta || "review"];
        return `<div class="slide">${head(i, total)}<div class="cta"><div class="t"><span class="kick mono">${esc(c.kicker)}</span><h2 class="mart" data-max-lines="3">${esc(c.headline)}</h2><p class="sub" data-max-lines="2">${esc(c.sub)}</p></div>
          <div class="card"><span class="mono">${esc(c.label)}</span><span class="u mart">${esc(c.url)}</span></div></div>${foot(sl.foot || d.footer || "", "prycedigital.com")}</div>`;
      }
      const body = STAT[sl.type] ? STAT[sl.type](sl) : `<p>Unknown slide type ${esc(sl.type)}</p>`;
      if (!STAT[sl.type]) (window.__checks || []).push({ level: "error", msg: `Unknown stat slide type ${sl.type}` });
      return `<div class="slide">${head(i, total)}<div class="mid" style="display:block">${body}</div>${foot(sl.foot || d.footer || "", last ? "prycedigital.com" : "Swipe →")}</div>`;
    },
    needsLabel: false
  };

  window.FORMATS = FORMATS;
  window.KIT = { phone, placeMarkers, runChecks, waitImages, checkFonts, esc, CTA, LABEL };

  // ---------- markers ----------
  function placeMarkers(markMap, checks) {
    for (const [phId, items] of Object.entries(markMap)) {
      const root = document.getElementById(phId); if (!root) continue;
      const scr = root.querySelector(".scr"), sr = scr.getBoundingClientRect(), s = parseFloat(scr.dataset.s);
      (items || []).forEach((it, idx) => {
        if (!it.mark) return;
        const el = scr.querySelector(`[data-block="${CSS.escape(it.mark)}"]`);
        if (!el) { checks.push({ level: "error", msg: `Marker ${idx + 1}: no block "${it.mark}" in screen` }); return; }
        const r = el.getBoundingClientRect();
        const top = Math.max(r.top, sr.top) - sr.top, bottom = Math.min(r.bottom, sr.bottom) - sr.top;
        const left = r.left - sr.left, right = r.right - sr.left, w = right - left, h = bottom - top;
        if (h <= 4) { checks.push({ level: "error", msg: `Marker ${idx + 1}: block "${it.mark}" is off screen` }); return; }
        const a = it.anchor || "right";
        let cx, cy;
        if (typeof a === "object") { cx = left + a.x * w; cy = top + a.y * h; }
        else if (a === "left") { cx = left + 8 * s; cy = top + h / 2; }
        else if (a === "center") { cx = left + w / 2; cy = top + h / 2; }
        else if (a === "top-right") { cx = right - 40 * s; cy = top + 40 * s; }
        else { cx = right - 8 * s; cy = top + h / 2; }
        cx = Math.min(Math.max(cx, 28), sr.width - 28); cy = Math.min(Math.max(cy, 28), sr.height - 28);
        const m = document.createElement("div");
        m.className = "mk"; m.textContent = String(idx + 1);
        m.style.left = `${Math.round(cx - 24)}px`; m.style.top = `${Math.round(cy - 24)}px`;
        scr.appendChild(m);
      });
    }
  }

  // ---------- checks ----------
  function lineCount(el) {
    const cs = getComputedStyle(el); let lh = parseFloat(cs.lineHeight);
    if (isNaN(lh)) lh = parseFloat(cs.fontSize) * 1.2;
    return Math.round(el.getBoundingClientRect().height / lh);
  }
  function lastLineWords(el) {
    const tn = [...el.childNodes].find(n => n.nodeType === 3); if (!tn) return 99;
    const words = tn.textContent.trim().split(/\s+/); if (words.length < 3) return 99;
    const range = document.createRange(); const text = tn.textContent; let idx = text.length, tops = [];
    // walk words from the end and see how many share the last line's top
    let count = 0, lastTop = null, pos = text.length;
    for (let k = words.length - 1; k >= 0; k--) {
      const start = text.lastIndexOf(words[k], pos - 1); if (start < 0) break;
      range.setStart(tn, start); range.setEnd(tn, start + words[k].length);
      const top = Math.round(range.getBoundingClientRect().top);
      if (lastTop === null) lastTop = top;
      if (Math.abs(top - lastTop) > 2) break;
      count++; pos = start;
    }
    return count;
  }
  function runChecks(slide, needsLabel, checks) {
    slide.querySelectorAll("[data-max-lines]").forEach(el => {
      const n = lineCount(el), max = +el.dataset.maxLines;
      if (n > max) checks.push({ level: "error", msg: `Too long (${n} lines, max ${max}): "${el.textContent.trim().slice(0, 60)}"` });
      if (el.scrollWidth > el.clientWidth + 1) checks.push({ level: "error", msg: `Overflows sideways: "${el.textContent.trim().slice(0, 60)}"` });
      const words = el.textContent.trim().split(/\s+/).length;
      if (!el.closest(".cta") && words >= 4 && (el.tagName === "H1" || el.tagName === "H2" || el.classList.contains("tt")) && n > 1 && lastLineWords(el) === 1)
        checks.push({ level: "warn", msg: `Single word on last line: "${el.textContent.trim().slice(0, 60)}"` });
    });
    const sr = slide.getBoundingClientRect();
    slide.querySelectorAll("h1,h2,p,span").forEach(el => {
      if (el.closest(".bezel") || !el.textContent.trim()) return;
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > sr.right - 86 || r.left < sr.left + 86)) checks.push({ level: "error", msg: `Runs past the margin: "${el.textContent.trim().slice(0, 40)}"` });
    });
    const foot = slide.querySelector(".s-foot"), mid = slide.querySelector(".mid,.sbs,.cta");
    if (foot && mid && mid.getBoundingClientRect().bottom > foot.getBoundingClientRect().top - 24)
      checks.push({ level: "error", msg: "Content runs into the footer" });
    const hb = slide.querySelector(".hook");
    if (hb && hb.getBoundingClientRect().bottom > 760) checks.push({ level: "error", msg: "Hook text is too tall, phone would be hidden" });
    if (needsLabel && !slide.textContent.toLowerCase().includes("not a client project"))
      checks.push({ level: "error", msg: "Missing the 'not a client project' label" });
  }

  async function waitImages(checks) {
    const urls = new Set();
    document.querySelectorAll("#stage *").forEach(el => {
      const bg = getComputedStyle(el).backgroundImage;
      (bg.match(/url\("?(.*?)"?\)/g) || []).forEach(m => urls.add(m.replace(/^url\("?|"?\)$/g, "")));
    });
    await Promise.all([...urls].map(u => new Promise(res => {
      const im = new Image(); im.onload = () => res(); im.onerror = () => { checks.push({ level: "error", msg: `Image failed to load: ${u}` }); res(); }; im.src = u;
    })));
  }

  async function checkFonts(checks) {
    const need = ['800 40px "Martian Mono"', '500 20px "Geist Mono"', '400 20px "Geist"', '600 20px "Geist"'];
    await Promise.all(need.map(q => document.fonts.load(q).catch(() => null)));
    await document.fonts.ready;
    need.forEach(q => { if (!document.fonts.check(q)) checks.push({ level: "error", msg: `Font not loaded: ${q}` }); });
  }

  window.boot = async function (spec, params) {
    const checks = []; window.__checks = checks;
    const fmt = FORMATS[spec.format];
    if (!fmt) return [{ level: "error", msg: `Unknown format ${spec.format}` }];
    const stage = document.getElementById("stage");
    stage.innerHTML = fmt.slide(spec.data, params.slide);
    await checkFonts(checks);
    await waitImages(checks);
    // second pass so layout settles with real fonts
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    placeMarkers(fmt.marks ? fmt.marks(spec.data, params.slide) : {}, checks);
    runChecks(stage.querySelector(".slide"), fmt.needsLabel, checks);
    return checks;
  };
})();
