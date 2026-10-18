/* Verdict panel: full-distribution opinion for one match (score, winner, goals, over/under, percentages). */
function verdictHtml(p) {
  const d = p.dist, o = p.odds, lg = DATA.leagues[p.league];
  if (!d) return `<div class="in"><button class="x" aria-label="סגור" onclick="this.closest('dialog').close()">×</button><p>אין עדיין התפלגות למשחק הזה. רענן את הנתונים.</p></div>`;
  const mx = Math.max(p.pH, p.pD, p.pA), dk = mx === p.pH ? "h" : (mx === p.pA ? "a" : "d");
  const winner = dk === "h" ? p.home : (dk === "a" ? p.away : "תיקו");
  const sorted = [p.pH, p.pD, p.pA].sort((x, y) => y - x), close = sorted[0] - sorted[1] < 6;
  const goalsTxt = d.exp_total >= 3.2 ? "משחק פתוח עם הרבה שערים" : (d.exp_total <= 2.3 ? "משחק סגור עם מעט שערים" : "כמות שערים רגילה");
  const maxT = Math.max(...d.total);
  const names = ["0", "1", "2", "3", "4", "5", "6+"];
  const bars = d.total.map((v, i) => `<div class="hb"><span class="num">${names[i]}</span><i class="${v === maxT ? "top" : ""}" style="width:${Math.max(2, v / maxT * 100)}%"></i><b class="num">${v.toFixed(0)}%</b></div>`).join("");
  const ln = [
    ["מעל 1.5", d.over["1.5"], null], ["מעל 2.5", d.over["2.5"], o && o.over25],
    ["מעל 3.5", d.over["3.5"], null], ["שתיהן מבקיעות", d.btts, o && o.btts_yes],
    ["מתחת 2.5", 100 - d.over["2.5"], o && o.under25], [p.home + " לא סופגת", d.cs_home, null]];
  const lines = ln.map(([t, v, pr]) => `<div>${esc(t)} <b class="num">${v.toFixed(0)}%</b>${pr ? `<div class="osrc">יחס Winner <span class="num">${pr.toFixed(2)}</span> · משתמע <span class="num">${(100 / pr).toFixed(0)}%</span></div>` : ""}</div>`).join("");
  const tops = d.top.slice(0, 6).map(t => `<div class="hb"><span class="num">${t.s}</span><i style="width:${Math.max(2, t.p / d.top[0].p * 100)}%"></i><b class="num">${t.p.toFixed(1)}%${o && o.cs && o.cs[t.s] ? ` · <span style="color:var(--ink-dim)">${o.cs[t.s].toFixed(1)}</span>` : ""}</b></div>`).join("");
  const cal = DATA.calib && DATA.calib[p.league];
  const op = p.opinion, c = p.ctx;
  const cell = (t, v) => `<div>${t}<br><b class="num" style="float:none">${v || "-"}</b></div>`;
  const ctxLine = c ? `<div class="sec"><h4>נתוני הסיטואציה</h4><div class="lines">${cell(esc(p.home) + " בבית", c.home && c.home.home10)}${cell(esc(p.away) + " בחוץ", c.away && c.away.away10)}${cell("כושר " + esc(p.home), c.home && c.home.form)}${cell("כושר " + esc(p.away), c.away && c.away.form)}</div>${(c.h2h && c.h2h.length) ? `<div class="osrc" style="margin-top:6px">מפגשים ישירים אחרונים: ${c.h2h.map(esc).join(" | ")}</div>` : ""}${((c.home && c.home.partial) || (c.away && c.away.partial)) ? `<div class="osrc">לחלק מהקבוצות אין לנו את הליגה המקומית, לכן נתוני כושר ומנוחה חלקיים.</div>` : ""}</div>` : "";
  const leanTxt = op ? (op.lean === "h" ? "בית" : (op.lean === "a" ? "חוץ" : "תיקו")) : "";
  const vtxt = op ? (op.verified === "ok" ? "שחקנים אומתו מול הסגל הנוכחי (ESPN)" : (op.verified === "problems" ? "אזהרה: נזכרו שחקנים שאינם בסגל הנוכחי: " + esc((op.unknown_players || []).join(", ")) : "סגלים לא אומתו, התייחס בזהירות לשמות שחקנים")) : "";
  const opLine = op ? `<div class="opx"><b>דעת האנליסט (חדשות וסיטואציה):</b> נוטה ל${leanTxt}, ביטחון ${esc(op.confidence || "")}<div class="osrc">${vtxt}</div><div>${esc(op.summary || "")}</div><h5>${esc(p.home)}</h5><div>${esc(op.home_view || "")}</div><h5>${esc(p.away)}</h5><div>${esc(op.away_view || "")}</div>${(op.factors && op.factors.length) ? `<div class="chipsx">${op.factors.map(f => `<span>${esc(f)}</span>`).join("")}</div>` : ""}${(op.adjustments && op.adjustments.length) ? `<h5>התאמות שהוכנסו</h5><div>${op.adjustments.map(esc).join("<br>")}</div>` : ""}<div class="osrc">${(op.sources || []).map(esc).join(" · ")}</div></div>` : "";
  const oddsBox = o ? `<div class="sec"><h4>יחסי ${esc(o.src)}: מודל מול שוק</h4><div class="lines">${[["h", esc(p.home), p.pH], ["d", "תיקו", p.pD], ["a", esc(p.away), p.pA]].map(([k, t, mp]) => `<div>${t}<b class="num">${o[k].toFixed(2)}</b><div class="osrc">מודל <span class="num">${mp}%</span> · שוק <span class="num">${o.market_p[k]}%</span> · ${o.ev[k] > 0 ? "המודל גבוה מהשוק" : "ללא יתרון"}</div></div>`).join("")}</div><div class="osrc">מרווח הבוקי ${o.margin}%${o.at ? ` · נקרא ${new Date(o.at).toLocaleString("he-IL", { timeZone: "Asia/Jerusalem", hour: "2-digit", minute: "2-digit" })}` : ""}</div></div>` : "";
  const menu = (p.menu || []).filter(m => !["o05"].includes(m.key)).slice(0, 18);
  const menuBox = menu.length ? `<div class="sec"><h4>תפריט שווקים לפי סיכוי (כל שוק מחושב מההתפלגות)</h4>${menu.map(m => `<div class="hb" style="grid-template-columns:1fr 46px 78px"><span>${esc(m.label)}${m.on_winner ? "" : ` <span class="osrc" style="display:inline">· לא נמכר ב-Winner</span>`}</span><b class="num">${m.p}%</b><span class="num" style="text-align:end;color:${m.price ? (m.ev > 0 ? "var(--good)" : "var(--ink-dim)") : "var(--ink-faint)"}">${m.price ? Number(m.price).toFixed(2) + " (" + (m.ev > 0 ? "+" : "") + Math.round(100 * m.ev) + "%)" : "-"}</span></div>`).join("")}<div class="osrc">בסוגריים: תוחלת ביחס של Winner. כשהמודל נותן 85%+ לשוק, בפועל זה קורה ב-89-92% (נבדק על 9,089 משחקים).</div></div>` : "";
  const marketLine = o ? `<div class="osrc">השוק (${esc(o.src)}) אחרי הסרת המרווח: בית ${o.market_p.h}% · תיקו ${o.market_p.d}% · חוץ ${o.market_p.a}%${p.live_mkt ? " · שולב בתחזית" : ""}</div>` : "";
  const overTxt = d.over["2.5"] >= 55 ? "נוטה למעל" : (d.over["2.5"] <= 45 ? "נוטה למתחת" : "קרוב ל-50:50");
  return `<div class="in"><header class="sh"><h3>${esc(p.home)} נגד ${esc(p.away)}<br><small style="font-weight:400;color:var(--ink-dim);font-size:13px">${esc(lg)} · ${fmtDate(p.date)}${o && o.kickoff ? " · " + o.kickoff + " שעון ישראל" : ""}</small></h3><button class="x" aria-label="סגור" onclick="this.closest('dialog').close()">×</button></header>
  <div class="hero">
    <div><small>מי תנצח</small><b class="acc">${esc(winner)}</b><small class="num">${mx}% ${close ? "· הפרש קטן, משחק צמוד" : ""}</small></div>
    <div><small>התוצאה לדעתי</small><b class="num">${p.pick}</b><small class="num">${p.p_pick}% לתוצאה המדויקת</small></div>
    <div><small>כמה שערים</small><b class="num">${d.exp_total.toFixed(1)}</b><small>${goalsTxt} · הכי סביר ${d.likely_total}</small></div>
    <div><small>מעל 2.5 שערים</small><b class="num">${d.over["2.5"].toFixed(0)}%</b><small>${overTxt}</small></div>
  </div>
  <div class="sec"><h4>ניצחון / תיקו / הפסד</h4><div class="bar" aria-hidden="true"><i class="h" style="width:${p.pH}%"></i><i class="d" style="width:${p.pD}%"></i><i class="a" style="width:${p.pA}%"></i></div>
    <div class="legend"><span>${esc(p.home)} <b class="num">${p.pH}%</b></span><span>תיקו <b class="num">${p.pD}%</b></span><span>${esc(p.away)} <b class="num">${p.pA}%</b></span></div>${marketLine}</div>
  <div class="sec"><h4>כמה שערים ייכנסו (סך הכול)</h4>${bars}</div>
  ${menuBox}
  ${oddsBox}
  <div class="sec"><h4>שווקים</h4><div class="lines">${lines}</div></div>
  <div class="sec"><h4>התוצאות הסבירות${o && o.cs ? " (בסוף: יחס Winner)" : ""}</h4>${tops}</div>
  ${opLine}${ctxLine}
  <div class="row2"><button class="btn primary" id="askc">בקש מ-Claude פסק דין מעמיק</button><button class="btn" id="copyp">העתק שאלה</button></div>
  <div class="trust"><b>כמה לסמוך על זה?</b> ${cal ? `בבדיקה לאחור על ${cal.n} משחקים ב${esc(lg)}: הכיוון נכון ב-${cal.direction}% והתוצאה המדויקת ב-${cal.exact}%.` : ""} אחוזי מעל/מתחת ושתיהן מבקיעות נבדקו על 9,000 משחקים וסטו נקודה עד נקודה וחצי. המודל מעריך נמוך במעט פייבוריטים חזקים מאוד (כ-3 נקודות). אין כאן ודאות: גם 70% פירושו שבשלושה משחקים מתוך עשרה זה לא קורה. ניתוח סטטיסטי, לא המלצת הימור.</div></div>`;
}

function buildPrompt(p) {
  const d = p.dist || {}, o = p.odds, c = p.ctx || {};
  const L = [];
  L.push(`אתה אנליסט כדורגל מומחה. תן לי פסק דין כן ומדויק על המשחק: ${p.home} נגד ${p.away} (${DATA.leagues[p.league]}, ${p.date}${o && o.kickoff ? ", " + o.kickoff + " שעון ישראל" : ""}).`);
  L.push(`נתוני המודל הסטטיסטי שלי: ניצחון בית ${p.pH}%, תיקו ${p.pD}%, ניצחון חוץ ${p.pA}%. תוצאה סבירה ביותר ${p.pick} (${p.p_pick}%). שערים צפויים ${d.exp_total}. מעל 2.5: ${d.over ? d.over["2.5"] : "?"}%, שתיהן מבקיעות: ${d.btts}%. תוצאות סבירות: ${(d.top || []).slice(0, 5).map(t => t.s + " " + t.p + "%").join(", ")}.`);
  if (o) L.push(`יחסי Winner: בית ${o.h}, תיקו ${o.d}, חוץ ${o.a}${o.over25 ? `, מעל 2.5 ${o.over25}, מתחת ${o.under25}` : ""}.`);
  if (c.home || c.away) L.push(`כושר ${p.home}: ${(c.home && c.home.form) || "?"}, שיא בית 10 אחרונים ${(c.home && c.home.home10) || "?"}. כושר ${p.away}: ${(c.away && c.away.form) || "?"}, שיא חוץ ${(c.away && c.away.away10) || "?"}.`);
  if (p.opinion) L.push(`הערת אנליסט קודמת: ${p.opinion.summary}`);
  L.push("חפש ברשת חדשות עדכניות (פציעות, הרחקות והשעיות, הרכבים צפויים, רוטציה, מוטיבציה, קהל ונסיעה) ואז תן לי: 1) מי תנצח ובאיזה אחוז, 2) תוצאה מדויקת אחת והסתברות, 3) מעל או מתחת 2.5 ובאיזה אחוז, 4) כמה שערים סך הכול (טווח ואחוזים), 5) שתיהן מבקיעות באחוזים, 6) איפה אתה חולק על המודל ולמה. היה כן, ציין חוסר ודאות, ואל תמציא נתונים.");
  return L.join("\n");
}

document.addEventListener("click", e => {
  const b = e.target.closest(".vbtn");
  if (!b) return;
  const [date, home, away] = b.dataset.v.split("|");
  const p = DATA.predictions.find(x => x.date === date && x.home === home && x.away === away);
  if (!p) return;
  const dlg = document.getElementById("sheet");
  dlg.innerHTML = verdictHtml(p);
  const pr = buildPrompt(p);
  const ask = dlg.querySelector("#askc"), cp = dlg.querySelector("#copyp");
  if (ask) ask.onclick = () => window.open("https://claude.ai/new?q=" + encodeURIComponent(pr), "_blank", "noopener");
  if (cp) cp.onclick = async () => { try { await navigator.clipboard.writeText(pr); toast("השאלה הועתקה. הדבק ב-Claude."); } catch (_) { toast("לא הצלחתי להעתיק, נסה את הכפתור השני"); } };
  dlg.showModal();
});
document.getElementById("sheet").addEventListener("click", e => { if (e.target.id === "sheet") e.target.close(); });
