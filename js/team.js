let FOCUS = (window.TEAM_PAGE && window.TEAM_PAGE.abbr) || "MIA";

function focusOf(data) {
  return data.focus || {};
}

function renderChrome(data) {
  const focus = focusOf(data);
  const headings = data.headings || {};
  if (focus.name) document.title = `The Push | ${focus.name} Playoff Dashboard`;
  const logo = document.querySelector(".brand-logo");
  if (logo && focus.logo) {
    logo.src = focus.logo;
    logo.alt = focus.name || "";
  }
  const icon = document.querySelector("link[rel='icon']");
  if (icon && focus.logo) icon.href = focus.logo;
  const eyebrow = document.querySelector(".eyebrow");
  if (eyebrow && focus.name) eyebrow.textContent = focus.name;
  const rules = $("rules");
  if (rules) {
    rules.innerHTML = (data.rules || []).map((rule) => `<span class="pill ghost">${esc(rule)}</span>`).join("");
  }
  const text = {
    divisionTitle: headings.division,
    leadersTitle: headings.leaders,
    leadersBlurb: headings.leadersBlurb,
    pathsBlurb: headings.pathsBlurb,
    legendTeam: headings.legendTeam,
    footerLine: headings.footer,
    footerTiny: headings.footerTiny,
    conclusionLede: headings.conclusion,
    injuryBlurb: headings.injuryBlurb,
    rootingBlurb: headings.rootingBlurb,
  };
  Object.entries(text).forEach(([id, value]) => {
    const el = $(id);
    if (el && value) el.textContent = value;
  });
}

function renderTicker(data) {
  const line = (data.ticker || []).join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderConclusion(data) {
  const out = Boolean(data.eliminated);
  document.body.classList.toggle("season-over", out);
  const banner = $("conclusion");
  if (banner) banner.hidden = !out;
  const lede = $("conclusionLede");
  const headings = data.headings || {};
  if (lede && headings.conclusion) lede.textContent = headings.conclusion;
}

function renderHero(data) {
  const narrative = data.narrative || {};
  const meters = data.meters || {};
  const primary = meters.primary || {};
  const third = meters.third || {};
  const odds = data.playoffOdds || {};
  const focus = focusOf(data);
  $("statusKicker").textContent = narrative.kicker || "";
  $("headline").textContent = narrative.headline || "";
  $("blurb").textContent = narrative.blurb || "";
  $("primaryLabel").textContent = primary.label || "Games back of the cut line";
  $("primaryGiant").textContent = primary.value ?? "—";
  $("primarySub").textContent = primary.sub || "";
  const heat = primary.heat ?? 0;
  $("heatName").textContent = primary.heatLabel || "Season left";
  $("heatValue").textContent = primary.heatText || `${heat}`;
  $("heatFill").style.width = `${Math.max(0, Math.min(100, heat))}%`;
  $("heroChips").innerHTML = (data.chips || [])
    .map((chip) => `<div class="chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></div>`)
    .join("");
  const pct = odds.percent;
  $("oddsGiant").textContent = fmtOdds(pct);
  $("oddsLine").textContent = odds.sims
    ? `${Number(odds.sims).toLocaleString("en-US")} sims · ${data.seasonGames || 17}-game season`
    : "";
  $("oddsNote").textContent = odds.note || "";
  const oddsCard = document.querySelector(".hero-score.odds");
  if (oddsCard) {
    oddsCard.classList.remove("longshot", "toss-up", "live");
    if (pct == null) {
      /* waiting on the simulation */
    } else if (pct < 25) {
      oddsCard.classList.add("longshot");
    } else if (pct < 45) {
      oddsCard.classList.add("toss-up");
    } else {
      oddsCard.classList.add("live");
    }
  }
  $("magicLabel").textContent = third.label || "Magic number";
  $("magicGiant").textContent = third.value ?? "—";
  $("magicLine").textContent = third.sub || "";
  $("magicNote").textContent = third.note || "";
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = data.eliminated
    ? `${data.season} season over`
    : `${data.season} ${focus.conference || ""}`.trim();
  if (data.legend) {
    $("legendIn").textContent = data.legend.in || "In a playoff spot";
    $("legendOut").textContent = data.legend.out || "Chasing";
  }
}

function renderKpis(data) {
  $("kpis").innerHTML = (data.kpis || []).map((kpi) => `
    <article class="kpi">
      <div class="label">${kpi.stat ? term(kpi.stat, kpi.label) : esc(kpi.label)}</div>
      <div class="value">${esc(kpi.value)}</div>
      <div class="hint">${esc(kpi.hint || "")}</div>
    </article>
  `).join("");
}

function renderTrends(data) {
  $("trends").innerHTML = (data.trends || []).map((card) => `
    <article class="trend-card ${esc(card.direction || "flat")}">
      <div class="label">${card.stat ? term(card.stat, card.label) : esc(card.label)}</div>
      <div class="value">${esc(card.value)} ${trendBadge(card.direction)}</div>
      <div class="hint">${esc(card.detail || "")}</div>
    </article>
  `).join("");
}

function renderPaths(data) {
  $("paths").innerHTML = ["division", "wildcard"].map((key) => {
    const path = (data.paths || {})[key] || {};
    return `<article class="path-card${path.in ? " in-path" : ""}">
      <h4>${esc(path.title || "")}</h4>
      <div class="path-num">${esc(path.value || "—")}</div>
      <p class="meta">${esc(path.detail || "")}</p>
    </article>`;
  }).join("");
}

function renderConference(data) {
  $("tableBlurb").textContent = data.tableBlurb || "";
  const head = [
    "#", "Team", term("Path", "Path"), term("W-L", "W-L"), term("PCT", "Pct"),
    term("PF", "PF"), term("PA", "PA"), term("DIFF", "Diff"), term("DIV", "Div"),
    term("STRK", "Strk"), term("GB", "GB"),
  ];
  document.querySelector("#conferenceTable thead").innerHTML = headerRow(head);
  document.querySelector("#conferenceTable tbody").innerHTML = (data.conference || []).map((team) => {
    const classes = [
      team.inField ? "row-in" : "",
      team.isFocus ? "row-jays" : "",
      team.isCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.isCut ? `<div class="cut-note">Last berth</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}${team.isFocus ? " ★" : ""}</td>
      <td>${esc(team.path)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(fmtPct(team.pct))}</td>
      <td>${esc(team.pf)}</td>
      <td>${esc(team.pa)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.divisionRecord || "—")}</td>
      <td>${esc(team.streak || "—")}</td>
      <td>${esc(team.gb ?? "—")}</td>
    </tr>`;
  }).join("");
}

function renderDivision(data) {
  const focus = focusOf(data);
  const head = [
    "#", "Team", term("W-L", "W-L"), term("GB", "GB"), term("DIV", "Div"),
    "Home", "Road", term("DIFF", "Diff"), term("GR", "GR"),
  ];
  document.querySelector("#eastTable thead").innerHTML = headerRow(head);
  document.querySelector("#eastTable tbody").innerHTML = (data.divisionTable || []).map((team) => {
    const classes = [
      team.seed <= 4 ? "row-in" : "",
      team.isFocus ? "row-jays" : "",
      team.divisionCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.divisionCut ? `<div class="cut-note">${esc(focus.divisionShort || "Division")} lead</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(team.gb ?? "—")}</td>
      <td>${esc(team.divisionRecord || "—")}</td>
      <td>${esc(team.home || "—")}</td>
      <td>${esc(team.road || "—")}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.gr ?? "—")}</td>
    </tr>`;
  }).join("");
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

function metricMax(rows, getter) {
  return Math.max(...rows.map((row) => getter(row)), 0.0001);
}

function compareBlock(rows, block) {
  const max = metricMax(rows, block.get);
  const sorted = [...rows].sort((a, b) => block.get(b) - block.get(a));
  const body = sorted.map((team) => {
    const width = Math.max(8, Math.min(100, Math.round((block.get(team) / max) * 100)));
    return `<div class="compare-row">
      <a class="who" href="${teamHref(team.abbr)}"><img src="${esc(team.logo)}" alt="" />${esc(team.abbr)}</a>
      <div class="bar ${team.abbr === FOCUS ? "jays" : ""}"><span style="width:${width}%"></span></div>
      <b>${esc(block.format(team))}</b>
    </div>`;
  }).join("");
  return `<div class="compare-block"><header>${block.title}</header>${body}</div>`;
}

function renderCompare(data) {
  $("compareTitle").textContent = data.compareTitle || (focusOf(data).division || "Division");
  const rows = data.compare || [];
  const columns = [
    {
      heading: "The standings",
      blocks: [
        { title: "Wins", get: (team) => team.wins || 0, format: (team) => team.wins },
        { title: term("DIFF", "Point diff"), get: (team) => (Number(team.diff) || 0) + 80, format: (team) => signed(team.diff) },
        { title: term("PPG", "Points / game"), get: (team) => Number(team.ppg) || 0, format: (team) => oneDecimal(team.ppg) },
      ],
    },
    {
      heading: "The football",
      blocks: [
        { title: "Points allowed", get: (team) => Math.max(0, 60 - (Number(team.papg) || 0)), format: (team) => oneDecimal(team.papg) },
        { title: term("YPG", "Yards / game"), get: (team) => Number(team.ypg) || 0, format: (team) => oneDecimal(team.ypg) },
        { title: term("TO", "Turnover margin"), get: (team) => (Number(team.to) || 0) + 12, format: (team) => signed(team.to) },
      ],
    },
  ];
  $("compare").innerHTML = columns.map((col) => `
    <div class="compare-col">
      <h4>${esc(col.heading)}</h4>
      ${col.blocks.map((block) => compareBlock(rows, block)).join("")}
    </div>
  `).join("");
}

function renderSchedule(data) {
  const focus = focusOf(data);
  const nick = focus.nickname || focus.abbr || "Team";
  const other = focus.conference === "NFC" ? "AFC" : "NFC";
  const left = data.remaining || {};
  const sos = left.sos == null ? "—" : fmtPct(left.sos);
  const bye = left.bye ? ` · bye in week ${left.bye}` : "";
  $("gauntletBlurb").textContent =
    `${left.games || 0} games left · ${left.home || 0} home · ${left.away || 0} road · ` +
    `${left.division || 0} against the ${focus.division || "division"}${bye} · opponent win rate ${sos}.`;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  $("tickets").innerHTML = (data.schedule || []).map((game) => {
    if (game.bye) {
      return `<article class="ticket">
        <div class="when">Week ${esc(game.week)}</div>
        <h4>Bye</h4>
        <div class="pitch">No game. The week off does not move the standings.</div>
        <div class="venue">Open date</div>
      </article>`;
    }
    const opp = game.opponent || {};
    const gameDay = game.date ? new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    }).format(new Date(game.date)) : "";
    const isToday = gameDay === today;
    const bucket = game.divisionGame ? (focus.division || "Division") : (game.conferenceGame ? (focus.conference || "") : other);
    const tags = [
      game.week ? `Week ${game.week}` : "",
      bucket,
      opp.record || "",
      opp.pct != null ? `Opp ${fmtPct(opp.pct)}` : "",
    ].filter(Boolean).join(" · ");
    const score = game.final
      ? `${game.result || ""} ${game.usScore}–${game.themScore}`
      : [game.venue, game.broadcast].filter(Boolean).join(" · ");
    const odds = game.final || game.winPct == null
      ? ""
      : `<div class="ticket-odds"><div class="split-odds">${esc(nick)} ${esc(game.winPct)}%</div></div>`;
    const live = game.live ? `<div class="live">${esc(game.detail || "Live")}</div>` : "";
    const oppLink = opp.abbr
      ? `<a href="${teamHref(opp.abbr)}">${esc(opp.abbr)}</a>`
      : "TBD";
    return `<article class="ticket${isToday ? " today" : ""}">
      <div class="when">${esc(fmtDate(game.date, true))}</div>
      <h4>${game.isHome ? "vs" : "@"} ${oppLink}</h4>
      <div class="pitch">${esc(tags)}</div>
      ${live}
      ${odds}
      <div class="venue">${esc(score || "")}</div>
    </article>`;
  }).join("");
}

function renderRooting(data) {
  const games = data.rooting || [];
  $("rooting").innerHTML = games.length
    ? games.map((game) => `
      <article class="root-card">
        <div class="root-head">
          <span class="tag ${esc(game.tagClass || "race")}">${esc(game.interest || "Game")}</span>
        </div>
        <strong><a href="${teamHref(game.awayAbbr)}">${esc(game.awayAbbr)}</a> @ <a href="${teamHref(game.homeAbbr)}">${esc(game.homeAbbr)}</a></strong>
        <div class="meta">${esc(fmtDate(game.date, true))}</div>
        <div class="score">${esc(game.awayAbbr)} ${esc(game.awayWinPct)}% · ${esc(game.homeAbbr)} ${esc(game.homeWinPct)}%</div>
        <p>${esc(game.note || "")}</p>
      </article>
    `).join("")
    : `<p class="meta">No games in the next couple of weeks change the picture.</p>`;
}

function renderResults(data) {
  $("recentBlurb").textContent = data.recentBlurb || "";
  const games = data.recent || [];
  if (!games.length) {
    $("results").innerHTML = `<li><span></span><span>Regular-season results land here after opening week.</span><strong></strong></li>`;
    return;
  }
  $("results").innerHTML = games.slice().reverse().map((game) => {
    const opp = game.opponent || {};
    const mark = game.result || "•";
    const who = opp.abbr
      ? `<a href="${teamHref(opp.abbr)}">${esc(opp.abbr)}</a>`
      : "";
    return `<li>
      <span class="badge ${esc(mark)}">${esc(mark)}</span>
      <span>${game.isHome ? "vs" : "@"} ${who} · ${esc(fmtDate(game.date))}</span>
      <strong>${esc(game.usScore)}–${esc(game.themScore)}</strong>
    </li>`;
  }).join("");
}

function renderTiebreak(data) {
  const box = data.tiebreak || {};
  const focus = focusOf(data);
  $("tiebreak").innerHTML = `
    <div class="kpis" style="margin:0">
      <article class="kpi"><div class="label">${term("DIV", "Division")}</div><div class="value">${esc(box.division ?? "—")}</div><div class="hint">${esc(focus.division || "Division")} games</div></article>
      <article class="kpi"><div class="label">${term("CONF", "Conference")}</div><div class="value">${esc(box.conference ?? "—")}</div><div class="hint">All ${esc(focus.conference || "")} games</div></article>
      <article class="kpi"><div class="label">${term("DIFF", "Point diff")}</div><div class="value">${esc(box.diff ?? "—")}</div><div class="hint">Later in the tiebreaker list</div></article>
      <article class="kpi"><div class="label">Elim #</div><div class="value">${esc(box.elimination ?? "—")}</div><div class="hint">vs ${esc(box.elimRival || "the leader")} on wins</div></article>
    </div>
    <p class="lede">${esc(box.headToHead || "")}</p>
    <p class="lede">${esc(box.detail || "")}</p>
  `;
}

function playerCard(player) {
  const who = [player.position, player.jersey ? `#${player.jersey}` : ""].filter(Boolean).join(" · ");
  return `<article class="player">
    <img src="${esc(player.headshot)}" alt="" onerror="this.style.opacity='0.25'" />
    <div>
      <strong>${esc(player.name)}</strong>
      <div class="meta">${esc(who)}${player.line ? ` · ${esc(player.line)}` : ""}</div>
    </div>
    <div class="statline"><span class="statline-value">${esc(player.value ?? "—")}</span><span class="statline-label">${player.statLabel ? term(player.statLabel, player.statLabel) : ""}</span></div>
  </article>`;
}

function renderPlayers(data) {
  const players = data.players || {};
  const note = players.label || "";
  if (note) $("qbBlurb").textContent = note;
  const qb = players.quarterback || [];
  const skill = players.skill || [];
  const defense = players.defense || [];
  $("quarterback").innerHTML = qb.map(playerCard).join("")
    || `<p class="meta">Quarterback numbers show up once the season feed posts them.</p>`;
  $("skill").innerHTML = skill.map(playerCard).join("")
    || `<p class="meta">Skill-player yards will land here after the next refresh.</p>`;
  $("defense").innerHTML = defense.map(playerCard).join("")
    || `<p class="meta">Defensive counting stats will land here after the next refresh.</p>`;
}

function renderInjuries(data) {
  const rows = data.injuries || [];
  const nick = focusOf(data).nickname || "this club";
  $("injuryMeta").innerHTML = `<span class="pill ghost">${rows.length} listed</span>`;
  $("injuries").innerHTML = rows.length
    ? rows.map((injury) => `
      <article class="injury">
        <span class="status">${esc(injury.status || "Out")}</span>
        <strong>${esc(injury.name)}${injury.position ? ` · ${esc(injury.position)}` : ""}</strong>
        ${injury.detail ? `<p>${esc(injury.detail)}</p>` : ""}
      </article>
    `).join("")
    : `<p class="meta">Nobody on the ${esc(nick)} roster is currently flagged injured or on IR.</p>`;
}

async function boot() {
  const page = window.TEAM_PAGE || {};
  const slug = String(page.abbr || FOCUS).toLowerCase();
  try {
    const res = await fetch(`${assetRoot()}data/teams/${slug}.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load team data");
    const data = await res.json();
    FOCUS = data.team || page.abbr || FOCUS;
    renderChrome(data);
    renderTicker(data);
    renderConclusion(data);
    renderHero(data);
    renderKpis(data);
    renderTrends(data);
    renderPaths(data);
    renderConference(data);
    renderDivision(data);
    renderLeaders(data);
    renderCompare(data);
    renderSchedule(data);
    renderRooting(data);
    renderResults(data);
    renderTiebreak(data);
    renderInjuries(data);
    renderPlayers(data);
    bindTermTips();
  } catch (err) {
    const headline = $("headline");
    if (headline) headline.textContent = "Dashboard needs a data refresh";
    const blurb = $("blurb");
    if (blurb) blurb.textContent = "Run scripts/fetch_playoff_data.py, then reload this page.";
    console.error(err);
  }
}

boot();
