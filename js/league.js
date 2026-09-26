function renderTicker(data) {
  const line = (data.ticker || []).join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderHero(data) {
  const narrative = data.narrative || {};
  const spot = data.spotlight || {};
  $("statusKicker").textContent = narrative.kicker || "";
  $("headline").textContent = narrative.headline || "";
  $("blurb").textContent = narrative.blurb || "";
  $("heroChips").innerHTML = (data.chips || [])
    .map((chip) => `<div class="chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></div>`)
    .join("");
  const card = (label, club, className) => {
    if (!club) return "";
    const odds = club.playoffPct == null ? "" : ` · ${fmtOdds(club.playoffPct)}`;
    return `<a class="hero-score ${className || ""}" href="${teamHref(club.abbr)}">
      <p class="score-label">${esc(label)}</p>
      <p class="score-giant">${esc(club.abbr)}</p>
      <p class="score-sub">${esc(club.nickname || club.name || "")} · ${esc(club.record || "")}${esc(odds)}</p>
    </a>`;
  };
  $("heroMeters").innerHTML = [
    card("Power No. 1", spot.top, ""),
    card("AFC cut line", spot.afc, "odds"),
    card("NFC cut line", spot.nfc, "magic"),
  ].join("");
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = data.weekLabel || `Week ${data.week || ""}`;
}

function renderClubs(data) {
  $("clubStrip").innerHTML = (data.clubs || []).map((team) => `
    <a class="club-link" href="${teamHref(team.abbr)}">
      <img src="${esc(team.logo)}" alt="" />
      <span>${esc(team.abbr)}</span>
    </a>
  `).join("");
}

function renderRankings(data) {
  $("rankingsBlurb").textContent = data.rankingsBlurb || "";
  const head = [
    "#", term("Move", "Move"), "Team", term("W-L", "W-L"), term("DIFF", "Diff"),
    term("Last 3", "Last 3"), term("STRK", "Strk"), term("Power", "Power"), term("Odds", "Odds"),
  ];
  document.querySelector("#rankTable thead").innerHTML = headerRow(head);
  document.querySelector("#rankTable tbody").innerHTML = (data.powerRankings || []).map((team) => `
    <tr>
      <td>${esc(team.rank)}</td>
      <td>${moveCell(team.move)}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.formRecord || "—")} · ${esc(signed(team.formDiff))}</td>
      <td>${esc(team.streak || "—")}</td>
      <td>${esc(team.power ?? "—")}</td>
      <td>${esc(fmtOdds(team.playoffPct))}</td>
    </tr>
  `).join("");
}

function standingsTable(tableId, rows) {
  const head = [
    "#", "Team", term("Path", "Path"), term("W-L", "W-L"), term("DIFF", "Diff"),
    term("GB", "GB"), term("Odds", "Odds"),
  ];
  const table = document.querySelector(tableId);
  table.querySelector("thead").innerHTML = headerRow(head);
  table.querySelector("tbody").innerHTML = (rows || []).map((team) => {
    const classes = [
      team.inField ? "row-in" : "",
      team.isCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.isCut ? `<div class="cut-note">Last berth</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.path)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.gb ?? "—")}</td>
      <td>${esc(fmtOdds(team.playoffPct))}</td>
    </tr>`;
  }).join("");
}

function renderPicture(data) {
  $("afcBlurb").textContent = data.afcBlurb || "";
  $("nfcBlurb").textContent = data.nfcBlurb || "";
  standingsTable("#afcTable", data.afc);
  standingsTable("#nfcTable", data.nfc);
}

function renderLeaders(data) {
  $("divLeaders").innerHTML = (data.leaders || []).map((team) => `
    <a class="div-card" href="${teamHref(team.abbr)}">
      <img src="${esc(team.logo)}" alt="" />
      <div>
        <strong>${esc(team.name)}</strong>
        <div class="meta">${esc(team.division)} · ${esc(team.record)} · ${esc(signed(team.diff))} · No. ${esc(team.seed)} seed</div>
      </div>
    </a>
  `).join("");
}

function trendCard(team) {
  const direction = team.formDirection || "flat";
  return `<a class="trend-team ${esc(direction)}" href="${teamHref(team.abbr)}">
    <img src="${esc(team.logo)}" alt="" />
    <div>
      <strong>${esc(team.name)}</strong>
      <div class="meta">${esc(team.record)} · last 3 ${esc(team.formRecord || "—")} · ${esc(team.streak || "—")}</div>
    </div>
    <div class="delta">${esc(signed(team.formDiff))} ${trendBadge(direction)}</div>
  </a>`;
}

function renderTrending(data) {
  $("trendingBlurb").textContent = data.trendingBlurb || "";
  const trending = data.trending || {};
  $("trendUp").innerHTML = (trending.up || []).map(trendCard).join("")
    || `<p class="meta">Form shows up after teams play.</p>`;
  $("trendDown").innerHTML = (trending.down || []).map(trendCard).join("")
    || `<p class="meta">Form shows up after teams play.</p>`;
}

function gameCard(game) {
  const side = (entry) => {
    const classes = [
      "side-line",
      entry.winner ? "winner" : "",
      game.completed && entry.winner === false ? "loser" : "",
    ].filter(Boolean).join(" ");
    const right = game.completed || game.live
      ? (entry.score ?? "")
      : (entry.record || "");
    return `<a class="${classes}" href="${teamHref(entry.abbr)}">
      <img src="${esc(entry.logo)}" alt="" />
      <span>${esc(entry.abbr)}</span>
      <span class="pts">${esc(right)}</span>
    </a>`;
  };
  const extra = [
    game.completed || game.live ? "" : game.broadcast,
    game.venue,
  ].filter(Boolean).join(" · ");
  return `<article class="game-card${game.live ? " live" : ""}">
    <div class="when">${esc(game.status || "")}</div>
    ${side(game.away || {})}
    ${side(game.home || {})}
    ${extra ? `<div class="venue">${esc(extra)}</div>` : ""}
  </article>`;
}

function renderWeek(data) {
  $("weekBlurb").textContent = data.weekBlurb || "";
  const games = data.thisWeek || [];
  $("weekGames").innerHTML = games.length
    ? games.map(gameCard).join("")
    : `<p class="meta">The slate for this week is not posted yet.</p>`;
  const byes = data.byes || [];
  $("byes").innerHTML = byes.length
    ? `<span class="pill ghost">Bye</span>${byes.map((team) => `
        <a class="bye-team" href="${teamHref(team.abbr)}"><img src="${esc(team.logo)}" alt="" />${esc(team.abbr)}</a>
      `).join("")}`
    : "";
}

function renderLast(data) {
  $("lastBlurb").textContent = data.lastBlurb || "";
  const games = data.lastWeek || [];
  $("lastGames").innerHTML = games.length
    ? games.map(gameCard).join("")
    : `<p class="meta">Scores from last week will show up after the first Sunday.</p>`;
}

async function boot() {
  try {
    const res = await fetch(`data/league.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load league.json");
    const data = await res.json();
    renderTicker(data);
    renderHero(data);
    renderClubs(data);
    renderRankings(data);
    renderPicture(data);
    renderLeaders(data);
    renderTrending(data);
    renderWeek(data);
    renderLast(data);
    bindTermTips();
  } catch (err) {
    const headline = $("headline");
    if (headline) headline.textContent = "The board needs a data refresh";
    const blurb = $("blurb");
    if (blurb) blurb.textContent = "Run scripts/fetch_playoff_data.py, then reload this page.";
    console.error(err);
  }
}

boot();
