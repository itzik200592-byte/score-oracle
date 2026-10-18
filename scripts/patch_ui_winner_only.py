"""One-off: rewrite the daily view and the verdict menu for Winner-only, min odds 1.50."""
import pathlib
R = pathlib.Path(__file__).resolve().parent.parent

# readable handicap labels in picks.menu
p = R / "oracle/picks.py"; s = p.read_text(encoding="utf-8")
if "def _hc_labels" not in s:
    s = s.replace('''def menu(row):''', '''def _hc_labels(h, a, s):
    """Plain-Hebrew meaning of Winner's 3-way handicap outcomes (A: d>s, X: d==s, B: d<s; d = home - away goals)."""
    if s > 0:
        return (f"{h} מנצחת בהפרש {s + 1} או יותר", f"{h} מנצחת בדיוק בהפרש {s}", f"{a} עם יתרון {s}: לא מפסידה בהפרש {s}+")
    L = -s
    return (f"{h} עם יתרון {L}: לא מפסידה בהפרש {L}+", f"{a} מנצחת בדיוק בהפרש {L}", f"{a} מנצחת בהפרש {L + 1} או יותר")


def menu(row):''', 1)
    s = s.replace('''        pa, px, pb = hc_probs(marg, hc["s"])
        for k, p, lab, pr in (("A", pa, hc["labels"][0], hc["prices"][0]), ("X", px, hc["labels"][1], hc["prices"][1]), ("B", pb, hc["labels"][2], hc["prices"][2])):
            add(f"hc:{hc['s']}:{k}", lab, p, pr, "יתרון")''', '''        pa, px, pb = hc_probs(marg, hc["s"])
        labs = _hc_labels(h, a, hc["s"])
        for k, p, lab, pr in (("A", pa, labs[0], hc["prices"][0]), ("X", px, labs[1], hc["prices"][1]), ("B", pb, labs[2], hc["prices"][2])):
            add(f"hc:{hc['s']}:{k}", "יתרון: " + lab, p, pr, "יתרון")''')
    p.write_text(s, encoding="utf-8")

p = R / "docs/app.js"; s = p.read_text(encoding="utf-8")
a = s.index("/* ---------- view: daily strongest recommendation ---------- */")
b = s.index("/* ---------- view: stars ---------- */")
new = '''/* ---------- view: daily recommendations (Winner only, odds 1.50+) ---------- */
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

'''
s = s[:a] + new + s[b:]
p.write_text(s, encoding="utf-8")

v = R / "docs/verdict.js"; t = v.read_text(encoding="utf-8")
a = t.index("  const menu = (p.menu || [])")
b = t.index("  const marketLine = o ?")
newm = '''  const menu = (p.menu || []);
  const row = m => `<div class="hb" style="grid-template-columns:1fr 44px 82px;opacity:${m.eligible ? 1 : .55}"><span>${esc(m.label)}${m.eligible ? "" : ` <span class="osrc" style="display:inline">· מתחת ל-1.50</span>`}</span><b class="num">${m.p}%</b><span class="num" style="text-align:end;color:${m.ev > 0 && m.eligible ? "var(--good)" : "var(--ink-dim)"}">${Number(m.price).toFixed(2)} (${m.ev > 0 ? "+" : ""}${Math.round(100 * m.ev)}%)</span></div>`;
  const groups = ["תוצאה", "שערים", "יתרון"];
  const menuBox = menu.length ? `<div class="sec"><h4>כל השווקים של Winner במשחק: סיכוי, יחס ותוחלת</h4>${groups.map(g => { const ms = menu.filter(m => m.group === g).sort((x, y) => y.p - x.p); return ms.length ? `<div class="osrc" style="margin:8px 0 2px;color:var(--accent)">${g}</div>` + ms.map(row).join("") : ""; }).join("")}<div class="osrc">בסוגריים: תוחלת לפי המודל ביחס של Winner. שורות עמומות מתחת ליחס 1.50 ולכן לא נכללות בהמלצות.</div></div>` : "";
'''
t = t[:a] + newm + t[b:]
v.write_text(t, encoding="utf-8")
print("ui winner-only patched")
