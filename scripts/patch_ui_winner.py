"""One-off UI patch: strategies, expected loss per 100, stake rule, per-strategy paper ledger, sharp status."""
import pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "docs/app.js"; s = p.read_text(encoding="utf-8")

old = '''  const opts = [["flag", "המלצות ערך"], ["surprise", "הפתעות (יחס 3+)"], ["paper", "יומן נייר"]];'''
new = '''  const opts = [["flag", "ערך לפי המודל"], ["favourite", "פייבוריטים"], ["sharp", "מול השוק החד"], ["surprise", "הפתעות (יחס 3+)"], ["paper", "יומן נייר"]];'''
assert old in s; s = s.replace(old, new)

old = '''  const rows = (DATA.value || []).filter(v => v.date >= todayIL());
  if (chip.winner === "paper") {'''
new = '''  const rows = (DATA.value || []).filter(v => v.date >= todayIL());
  const STR = { model_ev: "ערך לפי המודל", favourite: "פייבוריט", sharp_vs_winner: "Winner מעל השוק החד" };
  if (chip.winner === "sharp" && !DATA.sharp_available) {
    return html + `<div class="lead"><b>ההשוואה לשוק החד עדיין לא פעילה.</b> זו הדרך היחידה עם ראיות מאחוריה: כש-Winner משלם יותר מהמחיר ההוגן של בוקמייקרים חדים (Pinnacle ודומיו), יש יתרון אמיתי. כדי להפעיל: הרשמה חינמית ב-the-odds-api.com (500 בקשות בחודש), ושמירת המפתח בקובץ data/odds_api_key.txt במחשב. אחרי זה הלשונית הזאת תתמלא לבד.</div>`;
  }
  if (chip.winner === "paper") {'''
assert old in s; s = s.replace(old, new)

old = '''    if (!pap || !pap.recent || !pap.recent.length) return html + `<div class="empty">עדיין אין הימורי נייר שהסתיימו. כל המלצה מסומנת נרשמת אוטומטית במחיר של Winner ונסגרת מול התוצאה.</div>`;'''
new = '''    html += `<div class="lead"><b>מה זה יומן נייר:</b> כל המלצה נרשמת אוטומטית כהימור של יחידה אחת במחיר של Winner באותו רגע, בלי כסף. אחרי המשחק היא נסגרת מול התוצאה. ככה רואים אחרי עשרות הימורים מה באמת מרוויח ב-Winner, לפני שמסכנים שקל. שלוש שיטות נמדדות במקביל: ערך לפי המודל, פייבוריטים חזקים, ו-Winner מעל השוק החד.</div>`;
    if (pap && pap.by_strategy && Object.keys(pap.by_strategy).length) html += `<h2>לפי שיטה</h2>` + Object.entries(pap.by_strategy).map(([k, x]) => `<div class="rrow"><div class="m"><span>${STR[k] || k}</span><span class="num" style="color:${x.pnl > 0 ? "var(--good)" : (x.pnl < 0 ? "var(--bad)" : "inherit")}">${x.won}/${x.n} · ${x.pnl > 0 ? "+" : ""}${x.pnl} · ${x.roi}%</span></div><div class="pp">${x.open} פתוחים</div></div>`).join("");
    if (!pap || !pap.recent || !pap.recent.length) return html + `<div class="empty">עדיין אין הימורי נייר שהסתיימו. ${pap ? pap.open : 0} פתוחים ומחכים לתוצאות.</div>`;'''
assert old in s; s = s.replace(old, new)

old = '''  const list = chip.winner === "flag" ? rows.filter(v => v.flag) : rows.filter(v => v.surprise);'''
new = '''  const list = chip.winner === "flag" ? rows.filter(v => v.flag) : (chip.winner === "favourite" ? rows.filter(v => v.strategies.includes("favourite")) : (chip.winner === "sharp" ? rows.filter(v => v.sharp_flag) : rows.filter(v => v.surprise)));'''
assert old in s; s = s.replace(old, new)

old = '''  html += `<div class="lead">${chip.winner === "flag" ? "בחירות שבהן המודל נותן סיכוי גבוה מספיק מעל המחיר של Winner כדי לכסות את המרווח. <b>זה לא מבטיח רווח</b>: ליד כל בחירה מופיעה התשואה ההיסטורית של אותו סוג הימור." : "אנדרדוגים ותיקו ביחס 3 ומעלה שהמודל מעריך גבוה יותר מהשוק. היסטורית זה הסוג שמפסיד הכי הרבה; הסיכוי לזכייה כתוב ליד כל אחד."}</div>`;'''
new = '''  const leads = { flag: "בחירות שבהן המודל נותן סיכוי גבוה מספיק מעל המחיר של Winner כדי לכסות את המרווח. <b>זה לא מבטיח רווח</b>: ליד כל בחירה מופיעה התשואה ההיסטורית של אותו סוג הימור.",
    favourite: "פייבוריטים חזקים (יחס עד 1.60, המודל 62%+). זו השיטה שהפסידה הכי פחות בבדיקה לאחור (כ-1.4% מול השוק הממוצע, כ-10% ב-Winner). הסיכוי לזכות גבוה, הרווח קטן, וההפסד הצפוי לכל 100 ש\\"ח כתוב ליד כל אחד.",
    sharp: "בחירות שבהן Winner משלם יותר מהמחיר ההוגן של השוק החד. השיטה היחידה עם ראיות ליתרון אמיתי.",
    surprise: "אנדרדוגים ותיקו ביחס 3 ומעלה שהמודל מעריך גבוה יותר מהשוק. היסטורית זה הסוג שמפסיד הכי הרבה; הסיכוי לזכייה כתוב ליד כל אחד." };
  html += `<div class="lead">${leads[chip.winner]}</div>`;'''
assert old in s; s = s.replace(old, new)

old = '''      <div class="osrc">${v.hist_roi != null ? `הימורים מסוג זה הפסידו היסטורית <span class="num">${v.hist_roi}%</span> ליחידה (בדיקה לאחור, יחסי שוק ממוצעים).` : "אין נתון היסטורי לשוק הזה."} תוחלת = סיכוי המודל כפול היחס פחות 1.</div>'''
new = '''      <div class="osrc">${v.sharp_p != null ? `השוק החד נותן <span class="num">${v.sharp_p}%</span> (יתרון מול Winner <span class="num">${v.sharp_edge > 0 ? "+" : ""}${v.sharp_edge}%</span>). ` : ""}${v.loss_per_100 > 0 ? `הפסד צפוי לכל 100 ש"ח: <span class="num" style="color:var(--bad)">${v.loss_per_100}</span> ש"ח.` : `רווח צפוי לכל 100 ש"ח: <span class="num" style="color:var(--good)">+${Math.abs(v.ev).toFixed(1)}</span> ש"ח (לפי המודל בלבד).`} גודל הימור מומלץ (רבע קלי): <b class="num">${v.stake_pct}%</b> מהבנקרול${v.stake_pct === 0 ? ", כלומר לא להמר" : ""}. ${v.hist_roi != null ? `הימורים מסוג זה הפסידו היסטורית <span class="num">${v.hist_roi}%</span> ליחידה.` : ""}</div>'''
assert old in s; s = s.replace(old, new)

old = '''      <div class="ch">${v.kickoff ? `<span class="t num">${v.kickoff}</span>` : ""}<span>${fmtDate(v.date)}</span><span class="lg">${esc(DATA.leagues[v.league])}</span>${v.flag ? `<span class="star">ערך</span>` : ""}${v.surprise ? `<span class="tag gold" style="font-size:11px">הפתעה</span>` : ""}</div>'''
new = '''      <div class="ch">${v.kickoff ? `<span class="t num">${v.kickoff}</span>` : ""}<span>${fmtDate(v.date)}</span><span class="lg">${esc(DATA.leagues[v.league])}</span>${(v.strategies || []).map(t => `<span class="tag ${t === "sharp_vs_winner" ? "ok" : "gold"}" style="font-size:11px">${STR[t] || t}</span>`).join("")}${v.surprise ? `<span class="tag" style="font-size:11px">הפתעה</span>` : ""}</div>'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("ui patched")
