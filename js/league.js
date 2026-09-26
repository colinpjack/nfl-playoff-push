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

const MY_TEAMS_KEY = "push-my-teams";
let leagueData = null;
let myTeamsEditing = false;
let trackedMemory = null;

function trackedTeams() {
  if (trackedMemory) return trackedMemory.slice();
  let saved = [];
  try {
    saved = JSON.parse(localStorage.getItem(MY_TEAMS_KEY) || "[]");
  } catch (err) {
    saved = [];
  }
  if (!Array.isArray(saved)) saved = [];
  const abbrs = [0, 1, 2].map((index) => String(saved[index] || "").toUpperCase());
  const seen = new Set();
  return abbrs.map((abbr) => {
    if (!abbr || seen.has(abbr)) return "";
    seen.add(abbr);
    return abbr;
  });
}

function setTracked(abbrs) {
  const seen = new Set();
  const next = [0, 1, 2].map((index) => {
    const abbr = String(abbrs[index] || "").toUpperCase();
    if (!abbr || seen.has(abbr)) return "";
    seen.add(abbr);
    return abbr;
  });
  trackedMemory = next;
  try {
    localStorage.setItem(MY_TEAMS_KEY, JSON.stringify(next));
  } catch (err) {
    /* Private browsing can block storage; the in-memory list still works this visit. */
  }
  return next;
}

function magicFor(team, rows) {
  const rivals = rows.filter((row) => row.division === team.division && row.abbr !== team.abbr);
  if (!rivals.length) return { value: "—", title: "Division rivals are not on the board yet.", kind: "" };
  let best = null;
  rivals.forEach((rival) => {
    const value = 18 - Number(team.wins) - Number(rival.losses);
    if (!best || value > best.value) best = { value, rival };
  });
  const clubMax = Number(team.wins) + Number(team.gr || 0);
  const clear = rows.filter((row) => (
    row.conference === team.conference && row.abbr !== team.abbr && Number(row.wins) > clubMax
  )).length;
  if (clear >= 7) {
    return { value: "OUT", title: "Cannot catch seven clubs already ahead.", kind: "out" };
  }
  if (best.value <= 0) {
    return { value: "IN", title: `${team.division} clinched on wins.`, kind: "in" };
  }
  return {
    value: String(best.value),
    title: `${team.abbr} wins plus ${best.rival.abbr} losses to win the ${team.division}.`,
    kind: "",
  };
}

function slateFor(abbr, data) {
  const game = (data.thisWeek || []).find((item) => item.home?.abbr === abbr || item.away?.abbr === abbr);
  if (!game) {
    const bye = (data.byes || []).some((team) => team.abbr === abbr);
    return bye
      ? { label: "Bye", title: "No game this week." }
      : { label: "—", title: "This week's matchup is not posted." };
  }
  const home = game.home?.abbr === abbr;
  const opp = home ? game.away : game.home;
  const where = home ? "vs" : "@";
  const label = `${where} ${opp?.abbr || ""}`;
  if (game.completed || game.live) {
    const us = home ? game.home?.score : game.away?.score;
    const them = home ? game.away?.score : game.home?.score;
    return { label, title: `${game.status || ""} ${us}–${them}`.trim() };
  }
  return { label, title: [game.status, game.broadcast].filter(Boolean).join(" · ") };
}

function teamSelect(rows, tracked, slot) {
  const taken = new Set(tracked.filter((abbr, index) => abbr && index !== slot));
  const ordered = rows.slice().sort((a, b) => a.division.localeCompare(b.division) || a.name.localeCompare(b.name));
  const groups = [];
  ordered.forEach((team) => {
    const last = groups[groups.length - 1];
    if (!last || last.name !== team.division) groups.push({ name: team.division, teams: [team] });
    else last.teams.push(team);
  });
  const options = groups.map((group) => {
    const items = group.teams.map((team) => {
      const disabled = taken.has(team.abbr) ? " disabled" : "";
      const selected = team.abbr === tracked[slot] ? " selected" : "";
      return `<option value="${esc(team.abbr)}"${selected}${disabled}>${esc(team.name)}</option>`;
    }).join("");
    return `<optgroup label="${esc(group.name)}">${items}</optgroup>`;
  }).join("");
  return `<label class="mine-pick">${slot + 1}
    <select data-slot="${slot}" aria-label="Team ${slot + 1}">
      <option value="">Choose a team</option>
      ${options}
    </select>
  </label>`;
}

function renderMyTeams(data) {
  if (!data) return;
  leagueData = data;
  const rows = data.powerRankings || [];
  const byAbbr = Object.fromEntries(rows.map((team) => [team.abbr, team]));
  const tracked = trackedTeams().map((abbr) => (byAbbr[abbr] ? abbr : ""));
  const hasAny = tracked.some(Boolean);
  const editing = myTeamsEditing || !hasAny;
  const button = $("myTeamsEdit");
  if (button) {
    button.hidden = !hasAny;
    button.textContent = editing ? "Done" : "Edit";
    button.setAttribute("aria-expanded", editing ? "true" : "false");
  }
  const body = $("myTeamsBody");
  if (!body) return;
  if (editing) {
    body.innerHTML = `<div class="mine-picks">
      ${[0, 1, 2].map((slot) => teamSelect(rows, tracked, slot)).join("")}
      <p class="mine-note">Pick up to three. Saved on this browser.</p>
    </div>`;
    return;
  }
  const cards = tracked.map((abbr, slot) => {
    if (!abbr) {
      return `<button type="button" class="mine-empty" data-slot="${slot}">Pick a team</button>`;
    }
    const team = byAbbr[abbr];
    const direction = team.formDirection || "flat";
    const trend = signed(team.formDiff);
    const slate = slateFor(abbr, data);
    const magic = magicFor(team, rows);
    const summary = `${team.name}, power rank ${team.rank}, trend ${trend} over the last three games, ${slate.label}, magic number ${magic.value}.`;
    return `<a class="mine-row" href="${teamHref(abbr)}" aria-label="${esc(summary)}">
      <img src="${esc(team.logo)}" alt="" />
      <span class="mine-abbr">${esc(abbr)}</span>
      <span class="mine-rank">${esc(team.rank)}</span>
      <span class="mine-trend ${esc(direction)}" title="Point differential over the last three games">${esc(trend)}</span>
      <span class="mine-week" title="${esc(slate.title)}">${esc(slate.label)}</span>
      <span class="mine-magic ${esc(magic.kind)}" title="${esc(magic.title)}">${esc(magic.value)}</span>
    </a>`;
  }).join("");
  body.innerHTML = `<div class="mine-cols" aria-hidden="true"><span></span><span></span><span>Rank</span><span>Trend</span><span>Week</span><span>Magic</span></div>${cards}`;
}

function wireMyTeams() {
  const root = $("myTeams");
  if (!root || root.dataset.wired) return;
  root.dataset.wired = "1";
  root.addEventListener("click", (event) => {
    const edit = event.target.closest("#myTeamsEdit");
    if (edit) {
      myTeamsEditing = edit.textContent !== "Done";
      renderMyTeams(leagueData);
      if (myTeamsEditing) {
        const select = root.querySelector("select");
        if (select) select.focus();
      }
      return;
    }
    const empty = event.target.closest(".mine-empty");
    if (!empty) return;
    myTeamsEditing = true;
    renderMyTeams(leagueData);
    const select = root.querySelector(`select[data-slot="${empty.dataset.slot}"]`);
    if (select) select.focus();
  });
  root.addEventListener("change", (event) => {
    const select = event.target.closest("select[data-slot]");
    if (!select) return;
    const next = trackedTeams();
    next[Number(select.dataset.slot)] = select.value;
    myTeamsEditing = true;
    setTracked(next);
    renderMyTeams(leagueData);
    const fresh = root.querySelector(`select[data-slot="${select.dataset.slot}"]`);
    if (fresh) fresh.focus();
  });
}

async function boot() {
  try {
    const res = await fetch(`data/league.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load league.json");
    const data = await res.json();
    renderTicker(data);
    renderHero(data);
    renderMyTeams(data);
    wireMyTeams();
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
