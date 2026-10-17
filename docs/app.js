/* Score Oracle front end: 4 views (today, stars, results, all matches). */
const REPO = "itzik200592-byte/score-oracle";
const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const LG_ORDER = ["IL", "CL", "EL", "PL", "LL", "SA", "L1"];
let DATA = null;
let view = safe(() => localStorage.getItem("view")) || "today";
let chip = { stars: "all", all: "all" };
document.getElementById("run").href = `https://github.com/${REPO}/actions/workflows/oracle.yml`;

function safe(f) { try { return f(); } catch (_) { return null; } }
const toast = t => { const e = document.getElementById("toast"); e.textContent = t; e.classList.add("show"); setTimeout(() => e.classList.remove("show"), 3200); };
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const todayIL = () => new Date().toLocaleDateString("sv", { timeZone: "Asia/Jerusalem" });
const fmtDate = iso => { const d = new Date(iso + "T12:00:00"); return `יום ${DAYS[d.getDay()]}, ${d.getDate()}.${d.getMonth() + 1}`; };
const dayLabel = iso => { const t = todayIL(); const dt = new Date(t + "T12:00:00"); const nx = new Date(dt.getTime() + 864e5).toLocaleDateString("sv"); const pv = new Date(dt.getTime() - 864e5).toLocaleDateString("sv");
  return iso === t ? `היום, ${fmtDate(iso)}` : (iso === nx ? `מחר, ${fmtDate(iso)}` : (iso === pv ? `אתמול, ${fmtDate(iso)}` : fmtDate(iso))); };
const ago = iso => { const m = Math.round((Date.now() - new Date(iso)) / 60000); if (m < 60) return `לפני ${Math.max(m, 0)} דק'`; const h = Math.round(m / 60); if (h < 48) return `לפני ${h} שעות`; return `לפני ${Math.round(h / 24)} ימים`; };
const ko = p => (p.odds && p.odds.kickoff) || "";
const mx = p => Math.max(p.pH, p.pD, p.pA);
const dirOf = p => { const m = mx(p); return m === p.pH ? "h" : (m === p.pA ? "a" : "d"); };
const starSvg = `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4 6.1 20.5l1.2-6.5L2.5 9.4l6.6-.9z"/></svg>`;

async function load() {
  const btn = document.getElementById("reload"); btn.setAttribute("aria-busy", "true");
  try {
    const r = await fetch(`data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    DATA = await r.json();
    render();
  } catch (e) {
    document.getElementById("view").innerHTML = `<div class="empty">לא הצלחתי לטעון נתונים.<br><small>${esc(e.message)}</small></div>`;
  } finally { btn.removeAttribute("aria-busy"); }
}

function upcomingDays() { return [...new Set(DATA.predictions.map(p => p.date))].filter(d => d >= todayIL()).sort(); }

function render() {
  const g = new Date(DATA.generated_at);
  document.getElementById("updated").textContent = `עודכן ${ago(DATA.generated_at)} · ${g.toLocaleString("he-IL", { timeZone: "Asia/Jerusalem", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}`;
  const days = upcomingDays();
  const nToday = DATA.predictions.filter(p => p.date === (days[0] || todayIL())).length;
  const nStars = DATA.predictions.filter(p => p.odds && p.odds.star && p.date >= todayIL()).length;
  const nRes = (DATA.track && DATA.track.overall && DATA.track.overall.n) || 0;
  const tabs = [["today", days[0] === todayIL() ? "היום" : "הקרובים", nToday], ["stars", "כוכבים", nStars], ["results", "תוצאות", nRes], ["all", "הכול", DATA.predictions.length]];
  document.getElementById("mainTabs").innerHTML = tabs.map(([k, t, n]) => `<button class="mtab" role="tab" data-k="${k}" aria-selected="${k === view}">${t}<span class="cnt num">${n}</span></button>`).join("");
  document.querySelectorAll(".mtab").forEach(b => b.onclick = () => { view = b.dataset.k; safe(() => localStorage.setItem("view", view)); render(); window.scrollTo({ top: 0 }); });
  const st = DATA.stale || [];
  const warn = document.getElementById("warn") || Object.assign(document.createElement("div"), { id: "warn" });
  warn.className = "lead"; warn.style.borderColor = "rgba(255,138,128,.5)";
  if (st.length) { warn.innerHTML = `<b>אזהרת נתונים:</b> חסרות תוצאות ל${st.map(x => `${esc(DATA.leagues[x.league])} (${x.missing} משחקים מאז ${x.oldest.slice(5).replace("-", ".")})`).join(", ")}. מקור התוצאות כנראה נשבר, והחיזויים לליגה הזאת מתבססים על נתונים ישנים.`; document.getElementById("main").prepend(warn); }
  else if (warn.parentNode) warn.remove();
  const chips = document.getElementById("chips");
  chips.hidden = true;
  const v = document.getElementById("view");
  if (view === "today") v.innerHTML = viewToday();
  else if (view === "stars") v.innerHTML = viewStars(chips);
  else if (view === "results") v.innerHTML = viewResults();
  else v.innerHTML = viewAll(chips);
  const lr = DATA.last_result || {};
  document.getElementById("foot").innerHTML = `תוצאה אחרונה במאגר: ${Object.keys(lr).filter(k => lr[k]).map(k => `${esc(DATA.leagues[k])} <span class="num">${lr[k].slice(5).replace("-", ".")}</span>`).join(" · ")}<br>המודל הסטטיסטי מבוסס על תוצאות קבוצות בלבד. שמות שחקנים מופיעים רק בחוות דעת הסוכן ומאומתים מול הסגל הנוכחי ב-ESPN.`;
}

/* ---------- compact card ---------- */
function card(p, i = 0, showDate = false) {
  const o = p.odds, st = o && o.star, d = dirOf(p), m = mx(p);
  const fav = d === "h" ? "h" : (d === "a" ? "a" : null);
  const chipP = v => `<span class="wp num">${v}%</span>`;
  const dirName = d === "h" ? p.home : (d === "a" ? p.away : "תיקו");
  const sorted = [p.pH, p.pD, p.pA].sort((x, y) => y - x), close = sorted[0] - sorted[1] < 6;
  const oddsMini = o ? `<div class="oddsmini" aria-label="יחסי Winner">${[["h", "בית"], ["d", "תיקו"], ["a", "חוץ"]].map(([k, t]) => `<div class="${st && st.outcome === k ? "pk" : ""}">${t}<b class="num">${o[k].toFixed(2)}</b></div>`).join("")}</div>` : "";
  const starB = st ? `<span class="star">${starSvg}כוכב: ${esc(st.outcome === "h" ? p.home : (st.outcome === "a" ? p.away : "תיקו"))} ${st.odds.toFixed(2)}</span>` : "";
  const vb = p.opinion ? (p.opinion.verified === "ok" ? `<span class="tag ok" style="font-size:11px">שחקנים אומתו מול הסגל הנוכחי</span>` : (p.opinion.verified === "problems" ? `<span class="tag no" style="font-size:11px">אזהרה: שחקן שאינו בסגל (${esc((p.opinion.unknown_players || []).join(", "))})</span>` : `<span class="tag" style="font-size:11px;color:var(--ink-faint)">סגלים לא אומתו</span>`)) : "";
  const op = p.opinion ? `<div class="opnote">דעת האנליסט: נוטה ל${p.opinion.lean === "h" ? "בית" : (p.opinion.lean === "a" ? "חוץ" : "תיקו")} (ביטחון ${esc(p.opinion.confidence || "")}) ${vb}</div>` : "";
  return `<article class="card ${st ? "S" : ""}" style="animation-delay:${Math.min(i, 8) * 35}ms">
    <div class="ch">${ko(p) ? `<span class="t num">${ko(p)}</span>` : ""}${showDate ? `<span>${fmtDate(p.date)}</span>` : ""}<span class="lg">${esc(DATA.leagues[p.league])}</span>${starB}</div>
    <div class="row">
      <div class="teams">
        <div class="team ${fav === "h" ? "fav" : ""}">${esc(p.home)}${fav === "h" ? chipP(p.pH) : ""}</div>
        <div class="team ${fav === "a" ? "fav" : ""}">${esc(p.away)}${fav === "a" ? chipP(p.pA) : ""}</div>
      </div>
      <div class="pickbox"><small>תוצאה</small><b class="num">${p.pick}</b><span class="conf ${p.tier}" title="ביטחון בתוצאה המדויקת: A גבוה, C נמוך">ביטחון ${p.tier}</span></div>
    </div>
    <div class="dirline ${d}"><span>מי תנצח: <b>${esc(dirName)}</b>${close ? " · משחק צמוד" : ""}</span><span class="n num">${m}%</span></div>
    ${oddsMini}${op}
    <button class="vbtn" data-v="${p.date}|${p.home}|${p.away}" aria-label="פסק דין מלא: ${esc(p.home)} נגד ${esc(p.away)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/></svg>פסק דין מלא: שערים, מעל/מתחת, חדשות</button>
  </article>`;
}

const byTime = (a, b) => a.date.localeCompare(b.date) || (ko(a) || "99:99").localeCompare(ko(b) || "99:99") || a.league.localeCompare(b.league);

/* ---------- view: today ---------- */
function viewToday() {
  const days = upcomingDays().slice(0, 2);
  if (!days.length) return `<div class="empty">אין משחקים קרובים בנתונים.</div>`;
  let html = "", i = 0;
  const first = DATA.predictions.filter(p => p.date === days[0]);
  const sn = first.filter(p => p.tier === "A").length, ns = first.filter(p => p.odds && p.odds.star).length;
  html += `<div class="lead"><b>${dayLabel(days[0])}</b>: ${first.length} משחקים${ns ? `, <b>${ns} כוכבים</b> (ראה לשונית כוכבים)` : ""}. לחיצה על "פסק דין" בכל משחק פותחת ניתוח מלא.</div>`;
  for (const d of days) {
    html += `<div class="day">${dayLabel(d)}</div>`;
    for (const p of DATA.predictions.filter(x => x.date === d).sort(byTime)) html += card(p, i++);
  }
  return html;
}

/* ---------- view: stars ---------- */
function viewStars(chips) {
  chips.hidden = false;
  const all = DATA.predictions.filter(p => p.odds && p.odds.star && p.date >= todayIL());
  const opts = [["all", "הכול"], ["today", "היום"], ["value", "יתרון מול השוק"]];
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.stars === k}">${t}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.stars = b.dataset.c; render(); });
  let rows = all;
  if (chip.stars === "today") rows = all.filter(p => p.date === (upcomingDays()[0] || todayIL()));
  if (chip.stars === "value") rows = all.filter(p => p.odds.star.value);
  rows = [...rows].sort((a, b) => b.odds.star.model_p - a.odds.star.model_p || a.date.localeCompare(b.date));
  const rec = DATA.track && DATA.track.overall && DATA.track.overall.stars;
  let html = `<div class="lead"><b>כוכב</b> = קבוצה שצפויה לנצח ביחס של 1.5 ומעלה, והמודל נותן לה לפחות 50%. הרשימה <b>מדורגת מהסיכוי הגבוה ביותר</b> לפגוע בקבוצה המנצחת (לא בתוצאה המדויקת).${rec && rec.n ? `<br>עד עכשיו: <b>${rec.won} מתוך ${rec.n}</b> כוכבים פגעו${rec.breakeven ? ` (כדי לאזן ביחס ממוצע ${rec.avg_odds} צריך לפגוע ב-${rec.breakeven}%)` : ""}. מדגם קטן מאוד.` : ""}</div>`;
  if (!rows.length) return html + `<div class="empty">אין כרגע כוכבים בקטגוריה הזאת.</div>`;
  rows.forEach((p, i) => {
    const s = p.odds.star, nm = s.outcome === "h" ? p.home : (s.outcome === "a" ? p.away : "תיקו");
    html += `<article class="card S starcard" style="animation-delay:${Math.min(i, 8) * 35}ms">
      <div class="rank num">${i + 1}</div>
      <div>
        <div style="font-weight:800;font-size:15.5px">${s.outcome === "d" ? "תיקו" : "ניצחון " + esc(nm)}</div>
        <div class="sline">${esc(p.home)} - ${esc(p.away)}</div>
        <div class="sline">${fmtDate(p.date)}${ko(p) ? ` · <span class="num">${ko(p)}</span>` : ""} · ${esc(DATA.leagues[p.league])}</div>
        <div class="sline">יחס Winner <b class="num">${s.odds.toFixed(2)}</b> · שוק <b class="num">${s.market_p}%</b> · ${s.value ? `<span class="val">המודל גבוה מהשוק</span>` : `<span class="noval">המודל כמו השוק</span>`}</div>
      </div>
      <div class="bigp"><b class="num">${s.model_p}%</b><small>סיכוי לפגוע</small></div>
      <button class="vbtn" style="grid-column:1/-1;margin-top:2px" data-v="${p.date}|${p.home}|${p.away}">פסק דין מלא</button>
    </article>`;
  });
  return html;
}

/* ---------- view: results (track record) ---------- */
function tags(r) {
  const T = (ok, t) => `<span class="tag ${ok ? "ok" : "no"}">${ok ? "✓" : "✗"} ${t}</span>`;
  const nm = { h: "בית", d: "תיקו", a: "חוץ" };
  let h = T(r.dir_ok, `כיוון: ${nm[r.pred_dir]} ${r.conf}%`) + T(r.exact, "תוצאה מדויקת") + (r.over_p != null ? T(r.over_ok, `${r.over_p > 50 ? "מעל" : "מתחת"} 2.5`) : "") + T(r.btts_ok, "שתיהן מבקיעות");
  if (r.star) h += `<span class="tag ${r.star_ok ? "ok" : "no"}">★ ${r.star_ok ? "כוכב פגע" : "כוכב לא פגע"}${r.star_odds ? ` (${r.star_odds.toFixed(2)})` : ""}</span>`;
  return h;
}
function viewResults() {
  const t = DATA.track;
  if (!t || !t.overall || !t.overall.n) return `<div class="lead">עדיין אין משחקים שהסתיימו אחרי שנוחשו. התוצאות יתמלאו אוטומטית.</div>`;
  const o = t.overall, s = o.stars;
  const bt = DATA.backtest;
  let html = `<div class="lead"><b>כך המערכת פגעה בפועל.</b> כל ניחוש נשמר לפני שהמשחק התחיל ונבדק מול התוצאה האמיתית (מ-${fmtDate(t.since)}). זה מדגם קטן, ולכן הוא משתנה מאוד מיום ליום; הבדיקה לאחור על אלפי משחקים מופיעה לצד כל מספר.</div>
  <div class="stats">
    <div class="stat"><b class="num">${o.dir_hits}/${o.n}</b><small>כיוון נכון (מי תנצח)</small><span class="sub num">${o.direction}% · בבדיקה לאחור ${bt ? bt.result_pct : "53"}%</span></div>
    <div class="stat"><b class="num">${o.exact_hits}/${o.n}</b><small>תוצאה מדויקת</small><span class="sub num">${o.exact}% · בבדיקה לאחור ${bt ? bt.exact_pct : "13"}%</span></div>
    <div class="stat"><b class="num">${o.over}%</b><small>מעל/מתחת 2.5 נכון</small><span class="sub">בבדיקה לאחור כ-58%</span></div>
    <div class="stat"><b class="num">${s.n ? s.won + "/" + s.n : "-"}</b><small>כוכבים שפגעו</small><span class="sub">${s.n ? `ממוצע יחס ${s.avg_odds}, ממוצע סיכוי ${s.avg_model_p}%` : "אין עדיין"}</span></div>
  </div>
  <div class="lead">שערים למשחק: בפועל <b class="num">${o.goals_actual}</b> מול <b class="num">${o.goals_model}</b> שהמודל ציפה לו. ${o.goals_actual - o.goals_model > 0.5 ? "הימים האחרונים היו עשירים בשערים מהצפוי." : ""}</div>`;
  const byDay = {};
  (t.recent || []).forEach(r => (byDay[r.date] = byDay[r.date] || []).push(r));
  Object.keys(byDay).sort().reverse().slice(0, 6).forEach(d => {
    const day = (t.days || []).find(x => x.date === d);
    html += `<div class="day">${dayLabel(d)}${day ? ` · כיוון ${day.dir_hits}/${day.n}, מדויק ${day.exact_hits}/${day.n}` : ""}</div>`;
    byDay[d].forEach(r => {
      html += `<div class="rrow"><div class="m"><span>${esc(r.home)} - ${esc(r.away)}</span><span class="res num">${r.actual}</span></div>
      <div class="pp">ניחוש <span class="num">${r.pick}</span> · ${esc(DATA.leagues[r.league])} · ${r.total} שערים</div><div class="tags">${tags(r)}</div></div>`;
    });
  });
  const lgs = Object.entries(t.by_league || {}).sort((a, b) => LG_ORDER.indexOf(a[0]) - LG_ORDER.indexOf(b[0]));
  if (lgs.length) html += `<h2>לפי תחרות</h2>` + lgs.map(([lg, x]) => `<div class="rrow"><div class="m"><span>${esc(DATA.leagues[lg])}</span><span class="num" style="font-size:13px;color:var(--ink-dim)">${x.n} משחקים</span></div><div class="tags"><span class="tag">כיוון ${x.dir_hits}/${x.n} (${x.direction}%)</span><span class="tag">מדויק ${x.exact_hits}/${x.n}</span><span class="tag">מעל/מתחת ${x.over}%</span></div></div>`).join("");
  return html;
}

/* ---------- view: all matches ---------- */
function viewAll(chips) {
  chips.hidden = false;
  const lgs = LG_ORDER.filter(l => DATA.predictions.some(p => p.league === l));
  const opts = [["all", "הכול"], ["A", "תוצאה בביטחון גבוה (A)"], ...lgs.map(l => [l, DATA.leagues[l]])];
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.all === k}">${esc(t)}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.all = b.dataset.c; render(); });
  let rows = DATA.predictions.filter(p => p.date >= todayIL());
  if (chip.all === "A") rows = rows.filter(p => p.tier === "A");
  else if (chip.all !== "all") rows = rows.filter(p => p.league === chip.all);
  rows = rows.sort(byTime);
  if (!rows.length) return `<div class="empty">אין משחקים בקטגוריה הזאת.</div>`;
  let html = "", day = "", i = 0;
  for (const p of rows) { if (p.date !== day) { day = p.date; html += `<div class="day">${dayLabel(day)}</div>`; } html += card(p, i++); }
  return html;
}

document.getElementById("reload").onclick = () => { load(); toast("מרענן..."); };
load();
