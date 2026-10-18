/* Score Oracle front end: 4 views (today, stars, results, all matches). */
const REPO = "itzik200592-byte/score-oracle";
const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const LG_ORDER = ["IL", "CL", "EL", "PL", "LL", "SA", "L1"];
let DATA = null;
let view = safe(() => localStorage.getItem("view")) || "today";
let chip = { stars: "daily", all: "all" };
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
  const nVal = (DATA.value || []).filter(v => v.flag && v.date >= todayIL()).length;
  const tabs = [["today", days[0] === todayIL() ? "היום" : "הקרובים", nToday], ["winner", "Winner", nVal], ["stars", "כוכבים", nStars], ["results", "תוצאות", nRes], ["all", "הכול", DATA.predictions.length]];
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
  else if (view === "winner") v.innerHTML = viewWinner(chips);
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

/* ---------- view: daily recommendations (Winner only, odds 1.50+) ---------- */
function pickRow(x, i) {
  const ev = x.ev, evTxt = `<b class="num" style="color:${ev > 0 ? "var(--good)" : "var(--bad)"}">${ev > 0 ? "+" : ""}${Math.round(100 * ev)}%</b>`;
  return `<article class="card ${i === 0 ? "S" : ""}" style="padding:12px"><div class="row"><div class="teams"><div class="team fav" style="direction:rtl;text-align:right;font-size:15.5px">${esc(x.label)}</div>
    <div class="sline">${esc(x.home)} - ${esc(x.away)}</div><div class="sline">${x.kickoff ? `<span class="num">${x.kickoff}</span> · ` : ""}${esc(DATA.leagues[x.league])}</div>
    <div class="sline">יחס Winner <b class="num">${Number(x.price).toFixed(2)}</b> · תוחלת לפי המודל ${evTxt}</div></div>
    <div class="bigp"><b class="num">${x.p}%</b><small>סיכוי</small></div></div>
    <button class="vbtn" style="margin-top:8px;min-height:40px" data-v="${x.date}|${x.home}|${x.away}">כל השווקים של Winner במשחק</button></article>`;
}
function viewDaily() {
  const days = Object.keys(DATA.daily || {}).sort();
  if (!days.length) return `<div class="empty">אין נתונים להמלצה היומית.</div>`;
  const pt = DATA.picks_track;
  let html = `<div class="lead"><b>כללי ההמלצה:</b> רק שווקים ש-Winner באמת מוכר (1X2, מעל/מתחת 2.5, טווחי שערים, שתיהן מבקיעות, והימור "יתרון"), ורק בחירה ביחס <b>1.50 ומעלה</b>. ההסתברות מחושבת מהמודל שנבדק על אלפי משחקים.<br><b>תקרה מתמטית:</b> ביחס 1.50 הסיכוי המשתמע הוא לכל היותר 66%, ועם המרווח של Winner בפועל כ-60%. <b>המלצה של 90% בתנאים האלה לא קיימת</b>, ואני לא ממציא אחת.<br>בבדיקה לאחור על 823 ימים: הבחירה הסבירה ביותר ביום (יחס 1.50+) פגעה ב-<b>62%</b>, והתשואה הייתה כמעט אפס מול יחסים ממוצעים בשוק, ושלילית ב-Winner בגלל המרווח שלו.</div>`;
  if (pt && pt.n) html += `<div class="stats"><div class="stat"><b class="num">${pt.hits}/${pt.n}</b><small>המלצות שפגעו</small><span class="sub num">${pt.hit_rate}% בפועל מול ${pt.promised}% שהובטח</span></div><div class="stat"><b class="num" style="color:${pt.pnl < 0 ? "var(--bad)" : "var(--good)"}">${pt.pnl > 0 ? "+" : ""}${pt.pnl}</b><small>רווח ביחידות במחירי Winner</small><span class="sub num">תשואה ${pt.roi}% · ${pt.open} פתוחות</span></div></div>`;
  else if (pt) html += `<div class="lead">מעקב: ${pt.open} המלצות נרשמו ומחכות לתוצאות. כאן יופיע כמה פגעו ומה הרווח ביחס Winner.</div>`;
  days.slice(0, 2).forEach(d => {
    const t = DATA.daily[d];
    html += `<div class="day">${dayLabel(d)}</div>`;
    if (!t.top || !t.top.length) { html += `<div class="lead">אין בחירה ביחס 1.50+ עם נתוני Winner למשחקי היום.</div>`; return; }
    html += `<h2 style="margin-top:6px">ההמלצה החזקה</h2><div class="lead" style="margin:6px 0 10px">הסיכוי הגבוה ביותר ביום ביחס 1.50+: <b class="num">${t.top[0].p}%</b>. תקרת היום: ${t.ceiling}%.</div>` + t.top.map((x, i) => pickRow(x, i)).join("");
    if (t.underdogs && t.underdogs.length) html += `<h2>אנדרדוגים (יחס 3+)</h2><div class="lead">בחירות ביחס 3 ומעלה שהמודל מעריך גבוה מהמחיר. <b>היסטורית הימורים כאלה הפסידו 14-24%</b>; ה"תוחלת" כאן היא של המודל בלבד.</div>` + t.underdogs.map(x => pickRow(x, -1)).join("");
  });
  return html;
}

/* ---------- view: stars ---------- */
function viewStars(chips) {
  chips.hidden = false;
  const all = DATA.predictions.filter(p => p.odds && p.odds.star && p.date >= todayIL());
  const opts = [["daily", "המלצת היום"], ["all", "כוכבי יחס 1.5+"], ["today", "כוכבים היום"], ["value", "יתרון מול השוק"]];
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.stars === k}">${t}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.stars = b.dataset.c; render(); });
  if (chip.stars === "daily") return viewDaily();
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

/* ---------- view: Winner value scanner + paper bets ---------- */
function viewWinner(chips) {
  chips.hidden = false;
  const opts = [["flag", "ערך לפי המודל"], ["favourite", "פייבוריטים"], ["sharp", "מול השוק החד"], ["surprise", "הפתעות (יחס 3+)"], ["paper", "יומן נייר"]];
  chip.winner = chip.winner || "flag";
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.winner === k}">${t}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.winner = b.dataset.c; render(); });
  const T = DATA.value_truth || {};
  const pap = DATA.paper;
  let html = `<div class="lead" style="border-color:rgba(255,201,77,.5)"><b>קודם האמת, ואז ההמלצות.</b> בבדיקה לאחור על 6,673 משחקים (2022-2026), הימור קבוע על כל בחירה שהמודל ראה בה ערך הפסיד <b class="num">${T.all_ev}%</b> מול יחסי שוק ממוצעים, והפתעות ביחס 6 ומעלה הפסידו <b class="num">${T.longshots}%</b>. המרווח של Winner (11-18%) גבוה מהממוצע, ולכן בפועל זה גרוע יותר. <b>אף מודל סטטיסטי לא מנצח את הבוקמייקר לאורך זמן.</b> לכן כל המלצה כאן נרשמת כהימור נייר במחיר של Winner, ואת הרווח האמיתי תראה ביומן לפני שאתה מסכן כסף.</div>`;
  if (pap) {
    const cls = pap.pnl > 0 ? "val" : (pap.pnl < 0 ? "" : "");
    html += `<div class="stats"><div class="stat"><b class="num">${pap.n}</b><small>הימורי נייר שהסתיימו</small><span class="sub">${pap.open} פתוחים</span></div><div class="stat"><b class="num ${cls}" style="${pap.pnl < 0 ? "color:var(--bad)" : (pap.pnl > 0 ? "color:var(--good)" : "")}">${pap.pnl > 0 ? "+" : ""}${pap.pnl.toFixed(1)}</b><small>רווח ביחידות (1 יחידה להימור)</small><span class="sub num">תשואה ${pap.roi}% · ${pap.won} זכיות</span></div></div>`;
  }
  const rows = (DATA.value || []).filter(v => v.date >= todayIL());
  const STR = { model_ev: "ערך לפי המודל", favourite: "פייבוריט", sharp_vs_winner: "Winner מעל השוק החד" };
  if (chip.winner === "sharp" && !DATA.sharp_available) {
    return html + `<div class="lead"><b>ההשוואה לשוק החד עדיין לא פעילה.</b> זו הדרך היחידה עם ראיות מאחוריה: כש-Winner משלם יותר מהמחיר ההוגן של בוקמייקרים חדים (Pinnacle ודומיו), יש יתרון אמיתי. כדי להפעיל: הרשמה חינמית ב-the-odds-api.com (500 בקשות בחודש), ושמירת המפתח בקובץ data/odds_api_key.txt במחשב. אחרי זה הלשונית הזאת תתמלא לבד.</div>`;
  }
  if (chip.winner === "paper") {
    html += `<div class="lead"><b>מה זה יומן נייר:</b> כל המלצה נרשמת אוטומטית כהימור של יחידה אחת במחיר של Winner באותו רגע, בלי כסף. אחרי המשחק היא נסגרת מול התוצאה. ככה רואים אחרי עשרות הימורים מה באמת מרוויח ב-Winner, לפני שמסכנים שקל. שלוש שיטות נמדדות במקביל: ערך לפי המודל, פייבוריטים חזקים, ו-Winner מעל השוק החד.</div>`;
    if (pap && pap.by_strategy && Object.keys(pap.by_strategy).length) html += `<h2>לפי שיטה</h2>` + Object.entries(pap.by_strategy).map(([k, x]) => `<div class="rrow"><div class="m"><span>${STR[k] || k}</span><span class="num" style="color:${x.pnl > 0 ? "var(--good)" : (x.pnl < 0 ? "var(--bad)" : "inherit")}">${x.won}/${x.n} · ${x.pnl > 0 ? "+" : ""}${x.pnl} · ${x.roi}%</span></div><div class="pp">${x.open} פתוחים</div></div>`).join("");
    if (!pap || !pap.recent || !pap.recent.length) return html + `<div class="empty">עדיין אין הימורי נייר שהסתיימו. ${pap ? pap.open : 0} פתוחים ומחכים לתוצאות.</div>`;
    pap.recent.forEach(r => { html += `<div class="rrow"><div class="m"><span>${esc(r.home)} - ${esc(r.away)}</span><span class="num" style="color:${r.pnl > 0 ? "var(--good)" : "var(--bad)"};font-weight:900">${r.pnl > 0 ? "+" : ""}${Number(r.pnl).toFixed(2)}</span></div><div class="pp">${esc(r.label)} @ <span class="num">${Number(r.odds).toFixed(2)}</span> · המודל <span class="num">${r.model_p}%</span> · תוצאה <span class="num">${esc(r.result)}</span> · ${fmtDate(r.date)}</div></div>`; });
    if (pap.by_market) html += `<h2>לפי שוק</h2>` + Object.entries(pap.by_market).map(([k, x]) => `<div class="rrow"><div class="m"><span>${{ "1x2": "1X2", ou: "מעל/מתחת", btts: "שתיהן מבקיעות", cs: "תוצאה מדויקת" }[k] || k}</span><span class="num">${x.won}/${x.n} · תשואה ${x.roi}%</span></div></div>`).join("");
    return html;
  }
  const list = chip.winner === "flag" ? rows.filter(v => v.flag) : (chip.winner === "favourite" ? rows.filter(v => v.strategies.includes("favourite")) : (chip.winner === "sharp" ? rows.filter(v => v.sharp_flag) : rows.filter(v => v.surprise)));
  if (!list.length) return html + `<div class="empty">${chip.winner === "flag" ? "אין כרגע בחירה שעוברת את סף הערך אחרי המרווח של Winner. זה המצב הרגיל, לא תקלה." : "אין כרגע הפתעות (יחס 3 ומעלה שהמודל נותן להן סיכוי גבוה מהשוק)."}</div>`;
  const leads = { flag: "בחירות שבהן המודל נותן סיכוי גבוה מספיק מעל המחיר של Winner כדי לכסות את המרווח. <b>זה לא מבטיח רווח</b>: ליד כל בחירה מופיעה התשואה ההיסטורית של אותו סוג הימור.",
    favourite: "פייבוריטים חזקים (יחס עד 1.60, המודל 62%+). זו השיטה שהפסידה הכי פחות בבדיקה לאחור (כ-1.4% מול השוק הממוצע, כ-10% ב-Winner). הסיכוי לזכות גבוה, הרווח קטן, וההפסד הצפוי לכל 100 ש\"ח כתוב ליד כל אחד.",
    sharp: "בחירות שבהן Winner משלם יותר מהמחיר ההוגן של השוק החד. השיטה היחידה עם ראיות ליתרון אמיתי.",
    surprise: "אנדרדוגים ותיקו ביחס 3 ומעלה שהמודל מעריך גבוה יותר מהשוק. היסטורית זה הסוג שמפסיד הכי הרבה; הסיכוי לזכייה כתוב ליד כל אחד." };
  html += `<div class="lead">${leads[chip.winner]}</div>`;
  list.forEach((v, i) => {
    html += `<article class="card ${v.flag ? "S" : ""}" style="animation-delay:${Math.min(i, 8) * 35}ms">
      <div class="ch">${v.kickoff ? `<span class="t num">${v.kickoff}</span>` : ""}<span>${fmtDate(v.date)}</span><span class="lg">${esc(DATA.leagues[v.league])}</span>${(v.strategies || []).map(t => `<span class="tag ${t === "sharp_vs_winner" ? "ok" : "gold"}" style="font-size:11px">${STR[t] || t}</span>`).join("")}${v.surprise ? `<span class="tag" style="font-size:11px">הפתעה</span>` : ""}</div>
      <div class="row"><div class="teams"><div class="team fav" style="direction:rtl;text-align:right">${esc(v.label)}</div><div class="sline">${esc(v.home)} - ${esc(v.away)}</div></div><div class="bigp"><b class="num">${v.model_p}%</b><small>סיכוי לזכייה לפי המודל</small></div></div>
      <div class="oddsmini"><div>יחס Winner<b class="num">${Number(v.odds).toFixed(2)}</b></div><div>השוק נותן<b class="num">${v.market_p != null ? v.market_p + "%" : "-"}</b></div><div>תוחלת<b class="num" style="color:${v.ev > 0 ? "var(--good)" : "var(--bad)"}">${v.ev > 0 ? "+" : ""}${v.ev}%</b></div></div>
      <div class="osrc">${v.sharp_p != null ? `השוק החד נותן <span class="num">${v.sharp_p}%</span> (יתרון מול Winner <span class="num">${v.sharp_edge > 0 ? "+" : ""}${v.sharp_edge}%</span>). ` : ""}${v.loss_per_100 > 0 ? `הפסד צפוי לכל 100 ש"ח: <span class="num" style="color:var(--bad)">${v.loss_per_100}</span> ש"ח.` : `רווח צפוי לכל 100 ש"ח: <span class="num" style="color:var(--good)">+${Math.abs(v.ev).toFixed(1)}</span> ש"ח (לפי המודל בלבד).`} גודל הימור מומלץ (רבע קלי): <b class="num">${v.stake_pct}%</b> מהבנקרול${v.stake_pct === 0 ? ", כלומר לא להמר" : ""}. ${v.hist_roi != null ? `הימורים מסוג זה הפסידו היסטורית <span class="num">${v.hist_roi}%</span> ליחידה.` : ""}</div>
      <button class="vbtn" data-v="${v.date}|${v.home}|${v.away}">פסק דין מלא</button></article>`;
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
