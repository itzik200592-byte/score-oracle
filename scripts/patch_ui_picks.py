"""One-off UI patch: daily strongest recommendation, safest list, Winner-sold list, market menu in the verdict sheet,
and the accountability block (do the 85%+ picks hit?)."""
import pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "docs/app.js"; s = p.read_text(encoding="utf-8")

# 1) default stars tab -> daily picks, new chip
s = s.replace('let chip = { stars: "all", all: "all" };', 'let chip = { stars: "daily", all: "all" };')
old = '''  const opts = [["all", "הכול"], ["today", "היום"], ["value", "יתרון מול השוק"]];
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.stars === k}">${t}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.stars = b.dataset.c; render(); });'''
new = '''  const opts = [["daily", "המלצת היום"], ["all", "כוכבי יחס 1.5+"], ["today", "כוכבים היום"], ["value", "יתרון מול השוק"]];
  chips.innerHTML = opts.map(([k, t]) => `<button class="chip" data-c="${k}" aria-pressed="${chip.stars === k}">${t}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(b => b.onclick = () => { chip.stars = b.dataset.c; render(); });
  if (chip.stars === "daily") return viewDaily();'''
assert old in s; s = s.replace(old, new)

# 2) the daily view
s = s.replace('''/* ---------- view: stars ---------- */''', '''/* ---------- view: daily strongest recommendation ---------- */
function pickRow(x, showPrice = true) {
  const priceTxt = x.price ? `Winner <b class="num">${Number(x.price).toFixed(2)}</b> · תוחלת <b class="num" style="color:${x.ev > 0 ? "var(--good)" : "var(--bad)"}">${x.ev > 0 ? "+" : ""}${(100 * x.ev).toFixed(0)}%</b>` : `<span class="noval">לא נמכר ב-Winner</span>`;
  return `<article class="card" style="padding:12px"><div class="row"><div class="teams"><div class="team fav" style="direction:rtl;text-align:right;font-size:15.5px">${esc(x.label)}</div>
    <div class="sline">${esc(x.home)} - ${esc(x.away)}</div><div class="sline">${x.kickoff ? `<span class="num">${x.kickoff}</span> · ` : ""}${esc(DATA.leagues[x.league])}${x.lift != null ? ` · מעל הבסיס <span class="num">+${x.lift}</span> נק'` : ""}</div>
    ${showPrice ? `<div class="sline">${priceTxt}</div>` : ""}</div><div class="bigp"><b class="num">${x.p}%</b><small>סיכוי</small></div></div>
    <button class="vbtn" style="margin-top:8px;min-height:40px" data-v="${x.date}|${x.home}|${x.away}">כל השווקים במשחק</button></article>`;
}
function viewDaily() {
  const days = Object.keys(DATA.daily || {}).sort();
  if (!days.length) return `<div class="empty">אין נתונים להמלצה היומית.</div>`;
  const pt = DATA.picks_track;
  let html = `<div class="lead"><b>איך נבחרת ההמלצה:</b> מכל השווקים של כל משחק (כפל סיכוי, קבוצה מנצחת ומעל גול, שערי קבוצה, שער נקי, סך שערים), נבחר השוק עם הסיכוי הגבוה ביותר, בתנאי שהוא <b>גבוה מ-85% וגם גבוה בהרבה משכיחותו הרגילה</b> (כדי ש"מעל 0.5 שערים" לא יזכה כל יום). בבדיקה על 9,089 משחקים: <b>כשהמודל נתן 85%+, זה קרה בפועל ב-89-92%</b>, כלומר הוא שמרן.<br><b>הבעיה:</b> שווקים כמו "בית לא מפסידה" לא נמכרים ב-Winner. ב-Winner אפשר רק 1X2, מעל/מתחת 2.5, טווחי שערים ושתיהן מבקיעות, ושם היחס הנמוך מבטל את הרווח.</div>`;
  if (pt && pt.n) html += `<div class="stats"><div class="stat"><b class="num">${pt.hits}/${pt.n}</b><small>המלצות 85%+ שפגעו</small><span class="sub num">${pt.hit_rate}% בפועל מול ${pt.promised}% שהובטח</span></div>${pt.headline && pt.headline.n ? `<div class="stat"><b class="num">${pt.headline.hits}/${pt.headline.n}</b><small>ההמלצה הראשית היומית</small><span class="sub">${pt.open} פתוחות</span></div>` : ""}</div>`;
  else if (pt) html += `<div class="lead">מעקב: ${pt.open} המלצות 85%+ נרשמו ומחכות לתוצאות. כאן יופיע כמה מהן פגעו מול מה שהובטח.</div>`;
  days.slice(0, 2).forEach((d, di) => {
    const t = DATA.daily[d];
    html += `<div class="day">${dayLabel(d)}</div>`;
    if (t.headline) html += `<h2 style="margin-top:6px">ההמלצה החזקה</h2>` + pickRow(t.headline).replace('<article class="card"', '<article class="card S"');
    else html += `<div class="lead">אין היום שוק שעומד בתנאים (85%+ וגבוה משכיחותו). זה לא תקלה: לפעמים אין המלצה חזקה.</div>`;
    if (t.safe && t.safe.length > 1) html += `<h2>עוד בטוחים (אחד לכל משחק)</h2>` + t.safe.slice(1).map(x => pickRow(x)).join("");
    if (t.sold && t.sold.length) html += `<h2>הכי סביר ממה ש-Winner מוכר</h2><div class="lead">מהשווקים ש-Winner באמת מוכר, זה הסביר ביותר בכל משחק. התוחלת שלילית כמעט תמיד: המחיר כבר מגלם את הסיכוי ועוד מרווח.</div>` + t.sold.slice(0, 6).map(x => pickRow(x)).join("");
  });
  return html;
}

/* ---------- view: stars ---------- */''', 1)

p.write_text(s, encoding="utf-8")

# 3) verdict sheet: full market menu
v = R / "docs/verdict.js"; t = v.read_text(encoding="utf-8")
old = '''  ${oddsBox}'''
new = '''  ${menuBox}
  ${oddsBox}'''
assert old in t; t = t.replace(old, new, 1)
old = '''  const marketLine = o ?'''
new = '''  const menu = (p.menu || []).filter(m => !["o05"].includes(m.key)).slice(0, 18);
  const menuBox = menu.length ? `<div class="sec"><h4>תפריט שווקים לפי סיכוי (כל שוק מחושב מההתפלגות)</h4>${menu.map(m => `<div class="hb" style="grid-template-columns:1fr 46px 78px"><span>${esc(m.label)}${m.on_winner ? "" : ` <span class="osrc" style="display:inline">· לא נמכר ב-Winner</span>`}</span><b class="num">${m.p}%</b><span class="num" style="text-align:end;color:${m.price ? (m.ev > 0 ? "var(--good)" : "var(--ink-dim)") : "var(--ink-faint)"}">${m.price ? Number(m.price).toFixed(2) + " (" + (m.ev > 0 ? "+" : "") + Math.round(100 * m.ev) + "%)" : "-"}</span></div>`).join("")}<div class="osrc">בסוגריים: תוחלת ביחס של Winner. כשהמודל נותן 85%+ לשוק, בפועל זה קורה ב-89-92% (נבדק על 9,089 משחקים).</div></div>` : "";
  const marketLine = o ?'''
assert old in t; t = t.replace(old, new, 1)
v.write_text(t, encoding="utf-8")
print("ui patched")
