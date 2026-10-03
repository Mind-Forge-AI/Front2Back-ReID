/* Front2Back-ReID project page. Static, no build step. */
(() => {
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const NS = "http://www.w3.org/2000/svg";
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}
function s(tag, attrs = {}, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null) continue;
    if (k === "text") e.textContent = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k);
  return e;
}
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};
const fmt1 = v => (v == null ? "–" : (+v).toFixed(1));
const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(1);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const COND = { rgb_full: "Full RGB", front_crop: "Target crop", front_mask: "Silhouette" };
const CONDS = ["rgb_full", "front_crop", "front_mask"];
const CVAR = { rgb_full: "--s1", front_crop: "--s2", front_mask: "--s3" };

/* ------------------------------------------------------------ theme */
const root = document.documentElement;
const saved = store.get("f2b-theme");
if (saved === "dark" || saved === "light") root.dataset.theme = saved;
$("#theme-toggle").addEventListener("click", () => {
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  store.set("f2b-theme", root.dataset.theme);
  redrawCharts();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => redrawCharts());

/* ------------------------------------------------------------ tooltip */
const tip = $("#tooltip");
function showTip(evt, head, rows) {
  tip.replaceChildren();
  if (head) tip.append(h("div", { class: "t-head", text: head }));
  for (const r of rows) {
    const row = h("div", { class: "t-row" });
    if (r.color) { const i = h("i"); i.style.background = r.color; row.append(i); }
    row.append(h("b", { text: r.value }), h("span", { text: r.label }));
    tip.append(row);
  }
  tip.hidden = false;
  const rect = evt.currentTarget?.getBoundingClientRect?.();
  let x = evt.clientX ?? (rect ? rect.left + rect.width / 2 : 0), y = evt.clientY ?? (rect ? rect.top : 0);
  const w = tip.offsetWidth, ht = tip.offsetHeight;
  x = Math.min(window.innerWidth - w - 8, Math.max(8, x + 14));
  y = y - ht - 12 < 8 ? y + 18 : y - ht - 12;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const hideTip = () => { tip.hidden = true; };
function hover(node, fn) {
  node.setAttribute("tabindex", "0");
  node.addEventListener("pointermove", e => fn(e));
  node.addEventListener("focus", e => fn(e));
  node.addEventListener("pointerleave", hideTip);
  node.addEventListener("blur", hideTip);
}

/* ------------------------------------------------------------ data */
const DATA = { results: null, trials: null, byId: new Map(), picks: null, config: {} };
const getJSON = (u, opt) => fetch(u, { cache: "no-cache" }).then(r => (r.ok ? r.json() : opt ? null : Promise.reject(new Error(u + " " + r.status)))).catch(e => (opt ? null : Promise.reject(e)));
const ready = Promise.all([
  getJSON("site/data/results.json"), getJSON("site/data/trials.json"),
  getJSON("site-config.json", true).then(cfg => Promise.all([cfg, cfg?.model_picks_url ? getJSON(cfg.model_picks_url, true) : null])),
]).then(([res, tri, [cfg, picks]]) => {
  DATA.results = res; DATA.trials = tri.trials; DATA.config = cfg || {}; DATA.picks = picks && picks.runs ? picks : null;
  for (const t of DATA.trials) DATA.byId.set(t.id, t);
  return DATA;
});
const modelLabel = key => (DATA.results.models.find(m => m.key === key) || DATA.results.baselines.find(b => b.key === key) || { label: key }).label;
const cellAcc = (key, cond, eff) => DATA.results.table[eff]?.[key]?.[cond];

/* ------------------------------------------------------------ router */
const VIEWS = ["overview", "try", "explore"];
let current = null;
function route() {
  const raw = decodeURIComponent(location.hash.slice(1)) || "overview";
  let [view, arg] = raw.split("/");
  let anchor = null;
  if (!VIEWS.includes(view)) {
    const target = document.getElementById(raw);
    const sec = target?.closest(".view");
    if (sec) { anchor = target; view = sec.dataset.view; }
    else if (target) { anchor = target; view = current || "overview"; }
    else view = "overview";
  }
  const changed = view !== current;
  for (const v of VIEWS) $(`#view-${v}`).hidden = v !== view;
  $$(".tabs a").forEach(a => (a.dataset.tab === view ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  current = view;
  document.title = view === "overview" ? "Front2Back-ReID" : `${$(`.tabs a[data-tab="${view}"]`)?.textContent || ""} · Front2Back-ReID`;
  if (anchor) requestAnimationFrame(() => anchor.scrollIntoView({ block: "start" }));
  else if (changed) window.scrollTo(0, 0);
  ready.then(() => {
    if (view === "overview") drawResults();
    if (view === "explore") Explore.open(arg);
  });
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------ overview: composition */
function drawComposition() {
  const T = DATA.trials, n = T.length;
  const groups = [
    ["Time of day", t => t.tags.time, [["day", "Day"], ["dawn_dusk", "Dawn or dusk"], ["night", "Night"]]],
    ["Weather", t => t.tags.weather, [["overcast", "Overcast"], ["clear", "Clear"], ["sun_glare", "Sun glare"]]],
    ["Road context", t => t.tags.road, [["highway", "Highway"], ["urban", "Urban"], ["suburban", "Suburban"], ["construction_zone", "Construction"]]],
    ["Rear vehicles per pair, Vᵢ", t => t.tags.vi_bin, [["3", "3"], ["4-5", "4–5"], ["6+", "6 or more"]]],
    ["Front-target occlusion", t => t.tags.front_occ, [["none", "None"], ["partial", "Partial"], ["heavy", "Heavy"]]],
  ];
  const box = $("#composition"); box.replaceChildren();
  for (const [title, f, cats] of groups) {
    const g = h("div", { class: "comp-group" }, h("h4", { text: title }));
    for (const [k, label] of cats) {
      const c = T.filter(t => f(t) === k).length, pct = (100 * c) / n;
      const bar = h("span"); bar.style.width = Math.max(pct, 0.6) + "%";
      const row = h("div", { class: "comp-row" }, h("span", { text: label }), h("div", { class: "bar" }, bar), h("span", { class: "v", text: pct.toFixed(1) + "%" }));
      hover(row, e => showTip(e, title, [{ value: `${c} pairs`, label: `${label} · ${pct.toFixed(1)}%` }]));
      g.append(row);
    }
    box.append(g);
  }
}

/* ------------------------------------------------------------ results */
let reasoningMode = "none";
let sortState = null;
const ROWS = {
  none: [
    ["Retrieval controls", ["random_gallery", "hsv_histogram", "dinov2_vitb14", "siglip2_base"]],
    ["Open-family VLMs", ["llava_onevision_0_5b", "llama4_scout_groq", "qwen3_6_27b_groq"]],
    ["Closed hosted VLMs", ["gpt5_5", "gpt5_4_mini", "gemini_2_5_flash"]],
  ],
  medium: [
    ["Retrieval controls (no reasoning)", ["siglip2_base", "dinov2_vitb14", "hsv_histogram", "random_gallery"]],
    ["Closed hosted VLMs, medium-effort reasoning", ["gpt5_5", "gpt5_4_mini", "gemini_2_5_pro", "gemini_2_5_flash"]],
  ],
};
function resultRow(key, eff) {
  const base = DATA.results.baselines.some(b => b.key === key);
  const e = base ? "none" : eff;
  const cells = DATA.results.table[e][key];
  const prev = eff === "medium" && !base ? DATA.results.table.none[key] : null;
  const ctx = cells.rgb_full && cells.front_crop ? +(cells.rgb_full.acc - cells.front_crop.acc).toFixed(1) : null;
  const m = DATA.results.models.find(x => x.key === key);
  return { key, label: modelLabel(key), sub: base ? "frozen, crop only" : m ? `${m.family === "open" ? "Open" : "Closed"} · ${m.provider}${m.params !== "n/d" ? " · " + m.params : ""}` : "", cells, prev, ctx, base };
}
function drawLeaderboard() {
  const eff = reasoningMode, table = $("#leaderboard");
  $("#leaderboard-sub").textContent = eff === "none"
    ? "Reasoning disabled (paper Table 3). Gemini 2.5 Pro is excluded because its reasoning can’t be disabled."
    : "Medium-effort reasoning (paper Table 4). Retrieval controls repeated for reference.";
  const groups = ROWS[eff].map(([g, keys]) => [g, keys.map(k => resultRow(k, eff))]);
  // best and second best per column among non-human rows
  const rank = {};
  for (const c of CONDS) {
    const vals = groups.flatMap(([, rs]) => rs).map(r => r.cells[c]?.acc).filter(v => v != null).sort((a, b) => b - a);
    rank[c] = [vals[0], vals.find(v => v < vals[0])];
  }
  if (sortState) {
    const { col, dir } = sortState;
    const val = r => (col === "ctx" ? r.ctx : r.cells[col]?.acc) ?? -Infinity;
    for (const g of groups) g[1].sort((a, b) => (val(b) - val(a)) * (dir === "descending" ? 1 : -1));
  }
  const th = (label, col) => {
    const t = h("th", { scope: "col" });
    if (!col) { t.textContent = label; return t; }
    if (sortState?.col === col) t.setAttribute("aria-sort", sortState.dir);
    t.append(h("button", { type: "button", text: label, onclick: () => {
      sortState = sortState?.col === col && sortState.dir === "descending" ? { col, dir: "ascending" } : sortState?.col === col ? null : { col, dir: "descending" };
      drawLeaderboard();
    } }));
    return t;
  };
  const thead = h("thead", {}, h("tr", {}, th("Method"), th("Full RGB", "rgb_full"), th("Target crop", "front_crop"), th("Silhouette", "front_mask"), th("Δctx", "ctx")));
  const cell = (r, c) => {
    const v = r.cells[c];
    if (!v) return h("td", { class: "na", text: "–" });
    const dot = h("span", { class: "dot" }), range = h("span", { class: "range" });
    dot.style.left = v.acc + "%"; dot.style.background = `var(${CVAR[c]})`;
    range.style.left = v.lo + "%"; range.style.width = v.hi - v.lo + "%"; range.style.background = `var(${CVAR[c]})`;
    const dr = r.prev?.[c] ? +(v.acc - r.prev[c].acc).toFixed(1) : null;
    const best = v.acc === rank[c][0];
    const td = h("td", { class: best ? "best" : "" }, h("div", { class: "cell" },
      h("span", {}, h("b", { text: fmt1(v.acc) }), h("span", { class: "ci", text: `[${fmt1(v.lo)}–${fmt1(v.hi)}]` }),
        dr != null ? h("span", { class: "ci delta " + (dr > 0 ? "pos" : dr < 0 ? "neg" : ""), text: `Δr ${signed(dr)}` }) : null),
      h("span", { class: "mini-bar", "aria-hidden": "true" }, h("span", { class: "track" }), range, dot)));
    hover(td, e => showTip(e, `${r.label} · ${COND[c]}`, [{ value: `${fmt1(v.acc)}%`, label: `95% CI ${fmt1(v.lo)}–${fmt1(v.hi)}`, color: css(CVAR[c]) },
      ...(dr != null ? [{ value: signed(dr), label: "vs reasoning disabled" }] : []), ...(best ? [{ value: "Best", label: "in this column" }] : [])]));
    return td;
  };
  const tbody = h("tbody");
  for (const [g, rs] of groups) {
    tbody.append(h("tr", { class: "group" }, h("td", { colspan: 5, text: g })));
    for (const r of rs) {
      tbody.append(h("tr", {}, h("td", { class: "name" }, r.label, h("small", { text: r.sub })), cell(r, "rgb_full"), cell(r, "front_crop"), cell(r, "front_mask"),
        h("td", {}, r.ctx == null ? h("span", { class: "na", text: "–" }) : h("span", { class: "delta " + (r.ctx < 0 ? "neg" : r.ctx > 0 ? "pos" : ""), text: signed(r.ctx) }))));
    }
  }
  const H = DATA.results.human.accuracy;
  const hr = { label: "Human reference", sub: "25 participants · 1,000 judgments", cells: { rgb_full: H.rgb_full, front_crop: H.front_crop }, ctx: +(H.rgb_full.acc - H.front_crop.acc).toFixed(1) };
  tbody.append(h("tr", { class: "group" }, h("td", { colspan: 5, text: "People" })));
  const saveRank = { ...rank }; for (const c of CONDS) rank[c] = [null];
  tbody.append(h("tr", { class: "human" }, h("td", { class: "name" }, hr.label, h("small", { text: hr.sub })), cell(hr, "rgb_full"), cell(hr, "front_crop"), cell(hr, "front_mask"),
    h("td", {}, h("span", { class: "delta pos", text: signed(hr.ctx) }))));
  Object.assign(rank, saveRank);
  table.replaceChildren(h("caption", { class: "sr-only", style: "position:absolute;left:-9999px", text: "Rank-1 accuracy (%) with 95% BCa intervals" }), thead, tbody);
}

function axisX(g, x, ticks, y0, y1, fmt = v => v) {
  for (const t of ticks) {
    g.append(s("line", { class: "gridline", x1: x(t), x2: x(t), y1: y0, y2: y1 }));
    g.append(s("text", { x: x(t), y: y1 + 16, "text-anchor": "middle", class: "muted", text: fmt(t) }));
  }
}
function svgBox(container, W, H) {
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  container.replaceChildren(svg);
  return svg;
}
function legend(el, items) {
  el.replaceChildren(...items.map(it => {
    const i = h("i", { class: it.shape || "" }); i.style.background = it.color;
    return h("span", {}, i, it.label);
  }));
}

function drawAblation() {
  const eff = reasoningMode, box = $("#ablation-chart");
  const keys = eff === "none" ? ["qwen3_6_27b_groq", "gpt5_5", "gemini_2_5_flash", "llama4_scout_groq", "gpt5_4_mini", "llava_onevision_0_5b"]
                              : ["gpt5_5", "gemini_2_5_pro", "gpt5_4_mini", "gemini_2_5_flash"];
  const rows = keys.map(k => ({ key: k, label: modelLabel(k), cells: DATA.results.table[eff][k] }));
  const W = Math.max(320, box.clientWidth || 900), small = W < 560;
  const L = small ? 112 : 170, R = 16, top = 14, rowH = 34, Hh = top + rows.length * rowH + 30;
  const svg = svgBox(box, W, Hh);
  svg.setAttribute("aria-label", `Dot plot of Rank-1 accuracy for ${rows.length} VLMs across three front-evidence conditions`);
  const x0 = small ? 0 : 0, x = v => L + ((v - x0) / (100 - x0)) * (W - L - R);
  const g = s("g"); svg.append(g);
  axisX(g, x, [0, 20, 40, 60, 80, 100], top - 8, top + rows.length * rowH, v => v + "%");
  const H = DATA.results.human.accuracy, sig = DATA.results.table.none.siglip2_base.front_crop.acc;
  const refs = [[sig, `SigLIP2, crop ${fmt1(sig)}%`, css("--muted")], [H.front_crop.acc, `Humans, crop ${fmt1(H.front_crop.acc)}%`, css("--s2")], [H.rgb_full.acc, `Humans, full RGB ${fmt1(H.rgb_full.acc)}%`, css("--s1")]];
  for (const [v, , color] of refs) g.append(s("line", { x1: x(v), x2: x(v), y1: top - 10, y2: top + rows.length * rowH, stroke: color, "stroke-width": 1.5, opacity: 0.9 }));
  rows.forEach((r, i) => {
    const y = top + i * rowH + rowH / 2;
    const row = s("g");
    row.append(s("rect", { class: "hl", x: 0, y: y - rowH / 2, width: W, height: rowH, rx: 4 }));
    row.append(s("text", { x: L - 12, y: y + 4, "text-anchor": "end", class: "strong", text: small ? r.label.replace("LLaVA-OneVision", "LLaVA-OV").replace("Gemini 2.5", "Gem. 2.5") : r.label }));
    row.append(s("line", { class: "gridline", x1: L, x2: W - R, y1: y, y2: y }));
    for (const c of CONDS) {
      const v = r.cells[c]; if (!v) continue;
      const col = css(CVAR[c]);
      row.append(s("line", { x1: x(v.lo), x2: x(v.hi), y1: y, y2: y, stroke: col, "stroke-width": 3, "stroke-linecap": "round", opacity: 0.35 }));
    }
    for (const c of CONDS) {
      const v = r.cells[c]; if (!v) continue;
      row.append(s("circle", { cx: x(v.acc), cy: y, r: 5.5, fill: css(CVAR[c]), stroke: css("--surface"), "stroke-width": 2 }));
    }
    const hit = s("rect", { class: "hit", x: 0, y: y - rowH / 2, width: W, height: rowH });
    row.append(hit);
    hover(hit, e => { $$(".hl", svg).forEach(n => n.classList.remove("on")); row.firstChild.classList.add("on");
      showTip(e, r.label + (eff === "medium" ? " · reasoning" : ""), CONDS.filter(c => r.cells[c]).map(c => ({ value: fmt1(r.cells[c].acc) + "%", label: `${COND[c]} [${fmt1(r.cells[c].lo)}–${fmt1(r.cells[c].hi)}]`, color: css(CVAR[c]) }))); });
    hit.addEventListener("pointerleave", () => row.firstChild.classList.remove("on"));
    g.append(row);
  });
  legend($("#ablation-legend"), [...CONDS.map(c => ({ label: COND[c], color: css(CVAR[c]) })),
    ...refs.map(([, label, color]) => ({ label, color, shape: "line" }))]);
}

function drawReasoning() {
  const box = $("#reasoning-chart"), eff = DATA.results.reasoning_effects;
  const models = ["gpt5_5", "gpt5_4_mini", "gemini_2_5_flash"];
  const W = Math.max(300, box.clientWidth || 520), L = 118, R = 46, top = 8, bar = 12, gap = 2, groupGap = 18;
  const groupH = 3 * bar + 2 * gap, Hh = top + models.length * groupH + (models.length - 1) * groupGap + 30;
  const svg = svgBox(box, W, Hh);
  svg.setAttribute("aria-label", "Bar chart of the paired change in Rank-1 accuracy from enabling reasoning, for three models and three conditions");
  const lo = -5, hi = 20, x = v => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const g = s("g"); svg.append(g);
  axisX(g, x, [-5, 0, 5, 10, 15, 20], top, Hh - 30, v => (v > 0 ? "+" : "") + v);
  g.append(s("line", { class: "axis", x1: x(0), x2: x(0), y1: top, y2: Hh - 30, "stroke-width": 1.5 }));
  models.forEach((m, i) => {
    const y0 = top + i * (groupH + groupGap);
    g.append(s("text", { x: L - 10, y: y0 + groupH / 2 + 4, "text-anchor": "end", class: "strong", text: modelLabel(m) }));
    CONDS.forEach((c, j) => {
      const d = eff.find(e => e.model === m && e.condition === c); if (!d) return;
      const y = y0 + j * (bar + gap), col = css(CVAR[c]);
      const xa = x(Math.min(0, d.delta)), xb = x(Math.max(0, d.delta)), w = Math.max(1, xb - xa), r = Math.min(4, w);
      // rounded data end, square at baseline
      const p = d.delta >= 0 ? `M${xa},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${bar - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${w - r}z`
                             : `M${xb},${y}h-${w - r}a${r},${r} 0 0 0 -${r},${r}v${bar - 2 * r}a${r},${r} 0 0 0 ${r},${r}h${w - r}z`;
      const mark = s("path", { d: p, fill: col });
      g.append(mark);
      g.append(s("line", { x1: x(d.lo), x2: x(d.hi), y1: y + bar / 2, y2: y + bar / 2, stroke: css("--ink"), "stroke-width": 1.2, opacity: 0.55 }));
      g.append(s("line", { x1: x(d.lo), x2: x(d.lo), y1: y + 3, y2: y + bar - 3, stroke: css("--ink"), "stroke-width": 1.2, opacity: 0.55 }));
      g.append(s("line", { x1: x(d.hi), x2: x(d.hi), y1: y + 3, y2: y + bar - 3, stroke: css("--ink"), "stroke-width": 1.2, opacity: 0.55 }));
      g.append(s("text", { x: Math.max(x(d.hi), xb) + 5, y: y + bar - 2, "font-size": 11, text: signed(d.delta) }));
      const hit = s("rect", { class: "hit", x: L, y: y - 1, width: W - L, height: bar + 2 });
      g.append(hit);
      const crosses = d.lo <= 0;
      hover(hit, e => showTip(e, `${modelLabel(m)} · ${COND[c]}`, [
        { value: signed(d.delta) + " pts", label: `95% CI ${signed(d.lo)} to ${signed(d.hi)}`, color: col },
        { value: `${fmt1(d.none)} → ${fmt1(d.medium)}`, label: "disabled → medium" },
        ...(crosses ? [{ value: "n.s.", label: "interval crosses zero" }] : [])]));
    });
  });
  legend($("#reasoning-legend"), CONDS.map(c => ({ label: COND[c], color: css(CVAR[c]) })));
}

const STRATA_SERIES = [["gpt5_5", "GPT-5.5", "--s1"], ["siglip2_base", "SigLIP2 Base", "--s2"], ["llama4_scout_groq", "Llama 4 Scout", "--s3"]];
function strataPanels() {
  const S = DATA.results.strata, Hs = DATA.results.human.strata;
  const hum = name => Hs.find(x => x.factor === name)?.bins;
  const cap = v => v.charAt(0).toUpperCase() + v.slice(1).replace("_", " ");
  return [
    { title: "Rear vehicles per pair, Vᵢ", data: S.difficulty.candidate_count_bin, human: hum("Rear-gallery size"), label: b => b },
    { title: "Front-target scale", data: S.difficulty.front_target_bbox_size_bin, human: hum("Front-target scale"), label: cap },
    { title: "Rear-target scale", data: S.context.rear_target_bbox_size_bin, human: hum("Rear-target scale"), label: cap },
    { title: "Rear-target occlusion", data: S.context.rear_target_occlusion_bin, label: cap },
  ];
}
function drawStrata() {
  const box = $("#strata"); box.replaceChildren();
  const panels = strataPanels();
  const all = panels.flatMap(p => Object.values(p.data).flat().map(d => d.lo).concat((p.human || []).map(d => d.lo)));
  const ymin = Math.max(0, Math.floor(Math.min(...all) / 10) * 10);
  const star = (cx, cy, r) => { let d = ""; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r; d += (i ? "L" : "M") + (cx + rr * Math.cos(a)).toFixed(2) + "," + (cy + rr * Math.sin(a)).toFixed(2); } return d + "Z"; };
  for (const p of panels) {
    const fig = h("figure", {}, h("h4", { text: p.title }));
    const holder = h("div", { class: "chart" }); fig.append(holder); box.append(fig);
    const W = 260, Hh = 190, L = 34, R = 10, T = 8, B = 36;
    const svg = svgBox(holder, W, Hh);
    svg.setAttribute("aria-label", `${p.title}: Rank-1 accuracy by stratum`);
    const bins = p.data.gpt5_5.map(d => d.bin), n = bins.length;
    const x = i => L + (n === 1 ? 0.5 : i / (n - 1)) * (W - L - R - 16) + 8;
    const y = v => T + (1 - (v - ymin) / (100 - ymin)) * (Hh - T - B);
    for (let t = ymin; t <= 100; t += 20) {
      svg.append(s("line", { class: "gridline", x1: L, x2: W - R, y1: y(t), y2: y(t) }));
      svg.append(s("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", class: "muted", "font-size": 10.5, text: t }));
    }
    bins.forEach((b, i) => {
      svg.append(s("text", { x: x(i), y: Hh - B + 15, "text-anchor": "middle", "font-size": 10.5, text: p.label(b) }));
      svg.append(s("text", { x: x(i), y: Hh - B + 28, "text-anchor": "middle", class: "muted", "font-size": 9.5, text: "n=" + p.data.gpt5_5[i].n }));
    });
    const series = STRATA_SERIES.map(([k, label, v]) => ({ label, color: css(v), pts: p.data[k], marker: "dot" }));
    if (p.human) series.push({ label: "Humans (pooled)", color: css("--human"), pts: p.human, marker: "star" });
    const off = [-4.5, -1.5, 1.5, 4.5];
    series.forEach((se, si) => {
      const dx = off[si] || 0;
      se.pts.forEach((d, i) => svg.append(s("line", { x1: x(i) + dx, x2: x(i) + dx, y1: y(d.lo), y2: y(d.hi), stroke: se.color, "stroke-width": 1.2, opacity: 0.5 })));
      svg.append(s("path", { d: se.pts.map((d, i) => (i ? "L" : "M") + (x(i) + dx) + "," + y(d.acc)).join(""), fill: "none", stroke: se.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    });
    series.forEach((se, si) => {
      const dx = off[si] || 0;
      se.pts.forEach((d, i) => svg.append(se.marker === "star"
        ? s("path", { d: star(x(i) + dx, y(d.acc), 6.5), fill: se.color, stroke: css("--surface"), "stroke-width": 1.5 })
        : s("circle", { cx: x(i) + dx, cy: y(d.acc), r: 4, fill: se.color, stroke: css("--surface"), "stroke-width": 2 })));
    });
    bins.forEach((b, i) => {
      const w = (W - L - R) / n;
      const band = s("rect", { class: "hl", x: x(i) - w / 2, y: T, width: w, height: Hh - T - B, rx: 4 });
      const hit = s("rect", { class: "hit", x: x(i) - w / 2, y: 0, width: w, height: Hh });
      svg.append(band, hit);
      hover(hit, e => { band.classList.add("on"); showTip(e, `${p.title}: ${p.label(b)} (n=${p.data.gpt5_5[i].n})`, series.map(se => ({ value: fmt1(se.pts[i].acc) + "%", label: `${se.label} [${fmt1(se.pts[i].lo)}–${fmt1(se.pts[i].hi)}]${se.marker === "star" ? ", n=" + se.pts[i].n : ""}`, color: se.color }))); });
      hit.addEventListener("pointerleave", () => band.classList.remove("on"));
      hit.addEventListener("blur", () => band.classList.remove("on"));
    });
  }
  legend($("#strata-legend"), [...STRATA_SERIES.map(([, l, v]) => ({ label: l + " (crop)", color: css(v) })), { label: "Humans (RGB + crop pooled)", color: css("--human"), shape: "star" }]);
  // data table
  const det = h("details", { class: "quotes" }, h("summary", { text: "Show as a table" }));
  const tb = h("table", { class: "mini" });
  tb.append(h("thead", {}, h("tr", {}, h("th", { text: "Stratum" }), h("th", { text: "Bin" }), h("th", { text: "n" }), ...STRATA_SERIES.map(([, l]) => h("th", { text: l })), h("th", { text: "Humans" }))));
  const body = h("tbody");
  for (const p of panels) p.data.gpt5_5.forEach((d, i) => body.append(h("tr", {}, h("td", { text: p.title }), h("td", { text: p.label(d.bin) }), h("td", { text: d.n }),
    ...STRATA_SERIES.map(([k]) => h("td", { text: fmt1(p.data[k][i].acc) })), h("td", { text: p.human ? fmt1(p.human[i].acc) : "–" }))));
  tb.append(body); det.append(tb); box.append(h("div", { style: "grid-column:1/-1" }, det));
}

function drawParticipants() {
  const box = $("#participants-chart"), P = DATA.results.human.participant_scores;
  const conds = ["rgb_full", "front_crop"];
  const maxStack = Math.max(...conds.map(c => Math.max(...Object.values(P.reduce((m, p) => ((m[p[c]] = (m[p[c]] || 0) + 1), m), {})))));
  const W = Math.max(300, box.clientWidth || 480), L = 92, R = 16, T = 18, gap = 8.5, rowH = maxStack * gap + 34, Hh = T + 2 * rowH + 22;
  const svg = svgBox(box, W, Hh);
  svg.setAttribute("aria-label", "Stacked dot plot of 25 participants' accuracy in each condition");
  const x = v => L + ((v - 67.5) / 35) * (W - L - R);
  axisX(svg, x, [70, 80, 90, 100], T - 10, T + 2 * rowH - 8, v => v + "%");
  conds.forEach((c, ri) => {
    const base = T + ri * rowH + rowH - 22, col = css(CVAR[c]);
    svg.append(s("line", { class: "axis", x1: L, x2: W - R, y1: base + 6, y2: base + 6 }));
    svg.append(s("text", { x: L - 12, y: base - 10, "text-anchor": "end", class: "strong", text: COND[c] }));
    const counts = {};
    for (const p of [...P].sort((a, b) => a[c] - b[c])) {
      const k = p[c], idx = (counts[k] = (counts[k] || 0) + 1);
      svg.append(s("circle", { cx: x(k), cy: base - (idx - 1) * gap, r: 3.6, fill: col, stroke: css("--surface"), "stroke-width": 1.2 }));
    }
    const acc = DATA.results.human.accuracy[c].acc;
    svg.append(s("path", { d: `M${x(acc)},${base + 7}l-5,8h10z`, fill: css("--ink") }));
    svg.append(s("text", { x: x(acc) - 8, y: base + 15, "text-anchor": "end", "font-size": 11, text: `pooled ${fmt1(acc)}%` }));
    for (const v of Object.keys(counts).map(Number)) {
      const hit = s("rect", { class: "hit", x: x(v) - 10, y: base - maxStack * gap, width: 20, height: maxStack * gap + 8 });
      svg.append(hit);
      hover(hit, e => showTip(e, COND[c], [{ value: `${v}%`, label: `${counts[v]} participant${counts[v] > 1 ? "s" : ""} (${v / 5} of 20 correct)`, color: col }]));
    }
  });
}

function drawLatency() {
  const box = $("#latency-chart"), L = DATA.results.human.latency_by_outcome_s;
  const rows = [["Correct", "rgb_full", "rgb_full:1"], ["Correct", "front_crop", "front_crop:1"], ["Incorrect", "rgb_full", "rgb_full:0"], ["Incorrect", "front_crop", "front_crop:0"]];
  const W = Math.max(300, box.clientWidth || 480), Lm = 92, R = 40, T = 10, rowH = 30, Hh = T + rows.length * rowH + 40;
  const svg = svgBox(box, W, Hh);
  svg.setAttribute("aria-label", "Median and interquartile range of human decision time by outcome and condition");
  const x = v => Lm + (v / 45) * (W - Lm - R);
  axisX(svg, x, [0, 10, 20, 30, 40], T, T + rows.length * rowH + 8, v => v + " s");
  rows.forEach(([o, c, k], i) => {
    const d = L[k], y = T + i * rowH + rowH / 2 + (i >= 2 ? 8 : 0), col = css(CVAR[c]);
    if (i % 2 === 0) svg.append(s("text", { x: Lm - 12, y: y + rowH / 2 + 4, "text-anchor": "end", class: "strong", text: o }));
    svg.append(s("line", { x1: x(d.q25), x2: x(d.q75), y1: y, y2: y, stroke: col, "stroke-width": 4, "stroke-linecap": "round", opacity: 0.45 }));
    svg.append(s("circle", { cx: x(d.median), cy: y, r: 5, fill: col, stroke: css("--surface"), "stroke-width": 2 }));
    svg.append(s("text", { x: x(d.q75) + 6, y: y + 4, "font-size": 11, text: `${d.median.toFixed(1)} s` }));
    const hit = s("rect", { class: "hit", x: Lm, y: y - rowH / 2, width: W - Lm, height: rowH });
    svg.append(hit);
    hover(hit, e => showTip(e, `${o} answers · ${COND[c]}`, [{ value: `${d.median.toFixed(1)} s`, label: "median", color: col }, { value: `${d.q25.toFixed(1)}–${d.q75.toFixed(1)} s`, label: "IQR" }, { value: d.n, label: "responses" }]));
  });
  legend($("#latency-legend"), ["rgb_full", "front_crop"].map(c => ({ label: COND[c], color: css(CVAR[c]) })));
}

let resultsDrawn = false;
function drawResults() {
  drawLeaderboard(); drawStrata();
  $("#reasoning-note").textContent = reasoningMode === "none" ? "Paper Table 3" : "Paper Table 4 · Gemini 2.5 Pro added; Qwen, Llama and LLaVA weren’t run with reasoning";
  resultsDrawn = true;
}
$$("#reasoning-seg button").forEach(b => b.addEventListener("click", () => {
  reasoningMode = b.dataset.mode; sortState = null;
  $$("#reasoning-seg button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  ready.then(drawResults);
}));
function redrawCharts() {
  if (!DATA.results) return;
  if (current === "overview") drawResults(); else resultsDrawn = false;
  if (current === "try" && Try.state?.done) Try.renderDone();
}
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (current === "overview") drawResults(); }, 150); });

/* ------------------------------------------------------------ shared: pair viewer */
const BOX_PX = { label: 12.5, lh: 18, gap: 2 };
function picksFor(pid, cond) {
  if (!DATA.picks) return [];
  const out = [];
  for (const [run, r] of Object.entries(DATA.picks.runs)) {
    const [model, c, eff] = run.split(":");
    if (c !== cond) continue;
    const v = r.picks?.[pid]; if (v == null) continue;
    const pick = typeof v === "string" ? v : v.c;
    out.push({ run, model, eff, label: modelLabel(model) + (eff === "medium" ? " (R)" : ""), pick, conf: v.p, reason: v.r });
  }
  return out;
}
function pickPills(trial, cond) {
  const list = picksFor(trial.id, cond);
  if (!list.length) return null;
  const wrap = h("div", { class: "pick-list" }, h("span", { class: "hint", text: "Model picks:" }));
  for (const p of list) {
    const pill = h("span", { class: "pick " + (p.pick === trial.answer ? "ok" : "no") }, `${p.label}: ${p.pick}`);
    if (p.reason) pill.title = p.reason;
    wrap.append(pill);
  }
  return wrap;
}
const overlap = (a, b) => Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));

/* A two-panel front/rear viewer with screen-sized box labels, per-panel zoom and
   candidate close-ups. Used by both the Try and Explore tabs. */
class Viewer {
  constructor(root, opts = {}) {
    this.opts = opts; this.zooms = { front: 1, rear: 1 }; this.state = {};
    const zoomCtl = which => h("span", { class: "zoom-ctl", role: "group", "aria-label": `${which === "front" ? "Front" : "Rear"} image zoom` },
      ...[1, 2, 3].map(z => h("button", { type: "button", "data-zoom": z, "aria-pressed": String(z === 1), text: z + "×", onclick: () => this.zoom(which, z) })));
    this.frontCap = h("span", { class: "cap" }); this.rearCap = h("span", { class: "cap" });
    this.fImg = h("img", { alt: "", decoding: "async" }); this.fSvg = s("svg", { "aria-hidden": "true" });
    this.rImg = h("img", { alt: "", decoding: "async" }); this.rSvg = s("svg", { "aria-hidden": "true" });
    this.fStage = h("div", { class: "stage" }, this.fImg, this.fSvg);
    this.rStage = h("div", { class: "stage" }, this.rImg, this.rSvg);
    this.fZoom = h("div", { class: "zoomer" }, h("div", { class: "zoom-inner" }, this.fStage));
    this.rZoom = h("div", { class: "zoomer" }, h("div", { class: "zoom-inner" }, this.rStage));
    this.close = h("div", { class: "closeups", role: opts.onPick ? "radiogroup" : null, "aria-label": "Candidate close-ups" });
    this.closeWrap = h("div", { class: "closeup-wrap" }, h("p", { class: "closeup-title" }, h("b", { text: "Candidate close-ups" }), h("span", { class: "hint", text: opts.closeNote || "Enlarged from the rear frame" })), this.close);
    root.replaceChildren(h("div", { class: "arena" },
      h("figure", { class: "panel front-panel" }, h("figcaption", {}, h("span", { class: "tag", text: "Front-left camera" }), this.frontCap, zoomCtl("front")), this.fZoom),
      h("figure", { class: "panel rear-panel" }, h("figcaption", {}, h("span", { class: "tag", text: "Rear-left camera" }), this.rearCap, zoomCtl("rear")), this.rZoom)),
      this.closeWrap);
    this.root = root;
    this.ro = new ResizeObserver(() => { this.layoutLabels(); this.layoutFront(); });
    this.ro.observe(this.rStage); this.ro.observe(this.fStage);
  }
  load(trial, mode, { closeups = true } = {}) {
    this.trial = trial; this.mode = mode; this.state = {};
    const t = trial, W = t.rear.w, H = t.rear.h;
    this.root.dataset.mode = mode;
    // front
    const src = mode === "crop" ? t.front.crop : mode === "silhouette" ? t.front.silhouette : t.front.image;
    this.fStage.classList.toggle("is-crop", mode === "crop" || mode === "silhouette");
    this.fImg.alt = { full: "Front frame with the target boxed", crop: "Crop of the front target", silhouette: "Silhouette of the front target", original: "Original front frame" }[mode];
    this.fImg.onload = () => { this.layoutFront(); this.opts.onLoad?.("front"); };
    this.fImg.onerror = () => this.opts.onLoad?.("front");
    this.fImg.src = src;
    this.fSvg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    this.fSvg.replaceChildren();
    if (mode === "full") {
      const [x1, y1, x2, y2] = t.front.box;
      const g = s("g", { class: "cand target" });
      g.append(s("rect", { class: "halo", x: x1, y: y1, width: x2 - x1, height: y2 - y1 }), s("rect", { class: "box", x: x1, y: y1, width: x2 - x1, height: y2 - y1 }));
      const lab = s("g", { class: "lbl" }, s("rect", { rx: 3 }), s("text", { text: "T" }));
      g.append(lab); this.fSvg.append(g); this.fTarget = { g, lab, box: t.front.box };
    } else this.fTarget = null;
    this.frontCap.textContent = { full: "Target T is boxed", crop: "Target crop", silhouette: "Target silhouette, shape only", original: "Original frame" }[mode];
    // rear
    this.rImg.alt = `Rear frame with ${t.rear.candidates.length} labelled candidates`;
    this.rImg.onload = () => this.opts.onLoad?.("rear"); this.rImg.onerror = () => this.opts.onLoad?.("rear");
    this.rImg.src = t.rear.image;
    this.rSvg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    this.rSvg.replaceChildren();
    this.nodes = {};
    const order = [...t.rear.candidates].sort((a, b) => (b.box[2] - b.box[0]) * (b.box[3] - b.box[1]) - (a.box[2] - a.box[0]) * (a.box[3] - a.box[1]));
    const boxes = s("g"), labels = s("g");
    this.rSvg.append(boxes, labels);
    for (const c of order) {
      const [x1, y1, x2, y2] = c.box, bw = x2 - x1, bh = y2 - y1;
      const g = s("g", { class: "cand", "data-id": c.id });
      g.append(s("rect", { class: "halo", x: x1, y: y1, width: bw, height: bh }), s("rect", { class: "box", x: x1, y: y1, width: bw, height: bh }));
      const lead = s("line", { class: "lead" });
      const lab = s("g", { class: "lbl", "data-id": c.id }, lead, s("rect", { rx: 3 }), s("text", { text: c.id }));
      const hit = s("rect", { class: "hitbox" });
      g.append(hit);
      boxes.append(g); labels.append(lab);
      this.nodes[c.id] = { g, lab, lead, hit, c };
      if (this.opts.onPick) { g.addEventListener("click", () => this.opts.onPick(c.id)); lab.addEventListener("click", () => this.opts.onPick(c.id)); }
      for (const n of [g, lab]) { n.addEventListener("pointerenter", () => this.hot(c.id, true)); n.addEventListener("pointerleave", () => this.hot(c.id, false)); }
    }
    this.rearCap.textContent = this.opts.rearCaption ? this.opts.rearCaption(t) : `${t.rear.candidates.length} candidates`;
    // close-ups
    this.closeWrap.hidden = !closeups;
    this.close.replaceChildren();
    this.closeNodes = {};
    if (closeups) for (const c of t.rear.candidates) {
      const node = this.closeup(c, W, H);
      this.close.append(node); this.closeNodes[c.id] = node;
    }
    this.zoom("front", 1, true); this.zoom("rear", 1, true);
    requestAnimationFrame(() => { this.layoutLabels(); this.layoutFront(); });
  }
  closeup(c, W, H) {
    const [x1, y1, x2, y2] = c.box, bw = x2 - x1, bh = y2 - y1;
    const TH = matchMedia("(max-width: 640px)").matches ? 92 : 124;
    let ch = Math.max(bh * 1.5, bh + 16, 30), cw = Math.max(bw * 1.5, bw + 16, 30);
    let sc = TH / ch, tw = cw * sc;
    if (tw > 240) { tw = 240; cw = tw / sc; } if (tw < 76) { tw = 76; cw = tw / sc; }
    const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    let ox = Math.min(Math.max(0, cx - cw / 2), Math.max(0, W - cw)), oy = Math.min(Math.max(0, cy - ch / 2), Math.max(0, H - ch));
    const thumb = h("span", { class: "thumb" });
    Object.assign(thumb.style, { width: tw + "px", height: TH + "px", backgroundImage: `url("${this.trial.rear.image}")`, backgroundSize: `${W * sc}px ${H * sc}px`, backgroundPosition: `${-ox * sc}px ${-oy * sc}px` });
    const ring = h("span", { class: "ring" });
    Object.assign(ring.style, { left: (x1 - ox) * sc + "px", top: (y1 - oy) * sc + "px", width: bw * sc + "px", height: bh * sc + "px" });
    thumb.append(ring);
    const btn = h(this.opts.onPick ? "button" : "div", { class: "closeup", "data-id": c.id, type: this.opts.onPick ? "button" : null, role: this.opts.onPick ? "radio" : null, "aria-checked": this.opts.onPick ? "false" : null, "aria-label": `Candidate ${c.id}` },
      thumb, h("span", { class: "cl-label", text: c.id }));
    if (this.opts.onPick) btn.addEventListener("click", () => this.opts.onPick(c.id));
    btn.addEventListener("pointerenter", () => this.hot(c.id, true)); btn.addEventListener("pointerleave", () => this.hot(c.id, false));
    btn.addEventListener("focus", () => this.hot(c.id, true)); btn.addEventListener("blur", () => this.hot(c.id, false));
    return btn;
  }
  hot(id, on) {
    const n = this.nodes?.[id]; if (!n) return;
    n.g.classList.toggle("hot", on); n.lab.classList.toggle("hot", on);
    this.closeNodes?.[id]?.classList.toggle("hot", on);
    if (on) n.g.parentNode.append(n.g);
  }
  // Labels are sized in screen pixels and placed greedily to avoid covering other labels or boxes.
  layoutLabels() {
    if (!this.trial || !this.nodes) return;
    const r = this.rSvg.getBoundingClientRect(); if (!r.width) return;
    const W = this.trial.rear.w, H = this.trial.rear.h, k = r.width / W;
    const fs = BOX_PX.label / k, lh = BOX_PX.lh / k, g = BOX_PX.gap / k, minHit = 22 / k;
    const placed = [], boxes = Object.values(this.nodes).map(n => n.c.box);
    const items = Object.values(this.nodes).sort((a, b) => a.c.box[1] - b.c.box[1] || a.c.box[0] - b.c.box[0]);
    for (const n of items) {
      const [x1, y1, x2, y2] = n.c.box, lw = (n.c.id.length * 7.6 + 10) / k;
      const tries = [[x1, y1 - lh - g, 0], [x2 - lw, y1 - lh - g, 1], [x1, y2 + g, 2], [x2 - lw, y2 + g, 3], [x1 - lw - g, y1, 4], [x2 + g, y1, 4]];
      for (let st = 1; st <= 5; st++) tries.push([x1, y1 - lh - g - st * (lh + g), 5 + st], [x1, y2 + g + st * (lh + g), 5 + st]);
      let best = null;
      for (const [tx, ty, pen] of tries) {
        const lx = Math.min(Math.max(0, tx), W - lw), ly = Math.min(Math.max(0, ty), H - lh);
        const rect = [lx, ly, lx + lw, ly + lh];
        let score = pen * 0.4 + (Math.abs(lx - tx) + Math.abs(ly - ty)) * k * 0.05;
        for (const p of placed) score += overlap(rect, p) * k * k * 2;
        for (const b of boxes) if (b !== n.c.box) score += overlap(rect, b) * k * k * 0.25;
        if (overlap(rect, n.c.box) > 0 && pen < 4) score += overlap(rect, n.c.box) * k * k * 0.25;
        if (!best || score < best.score) best = { score, rect, pen };
      }
      const [lx, ly] = best.rect; placed.push(best.rect);
      const [rect, text] = [n.lab.querySelector("rect"), n.lab.querySelector("text")];
      rect.setAttribute("x", lx); rect.setAttribute("y", ly); rect.setAttribute("width", lw); rect.setAttribute("height", lh); rect.setAttribute("rx", 3 / k);
      text.setAttribute("x", lx + lw / 2); text.setAttribute("y", ly + lh * 0.72); text.setAttribute("font-size", fs); text.setAttribute("text-anchor", "middle");
      const far = best.pen >= 4;
      if (far) {
        const ax = Math.min(Math.max(lx + lw / 2, x1), x2), ay = ly + lh <= y1 ? y1 : ly >= y2 ? y2 : (y1 + y2) / 2;
        n.lead.setAttribute("x1", lx + lw / 2); n.lead.setAttribute("y1", ly + lh <= y1 ? ly + lh : ly);
        n.lead.setAttribute("x2", ax); n.lead.setAttribute("y2", ay);
      }
      n.lead.style.display = far ? "" : "none";
      const bw = x2 - x1, bh = y2 - y1, hw = Math.max(bw, minHit), hh = Math.max(bh, minHit);
      n.hit.setAttribute("x", (x1 + x2) / 2 - hw / 2); n.hit.setAttribute("y", (y1 + y2) / 2 - hh / 2); n.hit.setAttribute("width", hw); n.hit.setAttribute("height", hh);
    }
  }
  layoutFront() {
    if (this.fTarget) {
      const r = this.fSvg.getBoundingClientRect(); if (!r.width) return;
      const k = r.width / this.trial.rear.w, [x1, y1, x2, y2] = this.fTarget.box, lw = 22 / k, lh = BOX_PX.lh / k;
      const ly = y1 - lh - 2 / k < 0 ? y2 + 2 / k : y1 - lh - 2 / k, lx = Math.min(Math.max(0, x1), this.trial.rear.w - lw);
      const [rect, text] = [this.fTarget.lab.querySelector("rect"), this.fTarget.lab.querySelector("text")];
      rect.setAttribute("x", lx); rect.setAttribute("y", ly); rect.setAttribute("width", lw); rect.setAttribute("height", lh); rect.setAttribute("rx", 3 / k);
      text.setAttribute("x", lx + lw / 2); text.setAttribute("y", ly + lh * 0.72); text.setAttribute("font-size", BOX_PX.label / k); text.setAttribute("text-anchor", "middle");
    }
    if (this.fStage.classList.contains("is-crop") && this.fImg.naturalWidth) {
      // fill the panel, but never upscale a tiny crop beyond 7x
      this.fImg.style.maxWidth = Math.min(100 * 1, (this.fImg.naturalWidth * 7 / this.fStage.clientWidth) * 100) + "%";
      this.fImg.style.maxHeight = Math.min(100, (this.fImg.naturalHeight * 7 / this.fStage.clientHeight) * 100) + "%";
    } else { this.fImg.style.maxWidth = ""; this.fImg.style.maxHeight = ""; }
  }
  zoom(which, z, silent) {
    this.zooms[which] = z;
    const zoomer = which === "front" ? this.fZoom : this.rZoom, inner = zoomer.firstChild;
    zoomer.closest(".panel").querySelectorAll(".zoom-ctl button").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.zoom === z)));
    inner.style.width = z * 100 + "%";
    inner.style.height = which === "front" && (this.mode === "crop" || this.mode === "silhouette") ? z * 100 + "%" : "";
    zoomer.classList.toggle("zoomed", z > 1);
    if (silent) { zoomer.scrollLeft = 0; zoomer.scrollTop = 0; return; }
    requestAnimationFrame(() => {
      const t = this.trial; if (!t) return;
      let fx = 0.5, fy = 0.5;
      const b = which === "front" ? (this.mode === "full" || this.mode === "original" ? t.front.box : null) : (this.state.sel ? t.rear.candidates.find(c => c.id === this.state.sel)?.box : null);
      if (b) { fx = (b[0] + b[2]) / 2 / t.rear.w; fy = (b[1] + b[3]) / 2 / t.rear.h; }
      zoomer.scrollLeft = fx * inner.scrollWidth - zoomer.clientWidth / 2;
      zoomer.scrollTop = fy * inner.scrollHeight - zoomer.clientHeight / 2;
    });
  }
  // sel: selected id; answer/pick: reveal state
  setState({ sel = null, answer = null, pick = null } = {}) {
    this.state = { sel, answer, pick };
    for (const [id, n] of Object.entries(this.nodes || {})) {
      const isAns = answer && id === answer, isWrong = answer && pick && id === pick && pick !== answer;
      for (const el of [n.g, n.lab, this.closeNodes?.[id]].filter(Boolean)) {
        el.classList.toggle("sel", !answer && id === sel);
        el.classList.toggle("correct", !!isAns); el.classList.toggle("wrong", !!isWrong);
        el.classList.toggle("dim", !!answer && !isAns && !isWrong);
      }
      this.closeNodes?.[id]?.setAttribute?.("aria-checked", String(!answer && id === sel));
      if ((!answer && id === sel) || isAns || isWrong) { n.g.parentNode.append(n.g); n.lab.parentNode.append(n.lab); }
    }
  }
}

/* ------------------------------------------------------------ try the task */
function mulberry32(a) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function shuffle(arr, rnd) { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
const Try = {
  N: 20, state: null,
  init() {
    const seedEl = $("#seed");
    seedEl.value = String(100000 + Math.floor(Math.random() * 900000));
    $("#start").addEventListener("click", () => ready.then(() => this.start()));
    $("#quit").addEventListener("click", () => this.reset());
    $("#confirm").addEventListener("click", () => this.confirm());
    this.viewer = new Viewer($("#try-viewer"), {
      onPick: id => this.select(id),
      onLoad: () => { const st = this.state; if (st && ++st.loaded === 2) st.t0 = performance.now(); },
      rearCaption: () => "Which candidate is the same vehicle?",
      closeNote: "Enlarged from the rear frame. Study participants saw only the full frame.",
    });
    document.addEventListener("keydown", e => this.key(e));
    this.showBest();
  },
  sample(seed) {
    const rnd = mulberry32(seed);
    const bins = ["large", "medium", "small"], quota = [7, 7, 6];
    const rot = seed % 3; const q = bins.map((_, i) => quota[(i + rot) % 3]);
    const usedFront = new Set(), usedRear = new Set(), picked = [];
    bins.forEach((b, i) => {
      for (const t of shuffle(DATA.trials.filter(t => t.tags.rear_scale === b), rnd)) {
        if (picked.filter(p => p.tags.rear_scale === b).length >= q[i]) break;
        if (usedFront.has(t.front.image) || usedRear.has(t.rear.image)) continue;
        usedFront.add(t.front.image); usedRear.add(t.rear.image); picked.push(t);
      }
    });
    return shuffle(picked, rnd);
  },
  start() {
    const cond = $('input[name="cond"]:checked').value, mode = $('input[name="mode"]:checked').value, closeups = $("#opt-closeups").checked;
    let seed = parseInt($("#seed").value, 10);
    if (!Number.isFinite(seed) || seed < 0) { seed = 100000 + Math.floor(Math.random() * 900000); $("#seed").value = seed; }
    this.state = { cond, mode, seed, closeups, items: this.sample(seed).map(t => ({ trial: t, pick: null, ms: null })), idx: 0, sel: null, t0: 0, locked: false, done: false };
    $("#try-setup").hidden = true; $("#try-done").hidden = true; $("#try-run").hidden = false;
    $("#view-try").classList.add("running");
    this.render();
    $("#try-run").scrollIntoView({ block: "start" });
  },
  reset() {
    this.state = null;
    $("#view-try").classList.remove("running");
    $("#try-run").hidden = true; $("#try-done").hidden = true; $("#try-setup").hidden = false;
    this.showBest();
  },
  render() {
    const st = this.state, it = st.items[st.idx], t = it.trial;
    st.sel = null; st.locked = false; st.loaded = 0;
    $("#run-status").textContent = `Trial ${st.idx + 1} of ${st.items.length} · ${COND[st.cond]}`;
    $("#progress-bar").style.width = (100 * st.idx) / st.items.length + "%";
    st.t0 = performance.now();
    this.viewer.load(t, st.cond === "rgb_full" ? "full" : st.cond === "front_crop" ? "crop" : "silhouette", { closeups: st.closeups });
    this.viewer.setState({});
    const chips = $("#chips"); chips.replaceChildren();
    t.rear.candidates.forEach((c, i) => chips.append(h("button", { type: "button", class: "chip", role: "radio", "aria-checked": "false", "data-id": c.id, title: i < 9 ? `Key ${i + 1}` : null, text: c.id, onclick: () => this.select(c.id),
      onpointerenter: () => this.viewer.hot(c.id, true), onpointerleave: () => this.viewer.hot(c.id, false) })));
    $("#confirm").disabled = true; $("#confirm").textContent = st.idx === st.items.length - 1 && st.mode === "test" ? "Confirm and finish" : "Confirm";
    $("#feedback").hidden = true;
  },
  select(id) {
    const st = this.state; if (!st || st.locked) return;
    st.sel = id;
    $$("#chips .chip").forEach(c => c.setAttribute("aria-checked", String(c.dataset.id === id)));
    this.viewer.setState({ sel: id });
    $("#confirm").disabled = false;
  },
  confirm() {
    const st = this.state; if (!st || !st.sel || st.locked) return;
    const it = st.items[st.idx];
    it.pick = st.sel; it.ms = Math.round(performance.now() - st.t0); it.correct = it.pick === it.trial.answer;
    if (st.mode === "practice") { st.locked = true; this.reveal(it); } else this.next();
  },
  reveal(it) {
    const t = it.trial;
    this.viewer.setState({ answer: t.answer, pick: it.pick });
    $$("#chips .chip").forEach(c => { c.classList.toggle("correct", c.dataset.id === t.answer); c.classList.toggle("wrong", c.dataset.id === it.pick && !it.correct); });
    $("#confirm").disabled = true;
    const last = this.state.idx === this.state.items.length - 1;
    const fb = $("#feedback");
    fb.replaceChildren(...[
      h("span", { class: "verdict " + (it.correct ? "ok" : "no"), text: it.correct ? "Correct" : `Not quite: it was ${t.answer}` }),
      h("span", { class: "hint", text: `${(it.ms / 1000).toFixed(1)} s` }),
      t.tags.human_missed_both ? h("span", { class: "pill warn", text: "Both human judges missed this pair" }) : null,
      h("button", { class: "btn primary small", type: "button", text: last ? "See results" : "Next trial", onclick: () => this.next() }),
      pickPills(t, this.state.cond)].filter(Boolean));
    fb.hidden = false;
    fb.querySelector(".btn").focus({ preventScroll: true });
  },
  next() {
    const st = this.state;
    if (st.idx < st.items.length - 1) { st.idx++; this.render(); }
    else this.finish();
  },
  key(e) {
    if (current !== "try" || !this.state || this.state.done || $("#try-run").hidden) return;
    if (e.target.matches("input,select,textarea")) return;
    const t = this.state.items[this.state.idx].trial;
    if (/^[1-9]$/.test(e.key) && !this.state.locked) { const c = t.rear.candidates[+e.key - 1]; if (c) { this.select(c.id); e.preventDefault(); } }
    else if (e.key === "Enter") { e.preventDefault(); this.state.locked ? this.next() : this.confirm(); }
    else if (e.key.toLowerCase() === "z") { const z = this.viewer.zooms.rear; this.viewer.zoom("rear", z >= 3 ? 1 : z + 1); }
  },
  finish() {
    const st = this.state; st.done = true;
    $("#progress-bar").style.width = "100%";
    const n = st.items.length, k = st.items.filter(i => i.correct).length, acc = (100 * k) / n;
    const best = JSON.parse(store.get("f2b-best") || "{}");
    if (!best[st.cond] || acc > best[st.cond].acc) { best[st.cond] = { acc, seed: st.seed, at: new Date().toISOString().slice(0, 10) }; store.set("f2b-best", JSON.stringify(best)); }
    $("#try-run").hidden = true; $("#try-done").hidden = false;
    $("#view-try").classList.remove("running");
    this.renderDone();
    window.scrollTo(0, $("#view-try").offsetTop);
  },
  comparisons() {
    const st = this.state, cond = st.cond, ids = st.items.map(i => i.trial.id), R = DATA.results;
    const rows = [];
    for (const eff of ["none", "medium"]) for (const [key, cells] of Object.entries(R.table[eff])) {
      if (!cells[cond]) continue;
      const run = `${key}:${cond}:${eff}`;
      const pr = DATA.picks?.runs?.[run]?.picks;
      let mine = null;
      if (pr && ids.every(id => pr[id] != null)) mine = ids.filter(id => (typeof pr[id] === "string" ? pr[id] : pr[id].c) === DATA.byId.get(id).answer).length;
      rows.push({ label: modelLabel(key) + (eff === "medium" ? " · reasoning" : ""), overall: cells[cond].acc, mine, kind: R.baselines.some(b => b.key === key) ? "baseline" : "vlm" });
    }
    return rows;
  },
  renderDone() {
    const st = this.state, box = $("#try-done"), cond = st.cond, R = DATA.results;
    const n = st.items.length, k = st.items.filter(i => i.correct).length, acc = (100 * k) / n;
    const times = st.items.map(i => i.ms).sort((a, b) => a - b), med = (times[(n - 1) >> 1] + times[n >> 1]) / 2000;
    const human = R.human.accuracy[cond];
    const parts = R.human.participant_scores.map(p => p[cond]).filter(v => v != null);
    const beat = parts.filter(v => v < acc).length, tie = parts.filter(v => v === acc).length;
    const comps = this.comparisons();
    const haveMine = comps.some(c => c.mine != null);
    const bestModel = [...comps].sort((a, b) => b.overall - a.overall)[0];
    let line;
    if (human) line = acc >= human.acc ? `You matched or beat the pooled human score of ${fmt1(human.acc)}%.` : `People averaged ${fmt1(human.acc)}% in this condition.`;
    else line = "No human baseline exists for silhouettes. Only models were tested.";
    const lat = R.human.latency_s[cond];
    const left = h("div", { class: "card score-hero" },
      h("span", { class: "eyebrow", text: `Your result · ${COND[cond]} · set ${st.seed}${st.closeups ? " · with close-ups" : ""}` }),
      h("span", { class: "big", text: `${k}/${n}` }),
      h("span", { class: "verdict-line", text: `${fmt1(acc)}% Rank-1. ${line}` }),
      h("dl", { class: "kv" },
        h("dt", { text: "Your median decision time" }), h("dd", { text: `${med.toFixed(1)} s` }),
        lat ? h("dt", { text: "Human median in this condition" }) : null, lat ? h("dd", { text: `${lat.median.toFixed(1)} s` }) : null,
        parts.length ? h("dt", { text: "Participants you beat (of 25)" }) : null, parts.length ? h("dd", { text: `${beat}${tie ? ` + ${tie} tied` : ""}` }) : null,
        h("dt", { text: `Best model, ${COND[cond]}` }), h("dd", { text: `${bestModel.label} ${fmt1(bestModel.overall)}%` }),
        h("dt", { text: "Chance on your set" }), h("dd", { text: fmt1(st.items.reduce((a, i) => a + 100 / i.trial.rear.candidates.length, 0) / n) + "%" })),
      h("div", { class: "done-actions" },
        h("button", { class: "btn primary", type: "button", text: "New set", onclick: () => { $("#seed").value = String(100000 + Math.floor(Math.random() * 900000)); this.start(); } }),
        h("button", { class: "btn", type: "button", text: "Retry this set", onclick: () => { $("#seed").value = st.seed; this.start(); } }),
        h("button", { class: "btn", type: "button", text: "Change settings", onclick: () => this.reset() }),
        h("button", { class: "btn ghost", type: "button", text: "Download results", onclick: () => this.download() })));
    const chartCard = h("div", { class: "card" },
      h("h3", { class: "card-title", text: "You vs. the paper" }),
      h("p", { class: "card-sub", text: haveMine ? "Accuracy on your 20 pairs, from each model’s recorded answers (overall 500-pair accuracy in the tooltip)" : "Your score against overall 500-pair Rank-1 accuracy" }),
      h("div", { class: "chart", id: "you-chart" }));
    const grid = h("div", { class: "done-grid" }, left, chartCard);
    // breakdown
    const by = (f, cats) => cats.map(([key, label]) => { const its = st.items.filter(i => f(i.trial) === key); return { label, n: its.length, k: its.filter(i => i.correct).length }; }).filter(r => r.n);
    const bd = h("div", { class: "card" }, h("h3", { class: "card-title", text: "Where you slipped" }), h("p", { class: "card-sub", text: "Your accuracy by stratum on this set" }));
    const tb = h("table", { class: "mini" }, h("thead", {}, h("tr", {}, h("th", { text: "Stratum" }), h("th", { text: "Bin" }), h("th", { text: "Correct" }))));
    const tbody = h("tbody");
    const add = (title, rows) => rows.forEach((r, i) => tbody.append(h("tr", {}, h("td", { text: i ? "" : title }), h("td", { text: r.label }), h("td", { text: `${r.k}/${r.n}` }))));
    add("Rear-target size", by(t => t.tags.rear_scale, [["large", "Large"], ["medium", "Medium"], ["small", "Small"]]));
    add("Gallery size K", by(t => (t.tags.k <= 3 ? "3" : t.tags.k <= 5 ? "4-5" : "6+"), [["3", "3"], ["4-5", "4–5"], ["6+", "6+"]]));
    add("Road", by(t => t.tags.road, [["highway", "Highway"], ["urban", "Urban"], ["suburban", "Suburban"], ["construction_zone", "Construction"]]));
    tb.append(tbody); bd.append(tb);
    const hard = st.items.filter(i => i.trial.tags.human_missed_both);
    if (hard.length) bd.append(h("p", { class: "note-box", text: `${hard.length} of your pairs ${hard.length > 1 ? "were" : "was"} missed by both human judges in the study. You got ${hard.filter(i => i.correct).length} right.` }));
    if (!DATA.picks) bd.append(h("p", { class: "hint", style: "margin-top:12px", text: "Per-pair model answers aren’t published yet, so comparisons use each model’s overall accuracy." }));
    // review
    const rv = h("div", { class: "card" }, h("h3", { class: "card-title", text: "Review your answers" }), h("p", { class: "card-sub", text: "Click a pair to open it in the explorer with the match revealed" }));
    const grid2 = h("div", { class: "review" });
    st.items.forEach((it, i) => {
      const card = h("button", { type: "button", class: "review-item", onclick: () => { location.hash = `explore/${it.trial.id}`; Explore.revealNext = true; } },
        h("img", { src: it.trial.front[cond === "rgb_full" ? "image" : cond === "front_crop" ? "crop" : "silhouette"], alt: "", loading: "lazy", style: cond === "rgb_full" ? "" : "object-fit:contain;background:var(--surface-2)" }),
        h("div", {}, h("span", { text: `${i + 1}. ${it.trial.id}` }), h("span", { class: it.correct ? "res-ok" : "res-no", text: it.correct ? `✓ ${it.pick}` : `✗ ${it.pick} → ${it.trial.answer}` })));
      grid2.append(card);
    });
    rv.append(grid2);
    box.replaceChildren(grid, h("div", { class: "two-col" }, bd, h("div", { class: "card prose" }, h("h3", { text: "About the comparison" }),
      h("p", { text: "Human participants did 20 full-RGB and 20 crop trials each, balanced across difficulty, scene and source video. Your set is balanced across rear-target size, so a single 20-trial score moves in steps of 5 points and carries roughly ±10 points of noise." }),
      h("p", { text: "Models answered all 500 pairs with the same rear galleries. They saw the same aliases, but not the clickable overlay." }))), rv);
    this.drawYou(acc, comps, human, haveMine);
  },
  drawYou(acc, comps, human, haveMine) {
    const box = $("#you-chart");
    const rows = [{ label: "You", v: acc, you: true }];
    const tagO = l => (haveMine ? l + " (overall)" : l);
    if (human) rows.push({ label: tagO("Humans, this condition"), v: human.acc, human: true });
    for (const c of comps) rows.push({ label: haveMine && c.mine == null ? tagO(c.label) : c.label, v: haveMine && c.mine != null ? (100 * c.mine) / this.state.items.length : c.overall, overall: c.overall, mine: c.mine });
    rows.sort((a, b) => b.v - a.v || (a.you ? -1 : 1));
    const W = Math.max(300, box.clientWidth || 520), L = Math.min(190, W * 0.42), R = 44, rowH = 22, bar = 14, T = 4, Hh = T + rows.length * rowH + 24;
    const svg = svgBox(box, W, Hh);
    svg.setAttribute("aria-label", "Bar chart comparing your accuracy with humans and models");
    const x = v => L + (v / 100) * (W - L - R);
    axisX(svg, x, [0, 25, 50, 75, 100], T, T + rows.length * rowH, v => v + "%");
    rows.forEach((r, i) => {
      const y = T + i * rowH + (rowH - bar) / 2, w = Math.max(1, x(r.v) - x(0)), rr = Math.min(4, w);
      const col = r.you ? css("--accent") : r.human ? css("--human") : css("--axis");
      svg.append(s("text", { x: L - 8, y: y + bar - 3, "text-anchor": "end", class: r.you || r.human ? "strong" : "", "font-size": 11.5, text: r.label }));
      svg.append(s("path", { d: `M${x(0)},${y}h${w - rr}a${rr},${rr} 0 0 1 ${rr},${rr}v${bar - 2 * rr}a${rr},${rr} 0 0 1 -${rr},${rr}h-${w - rr}z`, fill: col }));
      svg.append(s("text", { x: x(r.v) + 5, y: y + bar - 3, "font-size": 11, class: r.you ? "strong" : "", text: fmt1(r.v) }));
      const hit = s("rect", { class: "hit", x: 0, y: y - 3, width: W, height: rowH });
      svg.append(hit);
      hover(hit, e => showTip(e, r.label, [{ value: fmt1(r.v) + "%", label: r.you ? "your 20 trials" : r.mine != null ? `${r.mine}/20 on your pairs` : "overall, 500 pairs" },
        ...(r.overall != null && r.mine != null ? [{ value: fmt1(r.overall) + "%", label: "overall, 500 pairs" }] : [])]));
    });
  },
  download() {
    const st = this.state;
    const out = { benchmark: "Front2Back-ReID", condition: st.cond, mode: st.mode, seed: st.seed, closeups: st.closeups, date: new Date().toISOString(),
      correct: st.items.filter(i => i.correct).length, trials: st.items.map(i => ({ pair_id: i.trial.id, candidate_id: i.pick, correct_candidate_id: i.trial.answer, correct: i.correct, response_ms: i.ms })) };
    const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], { type: "application/json" })), download: `front2back-try-${st.cond}-${st.seed}.json` });
    document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  },
  showBest() {
    const best = JSON.parse(store.get("f2b-best") || "{}");
    const parts = Object.entries(best).map(([c, b]) => `${COND[c]} ${fmt1(b.acc)}%`);
    $("#best-score").textContent = parts.length ? `Your best on this device: ${parts.join(" · ")}` : "";
  },
};

/* ------------------------------------------------------------ explore */
const Explore = {
  list: [], i: 0, view: "full", revealed: false, revealNext: false, inited: false,
  init() {
    if (this.inited) return; this.inited = true;
    this.viewer = new Viewer($("#ex-viewer"), { rearCaption: t => (this.revealed ? `Match: ${t.answer}` : `${t.rear.candidates.length} candidates`) });
    ["#f-road", "#f-scale", "#f-k", "#f-hard"].forEach(s2 => $(s2).addEventListener("change", () => this.filter()));
    $("#ex-prev").addEventListener("click", () => this.go(this.i - 1));
    $("#ex-next").addEventListener("click", () => this.go(this.i + 1));
    $("#ex-pick").addEventListener("change", e => this.go(this.list.findIndex(t => t.id === e.target.value)));
    $$("#ex-view button").forEach(b => b.addEventListener("click", () => { this.view = b.dataset.v; $$("#ex-view button").forEach(x => x.setAttribute("aria-pressed", String(x === b))); this.show(); }));
    $("#ex-reveal").addEventListener("click", () => { this.revealed = !this.revealed; this.show(); });
    document.addEventListener("keydown", e => {
      if (current !== "explore" || e.target.matches("input,select,textarea")) return;
      if (e.key === "ArrowRight") this.go(this.i + 1); else if (e.key === "ArrowLeft") this.go(this.i - 1); else if (e.key.toLowerCase() === "r") { this.revealed = !this.revealed; this.show(); }
    });
    this.filter(true);
  },
  open(arg) {
    this.init();
    if (arg === "hard") { $("#f-hard").checked = true; ["#f-road", "#f-scale", "#f-k"].forEach(x => ($(x).value = "")); this.filter(true); }
    else if (arg && DATA.byId.has(arg)) {
      let idx = this.list.findIndex(t => t.id === arg);
      if (idx < 0) { ["#f-road", "#f-scale", "#f-k"].forEach(x => ($(x).value = "")); $("#f-hard").checked = false; this.filter(true); idx = this.list.findIndex(t => t.id === arg); }
      this.revealed = this.revealNext; this.revealNext = false;
      this.i = idx; this.show();
    } else this.show();
  },
  filter(keep) {
    const road = $("#f-road").value, sc = $("#f-scale").value, k = $("#f-k").value, hard = $("#f-hard").checked;
    const cur = this.list[this.i]?.id;
    this.list = DATA.trials.filter(t => (!road || t.tags.road === road) && (!sc || t.tags.rear_scale === sc) && (!hard || t.tags.human_missed_both)
      && (!k || (k === "3" ? t.tags.k <= 3 : k === "4-5" ? t.tags.k >= 4 && t.tags.k <= 5 : t.tags.k >= 6)));
    $("#f-count").textContent = `${this.list.length} of ${DATA.trials.length} pairs`;
    const sel = $("#ex-pick"); sel.replaceChildren(...this.list.map(t => h("option", { value: t.id, text: t.id })));
    this.i = Math.max(0, keep && cur ? this.list.findIndex(t => t.id === cur) : 0);
    if (this.i < 0) this.i = 0;
    this.revealed = false;
    this.show();
  },
  go(i) { if (i < 0 || i >= this.list.length) return; this.i = i; this.revealed = false; this.show(); if (location.hash !== "#explore/" + this.list[i].id) history.replaceState(null, "", "#explore/" + this.list[i].id); },
  show() {
    const t = this.list[this.i];
    const empty = !t;
    $("#ex-viewer").hidden = empty;
    if (empty) { $("#ex-meta").replaceChildren(h("span", { class: "hint", text: "No pairs match these filters." })); $("#ex-picks").replaceChildren(); return; }
    $("#ex-pick").value = t.id;
    $("#ex-prev").disabled = this.i === 0; $("#ex-next").disabled = this.i === this.list.length - 1;
    const sameTrial = this.viewer.trial === t && this.viewer.mode === this.view;
    if (!sameTrial) this.viewer.load(t, this.view);
    this.viewer.rearCap.textContent = this.revealed ? `Match: ${t.answer}` : `${t.rear.candidates.length} candidates`;
    this.viewer.setState(this.revealed ? { answer: t.answer } : {});
    $("#ex-reveal").setAttribute("aria-pressed", String(this.revealed)); $("#ex-reveal").textContent = this.revealed ? "Hide match" : "Reveal match";
    const tg = t.tags, cap = v => ({ dawn_dusk: "Dawn/dusk", sun_glare: "Sun glare", construction_zone: "Construction" })[v] || v.charAt(0).toUpperCase() + v.slice(1);
    const pill = (k, v, cls) => h("span", { class: "pill " + (cls || "") }, k + " ", h("b", { text: v }));
    $("#ex-meta").replaceChildren(...[
      pill("Pair", t.id), pill("Road", cap(tg.road)), pill("Weather", cap(tg.weather)), pill("Time", cap(tg.time)),
      pill("Gallery K", tg.k), pill("Vehicles Vᵢ", tg.vi), pill("Rear target", tg.rear_scale), pill("Front target", tg.front_scale),
      pill("Front occlusion", tg.front_occ), pill("Rear occlusion", tg.rear_occ), tg.depth_m != null ? pill("Front range ≈", tg.depth_m + " m") : null,
      tg.human_missed_both ? h("span", { class: "pill warn", text: "Missed by both human judges" }) : null].filter(Boolean));
    const pp = this.revealed ? pickPills(t, this.view === "crop" ? "front_crop" : this.view === "silhouette" ? "front_mask" : "rgb_full") : null;
    $("#ex-picks").replaceChildren(...(pp ? [pp] : []));
  },
};

/* ------------------------------------------------------------ dataset tab */
function initDataset() {
  const c = DATA.config;
  if (c.dataset_url) $$(".dataset-link").forEach(a => { a.href = c.dataset_url; a.setAttribute("download", ""); });
  $("#copy-bib")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("#bibtex").textContent); $("#copy-status").textContent = "Copied."; }
    catch { const r = document.createRange(); r.selectNodeContents($("#bibtex")); getSelection().removeAllRanges(); getSelection().addRange(r); $("#copy-status").textContent = "Selected. Press Ctrl+C to copy."; }
  });
}

/* ------------------------------------------------------------ lightbox for paper figures */
function initLightbox() {
  const lb = $("#lightbox"), img = $("img", lb), cap = $(".lb-cap", lb);
  let last = null;
  const close = () => { lb.hidden = true; img.removeAttribute("src"); document.body.classList.remove("no-scroll"); last?.focus(); };
  for (const fig of $$("figure.teaser, figure.wide, figure.case")) {
    const im = $("img", fig); if (!im) continue;
    im.classList.add("zoomable"); im.tabIndex = 0; im.setAttribute("role", "button"); im.setAttribute("aria-label", "Enlarge figure: " + (im.alt || "").slice(0, 80));
    const open = () => { last = im; img.src = im.currentSrc || im.src; img.alt = im.alt; cap.textContent = $("figcaption", fig)?.textContent || ""; lb.hidden = false; document.body.classList.add("no-scroll"); $(".lb-close", lb).focus(); };
    im.addEventListener("click", open);
    im.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  }
  lb.addEventListener("click", e => { if (e.target !== img) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !lb.hidden) close(); });
}

/* ------------------------------------------------------------ boot */
Try.init();
initLightbox();
route();
ready.then(() => { initDataset(); if (current === "overview") drawResults(); })
  .catch(err => {
    console.error(err);
    const msg = h("p", { class: "note-box", text: "Couldn’t load the benchmark data. If you opened this file directly, serve the folder over HTTP instead (python -m http.server)." });
    $("#try-setup .setup").append(msg);
  });
})();
