const $ = (id) => document.getElementById(id);

const TERMS = {
  "W-L": "Wins and losses. A tie, if one shows up, is listed as a third number.",
  PCT: "Winning percentage: wins divided by games played. Ties count as half a win.",
  PF: "Points scored this season.",
  PA: "Points allowed this season.",
  PPG: "Points scored per game. League average sits near 22.",
  DIFF: "Point differential: points scored minus points allowed. The fastest check on whether the record is real.",
  DIV: "Record against division opponents. After head-to-head, this is the first divisional tiebreaker.",
  CONF: "Record against conference opponents. Used after division record in the tiebreaker list.",
  GB: "Games back of the pivot in that table: the cut line on the conference board, the division leader on the division board. A plus means that club is ahead of the pivot. A dash means they are even.",
  STRK: "Current winning or losing streak.",
  GR: "Games remaining. The regular season is 17 games, plus a bye that does not count.",
  Path: "Win the division and the berth is automatic. Otherwise the club is in the wild-card pool. Three wild cards get in.",
  SOS: "Strength of the remaining schedule: the average winning percentage of the opponents still left.",
  SEED: "Current playoff seed. Seeds 1–4 are the division winners. Seeds 5–7 are the wild cards.",
  TO: "Turnover margin: takeaways minus giveaways. Positive means this club is winning the ball.",
  "3rd": "Third-down conversion rate. Around 40% is an average NFL offense.",
  RZ: "Red-zone touchdown rate: share of trips inside the opponent 20 that end in a touchdown. Good offenses live near 55–60%.",
  SACK: "Sack margin: sacks recorded by the defense minus sacks allowed by the offense.",
  YPG: "Net yards per game. Offense is pass plus rush. Defense is the yards allowed.",
  RTG: "NFL passer rating. Around 90 is average. Above 100 is a good season.",
  TKL: "Combined tackles.",
  YDS: "Yards from scrimmage in the category shown.",
  INT: "Interceptions.",
  TOP: "Time of possession per game. Thirty minutes is an even split of the clock.",
  Odds: "Share of simulated seasons in which this club wins its division or claims a wild card. Not a betting line.",
  Power: "A blend of point differential, shrunk toward a league-average offense and defense, and the margin over the last three games. A way to sort the league. Not an official NFL ranking.",
  Move: "Places moved in the power rankings since the order was frozen at the start of this week. A dash means no change.",
  "Last 3": "Record and point differential over the last three games, or fewer if the club has not played three yet.",
};

function assetRoot() {
  return (window.TEAM_PAGE && window.TEAM_PAGE.assetRoot) || "";
}

function teamHref(abbr) {
  if (!abbr) return assetRoot() || "./";
  return `${assetRoot()}teams/${String(abbr).toLowerCase()}/`;
}

function term(code, label = code) {
  const def = TERMS[code];
  if (!def) return esc(label);
  return `<abbr class="term" tabindex="0" title="${esc(def)}" data-tip="${esc(def)}">${esc(label)}</abbr>`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmtDate(iso, withTime = false) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const opts = withTime
    ? { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }
    : { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" };
  return new Intl.DateTimeFormat("en-US", opts).format(date);
}

function relativeTime(iso) {
  const date = new Date(iso);
  const mins = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return fmtDate(iso, true);
}

function fmtPct(value) {
  if (value == null || value === "") return "—";
  const text = Number(value).toFixed(3);
  return text.startsWith("0") ? text.slice(1) : text;
}

function signed(value) {
  if (value == null || value === "") return "—";
  const text = String(value);
  if (text.startsWith("+") || text.startsWith("-") || text === "0") return text;
  const n = Number(value);
  if (Number.isNaN(n)) return text;
  return `${n > 0 ? "+" : ""}${n}`;
}

function fmtOdds(pct) {
  if (pct == null || Number.isNaN(Number(pct))) return "—";
  const n = Number(pct);
  if (n > 0 && n < 1) return "<1%";
  if (n < 10) return `${n.toFixed(1)}%`;
  return `${Math.round(n)}%`;
}

function oneDecimal(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return esc(value);
  return n.toFixed(1);
}

function trendBadge(direction) {
  if (!direction || direction === "flat") return "";
  const arrow = direction === "up" ? "▲" : "▼";
  return `<span class="trend ${esc(direction)}">${arrow}</span>`;
}

function teamCell(team) {
  return `<a class="team-cell" href="${teamHref(team.abbr)}">
    <img src="${esc(team.logo)}" alt="" />
    <span>${esc(team.abbr)}</span>
  </a>`;
}

function headerRow(labels) {
  return `<tr>${labels.map((label) => `<th>${label}</th>`).join("")}</tr>`;
}

function moveCell(move) {
  const n = Number(move) || 0;
  if (!n) return `<span class="move flat">—</span>`;
  if (n > 0) return `<span class="move up">▲ ${n}</span>`;
  return `<span class="move down">▼ ${Math.abs(n)}</span>`;
}

function bindTermTips() {
  let tip = document.getElementById("termTip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "termTip";
    tip.className = "term-tip";
    tip.setAttribute("role", "tooltip");
    document.body.appendChild(tip);
  }
  document.querySelectorAll("abbr.term").forEach((el) => {
    if (!el.dataset.tip && el.getAttribute("title")) el.dataset.tip = el.getAttribute("title");
    if (el.dataset.tip && !el.getAttribute("aria-label")) {
      el.setAttribute("aria-label", `${el.textContent}: ${el.dataset.tip}`);
    }
    el.removeAttribute("title");
  });
  const place = (el) => {
    const text = el.dataset.tip;
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("show");
    const pad = 12;
    const rect = el.getBoundingClientRect();
    const left = Math.max(pad, Math.min(rect.left + rect.width / 2 - tip.offsetWidth / 2, window.innerWidth - tip.offsetWidth - pad));
    let top = rect.top - tip.offsetHeight - 8;
    if (top < pad) top = Math.min(rect.bottom + 8, window.innerHeight - tip.offsetHeight - pad);
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  };
  const hide = () => tip.classList.remove("show");
  if (bindTermTips.bound) return;
  bindTermTips.bound = true;
  document.addEventListener("pointerover", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("pointerout", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (!el) return;
    if (event.relatedTarget && el.contains(event.relatedTarget)) return;
    hide();
  });
  document.addEventListener("focusin", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}
