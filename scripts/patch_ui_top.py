"""One-off: the strongest pick sits at the very top; compact ranked list; explanations collapse at the bottom;
the recommendations tab is first and the default."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent

p = R / "oracle/picks.py"; s = p.read_text(encoding="utf-8")
s = s.replace("def day_picks(rows, day, top=6):", "def day_picks(rows, day, top=10):")
s = s.replace("for i, c in enumerate(day_picks(rows, d, top=3)[\"top\"]):", "for i, c in enumerate(day_picks(rows, d, top=3)[\"top\"]):")
p.write_text(s, encoding="utf-8"); ast.parse(s)

p = R / "docs/app.js"; s = p.read_text(encoding="utf-8")
s = s.replace('let view = safe(() => localStorage.getItem("view")) || "today";', 'let view = safe(() => localStorage.getItem("view2")) || "stars";')
s = s.replace('safe(() => localStorage.setItem("view", view))', 'safe(() => localStorage.setItem("view2", view))')
old = '''  const tabs = [["today", days[0] === todayIL() ? "היום" : "הקרובים", nToday], ["winner", "Winner", nVal], ["stars", "כוכבים", nStars], ["results", "תוצאות", nRes], ["all", "הכול", DATA.predictions.length]];'''
new = '''  const nPicks = ((DATA.daily || {})[days[0]] || { top: [] }).top.length;
  const tabs = [["stars", "המלצות", nPicks], ["today", days[0] === todayIL() ? "היום" : "הקרובים", nToday], ["winner", "Winner", nVal], ["results", "תוצאות", nRes], ["all", "הכול", DATA.predictions.length]];'''
assert old in s; s = s.replace(old, new)

a = s.index("/* ---------- view: daily recommendations (Winner only, odds 1.50+) ---------- */")
b = s.index("/* ---------- view: stars ---------- */")
new_view = '''/* ---------- view: daily recommendations (Winner only, odds 1.50+) ---------- */
const evTag = ev => `<span class="num" style="color:${ev > 0 ? "var(--good)" : "var(--bad)"}">${ev > 0 ? "+" : ""}${Math.round(100 * ev)}%</span>`;
function heroPick(x, day) {
  return `<article class="hero-pick"><div class="hp-top"><span class="hp-badge">ההמלצה החזקה ${dayLabel(day).split(",")[0]}</span><span class="hp-time num">${x.kickoff || ""}</span></div>
    <div class="hp-main"><div class="hp-p num">${x.p}<small>%</small></div><div class="hp-txt"><div class="hp-label">${esc(x.label)}</div><div class="hp-match">${esc(x.home)} - ${esc(x.away)}</div><div class="hp-meta">${esc(DATA.leagues[x.league])}</div></div></div>
    <div class="hp-row"><div><small>יחס Winner</small><b class="num">${Number(x.price).toFixed(2)}</b></div><div><small>תוחלת (מודל)</small><b>${evTag(x.ev)}</b></div><div><small>בבדיקה היסטורית</small><b class="num">62%</b></div></div>
    <button class="vbtn" data-v="${x.date}|${x.home}|${x.away}">כל השווקים של Winner במשחק</button></article>`;
}
function rankRow(x, i) {
  return `<button class="rank-row" data-v="${x.date}|${x.home}|${x.away}" aria-label="${esc(x.label)}, ${esc(x.home)} נגד ${esc(x.away)}, סיכוי ${x.p} אחוז"><span class="rr-n num">${i + 1}</span>
    <span class="rr-mid"><b>${esc(x.label)}</b><small>${esc(x.home)} - ${esc(x.away)} · <span class="num">${x.kickoff || ""}</span></small></span>
    <span class="rr-end"><b class="num">${x.p}%</b><small class="num">${Number(x.price).toFixed(2)} · ${evTag(x.ev)}</small></span></button>`;
}
function viewDaily() {
  const days = Object.keys(DATA.daily || {}).sort();
  if (!days.length) return `<div class="empty">אין נתונים להמלצה היומית.</div>`;
  const pt = DATA.picks_track;
  const first = days.find(d => DATA.daily[d].headline) || days[0];
  let html = "";
  const t0 = DATA.daily[first];
  if (t0 && t0.headline) html += heroPick(t0.headline, first);
  else html += `<div class="lead">אין כרגע בחירה ביחס 1.50+ עם נתוני Winner.</div>`;
  // ranked lists: highest probability first, one line per match
  days.slice(0, 2).forEach(d => {
    const t = DATA.daily[d];
    if (!t || !t.top || !t.top.length) return;
    html += `<div class="day">${dayLabel(d)} · מדורג לפי סיכוי</div><div class="rank-list">${t.top.map((x, i) => rankRow(x, i)).join("")}</div>`;
  });
  if (pt && pt.n) html += `<div class="stats" style="margin-top:18px"><div class="stat"><b class="num">${pt.hits}/${pt.n}</b><small>המלצות שפגעו</small><span class="sub num">${pt.hit_rate}% בפועל מול ${pt.promised}% שהובטח</span></div><div class="stat"><b class="num" style="color:${pt.pnl < 0 ? "var(--bad)" : "var(--good)"}">${pt.pnl > 0 ? "+" : ""}${pt.pnl}</b><small>רווח ביחידות במחירי Winner</small><span class="sub num">תשואה ${pt.roi}% · ${pt.open} פתוחות</span></div></div>`;
  else if (pt) html += `<div class="lead" style="margin-top:18px">מעקב: ${pt.open} המלצות נרשמו ומחכות לתוצאות. כאן יופיע כמה פגעו והרווח במחירי Winner.</div>`;
  const dogs = days.slice(0, 1).flatMap(d => (DATA.daily[d].underdogs || []));
  if (dogs.length) html += `<details class="help"><summary>אנדרדוגים (יחס 3+)</summary><div class="note"><p>בחירות ביחס 3 ומעלה שהמודל מעריך גבוה מהמחיר. היסטורית הימורים כאלה <b>הפסידו 14-24%</b>; התוחלת היא של המודל בלבד.</p></div><div class="rank-list" style="padding-bottom:10px">${dogs.map((x, i) => rankRow(x, i)).join("")}</div></details>`;
  html += `<details class="help"><summary>איך נבחרות ההמלצות</summary><div class="note"><p><b>רק Winner:</b> שווקים ש-Winner באמת מוכר (1X2, מעל/מתחת 2.5, טווחי שערים, שתיהן מבקיעות, "הימור יתרון"), ורק ביחס <b>1.50 ומעלה</b>. ההסתברות מחושבת מהמודל שנבדק על אלפי משחקים.</p><p><b>תקרה מתמטית:</b> ביחס 1.50 הסיכוי המשתמע הוא לכל היותר 66%, ועם המרווח של Winner כ-60%. המלצה של 90% בתנאים האלה לא קיימת.</p><p><b>בבדיקה על 823 ימים:</b> הבחירה הסבירה ביותר ביום (יחס 1.50+) פגעה ב-62%, והתשואה הייתה כמעט אפס מול יחסי שוק ממוצעים, ושלילית ב-Winner בגלל המרווח שלו.</p><p><b>"יתרון +1"</b> ב-Winner הוא בעצם "הקבוצה לא מפסידה" (כפל סיכוי) במחיר של Winner.</p></div></details>`;
  return html;
}

'''
s = s[:a] + new_view + s[b:]
# global click handler for rank rows reuses verdict.js (data-v on any element): ensure closest('.vbtn,.rank-row')
p.write_text(s, encoding="utf-8")

v = R / "docs/verdict.js"; t = v.read_text(encoding="utf-8")
t = t.replace('const b = e.target.closest(".vbtn");', 'const b = e.target.closest(".vbtn, .rank-row");')
v.write_text(t, encoding="utf-8")

c = R / "docs/style.css"; css = c.read_text(encoding="utf-8")
if ".hero-pick" not in css:
    css += """
/* top recommendation */
.hero-pick{background:linear-gradient(160deg,rgba(200,245,66,.16),rgba(200,245,66,.04) 60%),var(--surface);border:1px solid rgba(200,245,66,.5);border-radius:20px;padding:16px;margin:14px 0 6px;box-shadow:0 10px 30px rgba(200,245,66,.08)}
.hp-top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}
.hp-badge{background:var(--accent);color:var(--accent-ink);font-weight:800;font-size:12.5px;border-radius:999px;padding:3px 11px}
.hp-time{color:var(--ink-dim);font-weight:700;font-size:14px}
.hp-main{display:flex;align-items:center;gap:14px}
.hp-p{font-family:Rubik,sans-serif;font-weight:900;font-size:58px;line-height:1;color:var(--accent);letter-spacing:-2px}
.hp-p small{font-size:26px;margin-inline-start:2px}
.hp-txt{min-width:0}.hp-label{font-weight:900;font-size:19px;line-height:1.25}.hp-match{color:var(--ink);margin-top:4px;font-size:15px;direction:ltr;text-align:right}.hp-meta{color:var(--ink-dim);font-size:12.5px;margin-top:2px}
.hp-row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
.hp-row>div{background:rgba(255,255,255,.05);border-radius:12px;padding:8px 6px;text-align:center}
.hp-row small{display:block;color:var(--ink-dim);font-size:11px}.hp-row b{font-size:18px;font-weight:800}
.rank-list{display:flex;flex-direction:column;gap:8px}
.rank-row{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;text-align:start;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:11px 12px;min-height:60px;width:100%;transition:transform var(--dur) var(--ease)}
.rank-row:active{transform:scale(.985)}
.rr-n{width:30px;height:30px;border-radius:10px;background:var(--surface-2);color:var(--ink-dim);font-weight:900;display:flex;align-items:center;justify-content:center;font-size:14px}
.rank-row:first-child .rr-n{background:rgba(200,245,66,.18);color:var(--accent)}
.rr-mid{min-width:0;display:flex;flex-direction:column}.rr-mid b{font-size:14.5px;font-weight:700;line-height:1.3}.rr-mid small{color:var(--ink-dim);font-size:12px;direction:ltr;text-align:right}
.rr-end{display:flex;flex-direction:column;align-items:flex-end}.rr-end b{font-family:Rubik,sans-serif;font-size:21px;font-weight:800;color:var(--accent)}.rr-end small{font-size:11.5px;color:var(--ink-dim);direction:ltr}
.main-tabs{grid-template-columns:repeat(5,1fr)}
"""
    c.write_text(css, encoding="utf-8")
print("top-first UI patched")
