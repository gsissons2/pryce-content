// Phone-screen block kit. Each block renders a piece of a 390×844 mobile homepage.
// A screen is { theme: {...}, blocks: [ {type, id?, ...props} ] }. Blocks match the Framer
// concept screens (Fernleaf, Southgate, Wattle Creek). New industries: design in Framer first,
// then add the block here. Every block root carries data-block="<id>" so markers can pin to it.
(function () {
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const f = (w, size, lh, fam, extra = "") => `font:${w} ${size}px/${lh} ${fam};${extra}`;
  const PHOTO = p => `url('${window.ASSET_ROOT || "../../assets/photos/"}${p}')`;

  const SVG = {
    status: c => `<svg width="74" height="13" viewBox="0 0 74 13" fill="none"><g fill="${c}"><rect x="0" y="8" width="3" height="4" rx=".8"/><rect x="4.6" y="6" width="3" height="6" rx=".8"/><rect x="9.2" y="3.5" width="3" height="8.5" rx=".8"/><rect x="13.8" y="1" width="3" height="11" rx=".8"/></g><g transform="translate(22 .5)" fill="${c}"><path d="M8 2.2c2.4 0 4.6.9 6.2 2.5l1.1-1.1C13.4 1.7 10.8.6 8 .6S2.6 1.7.7 3.6l1.1 1.1C3.4 3.1 5.6 2.2 8 2.2z"/><path d="M8 5.4c1.5 0 2.9.6 3.9 1.6l1.1-1.1C11.7 4.6 9.9 3.8 8 3.8s-3.7.8-5 2.1l1.1 1.1c1-1 2.4-1.6 3.9-1.6z"/><path d="M8 8.6c.6 0 1.2.2 1.6.7L8 11 6.4 9.3c.4-.5 1-.7 1.6-.7z"/></g><rect x="44.5" y=".5" width="25" height="12" rx="3.8" stroke="${c}" stroke-opacity=".4"/><rect x="46.5" y="2.5" width="21" height="8" rx="2.2" fill="${c}"/><path d="M71 4.5v4c.8-.3 1.3-1.1 1.3-2s-.5-1.7-1.3-2z" fill="${c}" fill-opacity=".45"/></svg>`,
    burger: c => `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 6.5h18M3 12h18M3 17.5h18" stroke="${c}" stroke-width="2" stroke-linecap="round"/></svg>`,
    chev: (c, d) => `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="${d}" stroke="${c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    down: c => `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3.5 5.5L7 9l3.5-3.5" stroke="${c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    arrow: c => `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10m0 0L9 4m4 4l-4 4" stroke="${c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    download: c => `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v8m0 0L4 6m3 3l3-3M2 12h10" stroke="${c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    spinner: () => `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="#D2D2D2" stroke-width="2.5"/><path d="M12 3a9 9 0 0 1 9 9" stroke="#8E8E8E" stroke-width="2.5" stroke-linecap="round"/></svg>`,
    phone: c => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M6.6 10.8a15.2 15.2 0 006.6 6.6l2.2-2.2a1 1 0 011-.25 11.4 11.4 0 003.6.57 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.45.57 3.57a1 1 0 01-.25 1z" fill="${c}"/></svg>`,
    calendar: c => `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="11" rx="1.5" stroke="${c}" stroke-width="1.3"/><path d="M2 6.5h12M5 1.5v3M11 1.5v3" stroke="${c}" stroke-width="1.3" stroke-linecap="round"/></svg>`,
    lock: c => `<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="2" y="5.5" width="8" height="5.5" rx="1" fill="${c}"/><path d="M4 5.5V4a2 2 0 014 0v1.5" stroke="${c}" stroke-width="1.2"/></svg>`,
    drop: c => `<svg width="26" height="32" viewBox="0 0 26 32" fill="none"><path d="M13 1C13 1 2 13.5 2 20.5 2 26.6 6.9 31 13 31s11-4.4 11-10.5C24 13.5 13 1 13 1z" fill="${c}"/><path d="M8 21c0 3 2.2 5 5 5" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/></svg>`,
    map: (pin, bg) => `<svg width="350" height="170" viewBox="0 0 350 170"><rect width="350" height="170" fill="#E9E3D6"/><rect x="205" y="16" width="118" height="62" rx="6" fill="#CFDCC4"/><path d="M-10 122 L360 98" stroke="#FFFFFF" stroke-width="14"/><path d="M140 -10 L168 180" stroke="#FFFFFF" stroke-width="10"/><path d="M-10 40 L360 58" stroke="#FFFFFF" stroke-width="6"/><path d="M58 -10 L76 180" stroke="#FFFFFF" stroke-width="6"/><path d="M268 -10 L286 180" stroke="#FFFFFF" stroke-width="6"/><circle cx="166" cy="106" r="24" fill="${pin}" fill-opacity=".12"/><path d="M166 80c-9 0-16 7-16 16 0 12 16 26 16 26s16-14 16-26c0-9-7-16-16-16z" fill="${pin}"/><circle cx="166" cy="96" r="6" fill="${bg}"/></svg>`
  };

  const wrap = (p, type, style, inner, cls = "") => `<div class="b b-${type} ${cls}" data-block="${esc(p.id || type)}" style="${style}">${inner}</div>`;

  const B = {
    status: (p) => wrap(p, "status", "", `<div class="sb"><span class="tm" style="color:${p.color}">9:41</span>${SVG.status(p.color)}</div>`),

    header: (p) => {
      const logo = p.logoParts
        ? `<div class="row" style="gap:8px">${p.logoIcon ? SVG[p.logoIcon](p.logoIconColor) : ""}<div style="display:flex;flex-direction:column;gap:2px">${p.logoParts.map(l => `<span style="${f(l.w, l.size, 1, l.fam, `letter-spacing:${l.ls || 0}em;color:${l.color}`)}">${esc(l.text)}</span>`).join("")}</div></div>`
        : `<div style="display:flex;flex-direction:column;gap:4px"><span style="${f(p.logoWeight || 400, p.logoSize, 1, p.logoFont, `${p.logoItalic ? "font-style:italic;" : ""}letter-spacing:${p.logoLs || 0}em;color:${p.color}`)}">${esc(p.logo)}</span>${p.sub ? `<span style="${f(500, 12, 1, "Inter", `color:${p.subColor}`)}">${esc(p.sub)}</span>` : ""}</div>`;
      const right = p.right ? `<span style="${f(400, 12, 1, p.rightFont || "Roboto", `color:${p.rightColor || p.color};white-space:pre`)}">${esc(p.right)}</span>` : (p.burger === false ? "" : SVG.burger(p.burgerColor || p.color));
      return wrap(p, "header", `height:${p.height || 52}px;width:100%;${p.border ? `border-bottom:1px solid ${p.border};` : ""}${p.bg ? `background:${p.bg};` : ""}`, `<div class="hdr" style="height:100%;padding:0 ${p.padX || 20}px">${logo}${right}</div>`);
    },

    group: (p, t) => wrap(p, "group", `display:flex;flex-direction:column;width:100%;gap:${p.gap || 0}px;padding:${p.padding || "0"};${p.bg ? `background:${p.bg};` : ""}${p.grow ? "flex:1 1 auto;overflow:hidden;" : ""}`, (p.blocks || []).map(b => render(b, t)).join("")),

    // Full-bleed photo with status bar + header on top (cafe "before" slider, motel "after" header)
    photoOverlay: (p, t) => {
      const inner = (p.blocks || []).map(b => render(b, t)).join("");
      return wrap(p, "photoOverlay", `height:${p.height}px;background-image:${PHOTO(p.photo)};background-position:${p.pos || "center"}`, `<div class="shade" style="background:${p.shade}"></div>${inner}`, "ovl");
    },
    spacer: (p) => wrap(p, "spacer", p.h ? `height:${p.h}px` : "flex:1 1 auto", ""),

    sliderCaption: (p) => wrap(p, "sliderCaption", "display:flex;flex-direction:column;align-items:center;gap:12px;padding:0 32px;text-align:center;width:100%",
      `<span style="${f(300, 12, 1, "Montserrat", "letter-spacing:.4em;color:#fff")}">${esc(p.kicker)}</span>
       <span style="${f(400, 46, 1.05, "'Playfair Display'", "font-style:italic;color:#fff")}">${esc(p.title)}</span>
       <span style="${f(400, 12, 1.4, "'Open Sans'", "color:rgba(255,255,255,.8);white-space:pre")}">${esc(p.tag)}</span>`),

    sliderControls: (p) => {
      const circ = d => `<div style="width:40px;height:40px;border-radius:20px;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.35);display:flex;align-items:center;justify-content:center">${SVG.chev("#fff", d)}</div>`;
      const dots = Array.from({ length: p.dots || 5 }, (_, i) => `<span style="width:8px;height:8px;border-radius:4px;background:${i === (p.active ?? 1) ? "#fff" : "rgba(255,255,255,.4)"}"></span>`).join("");
      return wrap(p, "sliderControls", "height:96px;padding:0 16px;width:100%;display:flex;justify-content:space-between;align-items:center", `${circ("M10 3L5 8l5 5")}<div class="row" style="gap:8px">${dots}</div>${circ("M6 3l5 5-5 5")}`);
    },

    pdfStrip: (p) => wrap(p, "pdfStrip", `height:80px;width:100%;background:${p.bg || "#1C1C1C"};display:flex;align-items:center;justify-content:center;padding:0 24px`,
      `<div class="row" style="gap:10px;height:44px;padding:0 20px;border:1px solid ${p.color}">${SVG.download(p.color)}<span style="${f(600, 11, 1, "Montserrat", `letter-spacing:.16em;color:${p.color}`)}">${esc(p.text)}</span></div>`),

    igLoading: (p) => wrap(p, "igLoading", "flex:1 1 auto;overflow:hidden;width:100%;background:#fff;display:flex;flex-direction:column;align-items:center;gap:10px;padding:22px 20px 0",
      `<span style="${f(400, 22, 1.1, "'Playfair Display'", "font-style:italic;color:#222;text-align:center")}">${esc(p.title)}</span>
       <span style="${f(400, 13, 1.2, "'Open Sans'", "color:#9A9A9A")}">${esc(p.sub || "Loading feed…")}</span>
       <div class="row" style="gap:4px;width:100%;height:114px">${[0, 1, 2].map(() => `<div style="flex:1;height:114px;background:#EDEDED;display:flex;align-items:center;justify-content:center">${SVG.spinner()}</div>`).join("")}</div>`),

    stockHero: (p) => wrap(p, "stockHero", `height:${p.height || 300}px;background-image:${PHOTO(p.photo)};background-position:center;justify-content:center;align-items:center;gap:12px;padding:0 28px;text-align:center`,
      `<div class="shade" style="background:${p.overlay}"></div>
       <span style="${f(800, 24, 1.15, "Montserrat", "letter-spacing:.01em;color:#fff;text-transform:uppercase")}">${esc(p.title)}</span>
       <span style="${f(400, 15, 1.3, "'Open Sans'", "color:rgba(255,255,255,.9)")}">${esc(p.sub)}</span>
       <div style="height:42px;padding:0 26px;background:${p.buttonBg};border-radius:3px;display:flex;align-items:center"><span style="${f(700, 13, 1, "Montserrat", "letter-spacing:.12em;color:#fff")}">${esc(p.button)}</span></div>`, "ovl"),

    longForm: (p) => {
      const field = l => `<div style="flex:1;display:flex;flex-direction:column;gap:5px"><span style="${f(600, 12, 1.2, "'Open Sans'", "color:#444")}">${esc(l)}</span><div style="height:40px;background:#fff;border-radius:2px;border:1px solid #C9C9C9"></div></div>`;
      return wrap(p, "longForm", `flex:1 1 auto;overflow:hidden;width:100%;background:${p.bg || "#F6F6F6"};display:flex;flex-direction:column;gap:12px;padding:22px 20px 0`,
        `<span style="${f(700, 20, 1.2, "Montserrat", `color:${p.titleColor}`)}">${esc(p.title)}</span>
         <span style="${f(400, 13, 1.45, "'Open Sans'", "color:#666")}">${esc(p.intro)}</span>
         ${p.rows.map(r => `<div class="row" style="gap:10px;align-items:flex-start">${r.map(field).join("")}</div>`).join("")}`);
    },

    steps: (p) => wrap(p, "steps", "height:44px;width:100%;background:#fff;border-bottom:1px solid #DADADA;display:flex;align-items:center;justify-content:center;gap:5px;padding:0 10px",
      p.items.map((s, i) => `${i ? `<span style="${f(400, 12, 1, "Roboto", "color:#B5B5B5")}">›</span>` : ""}<span style="${f(i === (p.active || 0) ? 700 : 400, 11.5, 1, "Roboto", `color:${i === (p.active || 0) ? p.activeColor : "#9A9A9A"}`)}">${esc(s)}</span>`).join("")),

    engineForm: (p) => {
      const icon = k => k === "calendar" ? SVG.calendar("#777") : k === "chevron" ? SVG.down("#555") : "";
      const field = fl => `<div style="flex:1;display:flex;flex-direction:column;gap:6px"><span style="${f(500, 12.5, 1.2, "Roboto", "color:#555")}">${esc(fl.label)}</span><div class="row" style="justify-content:space-between;height:42px;padding:0 12px;background:#fff;border-radius:3px;border:1px solid #BDBDBD"><span style="${f(400, 14, 1, "Roboto", `color:${fl.value ? "#333" : "#AAA"}`)}">${esc(fl.value || fl.placeholder || "")}</span>${icon(fl.icon)}</div></div>`;
      return wrap(p, "engineForm", "width:100%;display:flex;flex-direction:column;gap:14px;padding:20px 16px 0",
        `<span style="${f(700, 21, 1.2, "Roboto", "color:#333")}">${esc(p.title)}</span>
         <div data-block="${esc((p.id || "engineForm") + "-card")}" style="background:#fff;border-radius:4px;border:1px solid #D8D8D8;padding:16px;display:flex;flex-direction:column;gap:14px">
           ${p.rows.map(r => `<div class="row" style="gap:10px;align-items:flex-start">${r.map(field).join("")}</div>`).join("")}
           <div data-block="${esc((p.id || "engineForm") + "-button")}" style="height:46px;background:${p.buttonBg};border-radius:3px;display:flex;align-items:center;justify-content:center"><span style="${f(700, 14, 1, "Roboto", "letter-spacing:.05em;color:#fff")}">${esc(p.button)}</span></div>
         </div>
         <span data-block="${esc((p.id || "engineForm") + "-note")}" style="${f(400, 12.5, 1.45, "Roboto", "font-style:italic;color:#777")}">${esc(p.note)}</span>
         <div class="row" style="justify-content:center;gap:6px;padding-top:6px">${SVG.lock("#9A9A9A")}<span style="${f(400, 11.5, 1, "Roboto", "color:#9A9A9A")}">${esc(p.secure)}</span></div>`);
    },

    openRow: (p, t) => wrap(p, "openRow", "display:flex;align-items:center;gap:10px;width:100%",
      `<div class="row" style="gap:8px;padding:7px 12px;border-radius:999px;background:${p.pillBg}"><span style="width:8px;height:8px;border-radius:4px;background:${p.dot}"></span><span style="${f(600, 14, 1, "Inter", `color:${t.accent}`)}">${esc(p.pill)}</span></div><span style="${f(400, 14, 1, "Inter", `color:${t.muted}`)}">${esc(p.sub)}</span>`),

    chip: (p) => wrap(p, "chip", `display:flex;align-items:center;gap:8px;padding:7px 12px;border-radius:999px;background:${p.bg};align-self:flex-start`,
      `<span style="width:8px;height:8px;border-radius:4px;background:${p.dot}"></span><span style="${f(600, 13, 1, "Inter", `color:${p.color || "#fff"}`)}">${esc(p.text)}</span>`),

    h1: (p, t) => wrap(p, "h1", "width:100%", `<h1 style="${f(p.weight || 600, p.size, p.lh || 1.08, p.font || t.display, `letter-spacing:${p.ls ?? -0.025}em;color:${p.color || t.ink};text-wrap:balance`)}">${esc(p.text)}</h1>`),
    para: (p, t) => wrap(p, "para", "width:100%", `<p style="${f(400, p.size || 16, 1.4, p.font || "Inter", `color:${p.color || t.muted};text-wrap:pretty`)}">${esc(p.text)}</p>`),
    photo: (p) => wrap(p, "photo", `height:${p.height}px;border-radius:${p.radius ?? 16}px;background-image:${PHOTO(p.photo)};background-position:${p.pos || "center"}`, "", "ph-img"),

    button: (p, t) => wrap(p, "button", `height:${p.height || 54}px;border-radius:${p.radius ?? 12}px;background:${p.bg || t.accent};padding:0 20px`,
      `<span style="${f(600, p.size || 16, 1, p.font || "Inter", `color:${p.color || "#fff"}`)}">${esc(p.text)}</span>${p.arrow === false ? "" : SVG.arrow(p.color || "#fff")}`, "btn"),

    menuList: (p, t) => wrap(p, "menuList", "display:flex;flex-direction:column;width:100%",
      `<div class="row" style="justify-content:space-between;align-items:flex-end;padding:4px 0 10px"><span style="${f(600, 20, 1, t.display, `letter-spacing:-.01em;color:${t.ink}`)}">${esc(p.title)}</span><span style="${f(500, 14, 1, "Inter", `color:${t.accent};text-decoration:underline`)}">${esc(p.link)}</span></div>` +
      p.items.map(([n, pr]) => `<div class="row" style="justify-content:space-between;padding:12px 0;border-top:1px solid ${t.line}"><span style="${f(400, 15, 1.2, "Inter", `color:${t.ink}`)}">${esc(n)}</span><span style="${f(500, 15, 1.2, "Inter", `color:${t.ink};font-variant-numeric:tabular-nums`)}">${esc(pr)}</span></div>`).join("")),

    map: (p, t) => wrap(p, "map", "display:flex;flex-direction:column;gap:10px;padding-top:8px;width:100%",
      `<span style="${f(600, 20, 1, t.display, `letter-spacing:-.01em;color:${t.ink}`)}">${esc(p.title)}</span><div style="height:170px;border-radius:16px;overflow:hidden">${SVG.map(t.accent, t.bg)}</div>`),

    jobPhotos: (p) => wrap(p, "jobPhotos", `display:flex;gap:8px;width:100%;height:${p.height || 96}px`,
      p.photos.map(ph => `<div style="flex:1;height:100%;border-radius:10px;background:${PHOTO(ph)} center/cover"></div>`).join("")),

    quoteForm: (p, t) => {
      const inp = fl => `<div class="row" style="justify-content:space-between;height:54px;padding:0 14px;border-radius:10px;background:#F8F7F4;border:1px solid ${t.line}"><div style="display:flex;flex-direction:column;gap:4px"><span style="${f(500, 11, 1, "Inter", `color:${t.muted}`)}">${esc(fl.label)}</span><span style="${f(fl.filled ? 600 : 400, 15, 1.1, "Inter", `color:${fl.filled ? t.ink : "#A3A7AE"}`)}">${esc(fl.value)}</span></div>${fl.chevron ? SVG.down(t.ink) : ""}</div>`;
      return wrap(p, "quoteForm", `display:flex;flex-direction:column;gap:8px;width:100%;padding:16px;background:#fff;border-radius:16px;border:1px solid ${t.line};box-shadow:0 1px 2px rgba(14,27,44,.06),0 6px 16px rgba(14,27,44,.06)`,
        `<div style="display:flex;flex-direction:column;gap:4px;padding-bottom:4px"><span style="${f(700, 19, 1.1, t.display, `letter-spacing:-.01em;color:${t.ink}`)}">${esc(p.title)}</span><span style="${f(400, 13, 1.3, "Inter", `color:${t.muted}`)}">${esc(p.sub)}</span></div>
         ${p.fields.map(inp).join("")}
         <div style="height:50px;border-radius:10px;background:${t.ink};display:flex;align-items:center;justify-content:center"><span style="${f(600, 15, 1, "Inter", "color:#fff")}">${esc(p.button)}</span></div>`);
    },

    stickyCall: (p, t) => wrap(p, "stickyCall", `position:absolute;left:0;bottom:0;width:100%;height:92px;z-index:5;background:${p.glass};backdrop-filter:blur(12px);padding:10px 20px 28px;border-top:1px solid ${t.line}`,
      `<div class="btn" style="height:54px;border-radius:12px;background:${p.bg}">${SVG.phone("#fff")}<span style="${f(700, 17, 1, "Inter", "color:#fff;font-variant-numeric:tabular-nums")}">${esc(p.text)}</span></div>`),

    bookingCard: (p, t) => {
      const box = (l, v, chev, w = "flex:1") => `<div class="row" style="${w};justify-content:space-between;height:58px;padding:0 12px;background:${t.box};border-radius:12px"><div style="display:flex;flex-direction:column;gap:5px"><span style="${f(500, 11, 1, "'DM Sans'", `letter-spacing:.04em;color:${t.muted}`)}">${esc(l)}</span><span style="${f(600, 16, 1, "'DM Sans'", `color:${t.ink}`)}">${esc(v)}</span></div>${chev ? SVG.down(t.ink) : ""}</div>`;
      return wrap(p, "bookingCard", "display:flex;flex-direction:column;gap:10px;width:100%;padding:16px;background:#fff;border-radius:18px;box-shadow:0 1px 2px rgba(34,38,31,.08),0 8px 24px rgba(34,38,31,.08)",
        `<div class="row" data-block="dates" style="gap:8px">${p.dates.map(([l, v]) => box(l, v, false)).join("")}</div>
         ${box(p.guests[0], p.guests[1], true, "width:100%")}
         <div class="row" data-block="rate" style="justify-content:space-between;align-items:flex-end;padding:8px 2px 4px"><div style="display:flex;flex-direction:column;gap:5px"><span style="${f(600, 15, 1.1, "'DM Sans'", `color:${t.ink}`)}">${esc(p.room)}</span><span style="${f(400, 13, 1.1, "'DM Sans'", `color:${t.muted}`)}">${esc(p.roomSub)}</span></div><span style="${f(400, 36, 0.9, t.display, `color:${t.ink};font-variant-numeric:tabular-nums`)}">${esc(p.price)}</span></div>
         <div class="btn" data-block="book" style="height:54px;border-radius:12px;background:${t.accent2}"><span style="${f(600, 16, 1, "'DM Sans'", "color:#fff")}">${esc(p.button)}</span>${SVG.arrow("#fff")}</div>
         <span style="${f(400, 12.5, 1.2, "'DM Sans'", `color:${t.muted};text-align:center`)}">${esc(p.note)}</span>`);
    },

    roomCards: (p, t) => wrap(p, "roomCards", "display:flex;flex-direction:column;gap:12px;width:100%",
      `<div class="row" style="justify-content:space-between;align-items:flex-end;padding:0 4px"><span style="${f(400, 24, 1, t.display, `color:${t.ink}`)}">${esc(p.title)}</span><span style="${f(500, 14, 1, "'DM Sans'", `color:${t.accent};text-decoration:underline`)}">${esc(p.link)}</span></div>
       <div class="row" style="gap:10px;align-items:flex-start">${p.rooms.map(r => `<div style="flex:1;display:flex;flex-direction:column;gap:8px"><div style="height:120px;border-radius:12px;background:${PHOTO(r.photo)} center/cover"></div><div class="row" style="justify-content:space-between;padding:0 2px"><span style="${f(600, 15, 1, "'DM Sans'", `color:${t.ink}`)}">${esc(r.name)}</span><span style="${f(400, 14, 1, "'DM Sans'", `color:${t.muted}`)}">${esc(r.price)}</span></div></div>`).join("")}</div>`),

    caption: (p) => wrap(p, "caption", `width:100%;padding:${p.padding || "0 20px 18px"}`, `<span style="${f(500, 14, 1.2, "'DM Sans'", `color:${p.color || "rgba(255,255,255,.92)"}`)}">${esc(p.text)}</span>`)
  };

  function render(b, t) {
    const fn = B[b.type];
    if (!fn) { (window.__checks = window.__checks || []).push({ level: "error", msg: `Unknown block type: ${b.type}` }); return ""; }
    return fn(b, t);
  }

  window.renderScreen = function (screen) {
    const t = screen.theme;
    const vars = `--sbg:${t.bg};--ink:${t.ink}`;
    return `<div class="screen" style="${vars}">${screen.blocks.map(b => render(b, t)).join("")}</div>`;
  };
  window.BLOCK_TYPES = Object.keys(B);
})();
