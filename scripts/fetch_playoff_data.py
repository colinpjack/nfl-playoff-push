#!/usr/bin/env python3
"""Fetch NFL playoff-race data and write the league board plus one file per team."""

from __future__ import annotations

import json
import random
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
USER_AGENT = "NFLPlayoffPush/1.0 (+github-pages refresh)"
ROOT = Path(__file__).resolve().parents[1]
SEASON_GAMES = 17
SIMS = 5000
PYTH_EXP = 2.37
PRIOR_POINTS = 88  # about four games of league-average scoring
HOME_BUMP = 0.03

DIVISIONS = {
    "AFC East": ["BUF", "MIA", "NE", "NYJ"],
    "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West": ["DEN", "KC", "LV", "LAC"],
    "NFC East": ["DAL", "NYG", "PHI", "WSH"],
    "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"],
    "NFC West": ["ARI", "LAR", "SF", "SEA"],
}
ABBR_DIV = {abbr: name for name, members in DIVISIONS.items() for abbr in members}

_PREFER_CURL = False


def now_et() -> datetime:
    return datetime.now(TZ)


def fetch_json(url: str, retries: int = 3) -> dict:
    global _PREFER_CURL
    last_err: Exception | None = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if not _PREFER_CURL:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                    return json.load(resp)
            except Exception as err:
                last_err = err
                time.sleep(0.35 * (attempt + 1))
        _PREFER_CURL = True
    for attempt in range(retries):
        try:
            completed = subprocess.run(
                ["curl", "-fsSL", "-A", USER_AGENT, "--max-time", "45", url],
                check=True,
                capture_output=True,
                text=True,
                timeout=50,
            )
            return json.loads(completed.stdout)
        except Exception as err:
            last_err = err
            time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}") from last_err


def logo_of(team: dict) -> str:
    logos = team.get("logos") or []
    for logo in logos:
        href = logo.get("href") or ""
        if "/500/" in href:
            return href
    if logos:
        return logos[0].get("href") or ""
    return ""


def stat_index(stats: list) -> dict:
    indexed = {}
    for stat in stats or []:
        indexed[stat.get("name")] = {
            "value": stat.get("value"),
            "display": stat.get("displayValue"),
        }
    return indexed


def as_number(stat: dict | None, default: float = 0) -> float:
    if not stat:
        return default
    value = stat.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(stat.get("display") or "").replace("+", "").replace(",", "").strip()
    if text in {"", "-", "—"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def as_int(stat: dict | None, default: int = 0) -> int:
    return int(round(as_number(stat, default)))


def split_record(text: str | None) -> tuple[int, int, int]:
    parts: list[int] = []
    for piece in str(text or "0-0").split("-"):
        piece = piece.strip()
        if not piece:
            continue
        try:
            parts.append(int(float(piece)))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def record_text(wins: int, losses: int, ties: int = 0) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def signed(value: float | int | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    if abs(number - round(number)) < 0.05:
        number = int(round(number))
        return f"+{number}" if number > 0 else str(number)
    text = f"{number:.1f}"
    return f"+{text}" if number > 0 else text


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    text = f"{value:.3f}"
    return text[1:] if text.startswith("0") else text


def fmt_gb(value: float) -> str:
    if abs(value) < 0.05:
        return "—"
    mag = abs(value)
    text = str(int(round(mag))) if abs(mag - round(mag)) < 0.05 else f"{mag:.1f}"
    return f"+{text}" if value < 0 else text


def gb_words(value: float) -> str:
    mag = abs(value)
    if mag < 0.05:
        return "even"
    key = round(mag * 2) / 2
    labels = {
        0.5: "a half-game",
        1.0: "one game",
        1.5: "a game and a half",
        2.0: "two games",
        2.5: "two and a half games",
        3.0: "three games",
        4.0: "four games",
    }
    return labels.get(key, f"{mag:g} games")


def games_back(team: dict, pivot: dict) -> float:
    if team["abbr"] == pivot["abbr"]:
        return 0.0
    return ((pivot["wins"] - team["wins"]) + (team["losses"] - pivot["losses"])) / 2.0


def win_rate(team: dict) -> float:
    played = team["wins"] + team["losses"] + team["ties"]
    if played <= 0:
        return 0.5
    return (team["wins"] + 0.5 * team["ties"]) / played


def model_wp(points_for: float, points_against: float) -> float:
    scored = max(points_for, 0) + PRIOR_POINTS
    allowed = max(points_against, 0) + PRIOR_POINTS
    top = scored ** PYTH_EXP
    bottom = allowed ** PYTH_EXP
    if top + bottom == 0:
        return 0.5
    return top / (top + bottom)


def win_prob(home_wp: float, away_wp: float, neutral: bool = False) -> float:
    bump = 0.0 if neutral else HOME_BUMP
    probability = 0.5 + (home_wp - away_wp) * 0.9 + bump
    return min(0.88, max(0.12, probability))


def categories_of(side) -> list:
    if isinstance(side, dict):
        return side.get("categories") or []
    if isinstance(side, list) and side and isinstance(side[0], dict) and "stats" in side[0]:
        return side
    return []


def index_categories(categories: list) -> dict:
    indexed = {}
    for category in categories:
        bucket = {}
        for stat in category.get("stats") or []:
            bucket[stat.get("name")] = stat.get("value", stat.get("displayValue"))
            bucket[f"{stat.get('name')}__display"] = stat.get("displayValue")
        indexed[category.get("name")] = bucket
    return indexed


def num_from(bucket: dict, key: str, default=None):
    if key not in bucket or bucket[key] is None:
        return default
    value = bucket[key]
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("+", "").replace("%", "").replace(",", "").strip()
    if text in {"", "-", "—"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_team(entry: dict, conference: str) -> dict:
    raw = entry["team"]
    stats = stat_index(entry.get("stats"))
    wins = as_int(stats.get("wins"))
    losses = as_int(stats.get("losses"))
    ties = as_int(stats.get("ties"))
    points_for = as_int(stats.get("pointsFor"))
    points_against = as_int(stats.get("pointsAgainst"))
    diff = as_int(stats.get("pointDifferential"))
    div_w, div_l, div_t = split_record((stats.get("divisionRecord") or {}).get("display"))
    conf_w, conf_l, conf_t = split_record((stats.get("vs. Conf.") or {}).get("display"))
    abbr = raw.get("abbreviation") or ""
    division = ABBR_DIV.get(abbr, "Other")
    played = wins + losses + ties
    return {
        "abbr": abbr,
        "id": str(raw.get("id") or ""),
        "name": raw.get("displayName") or abbr,
        "nickname": raw.get("name") or raw.get("shortDisplayName") or abbr,
        "logo": logo_of(raw),
        "conference": conference,
        "division": division,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "gp": played,
        "pf": points_for,
        "pa": points_against,
        "diff": diff,
        "seed": as_int(stats.get("playoffSeed"), 99),
        "streak": (stats.get("streak") or {}).get("display") or "—",
        "divisionRecord": (stats.get("divisionRecord") or {}).get("display") or record_text(div_w, div_l, div_t),
        "conferenceRecord": (stats.get("vs. Conf.") or {}).get("display") or record_text(conf_w, conf_l, conf_t),
        "home": (stats.get("Home") or {}).get("display") or "—",
        "road": (stats.get("Road") or {}).get("display") or "—",
        "divWins": div_w,
        "confWins": conf_w,
        "wp": model_wp(points_for, points_against),
        "pct": win_rate({
            "wins": wins,
            "losses": losses,
            "ties": ties,
        }),
    }


def broadcast_names(comp: dict) -> str:
    names: list[str] = []
    for item in comp.get("broadcasts") or []:
        media = item.get("media") or {}
        candidates = list(item.get("names") or [])
        if media.get("shortName"):
            candidates.append(media["shortName"])
        for name in candidates:
            if name and name not in names:
                names.append(name)
    return ", ".join(names[:2])


def parse_schedule(payload: dict) -> tuple[list[dict], int | None]:
    games = []
    for event in payload.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        status = (comp.get("status") or {}).get("type") or {}
        sides = {}
        for competitor in comp.get("competitors") or []:
            team = competitor.get("team") or {}
            score = competitor.get("score") or {}
            sides[competitor.get("homeAway")] = {
                "abbr": team.get("abbreviation") or "",
                "name": team.get("displayName") or team.get("name") or "",
                "nickname": team.get("name") or team.get("shortDisplayName") or "",
                "score": score.get("displayValue") if isinstance(score, dict) else score,
                "logo": logo_of(team),
            }
        if "home" not in sides or "away" not in sides:
            continue
        week = event.get("week") or {}
        games.append({
            "id": str(comp.get("id") or event.get("id")),
            "date": event.get("date") or comp.get("date") or "",
            "week": week.get("number"),
            "name": event.get("shortName") or event.get("name") or "",
            "completed": bool(status.get("completed")),
            "state": status.get("state") or "",
            "detail": status.get("shortDetail") or status.get("detail") or "",
            "home": sides["home"],
            "away": sides["away"],
            "venue": (comp.get("venue") or {}).get("fullName") or "",
            "broadcast": broadcast_names(comp),
            "neutral": bool(comp.get("neutralSite")),
        })
    bye = payload.get("byeWeek")
    try:
        bye_week = int(bye) if bye else None
    except (TypeError, ValueError):
        bye_week = None
    return games, bye_week


def load_standings() -> tuple[int, dict]:
    payload = fetch_json("https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings")
    season = int((payload.get("season") or {}).get("year") or now_et().year)
    teams = {}
    for conference in payload.get("children") or []:
        conf_abbr = conference.get("abbreviation") or ""
        entries = (conference.get("standings") or {}).get("entries") or []
        for entry in entries:
            team = parse_team(entry, conf_abbr)
            if team["abbr"]:
                teams[team["abbr"]] = team
    if len(teams) < 32:
        raise RuntimeError(f"Expected 32 NFL teams, found {len(teams)}")
    return season, teams


def load_schedules(season: int, teams: dict) -> dict:
    found: dict[str, tuple[list[dict], int | None]] = {}

    def pull(abbr: str) -> tuple[str, list[dict], int | None]:
        team_id = teams[abbr]["id"]
        url = (
            "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/"
            f"teams/{team_id}/schedule?season={season}"
        )
        games, bye = parse_schedule(fetch_json(url))
        return abbr, games, bye

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(pull, abbr) for abbr in teams]
        for future in as_completed(futures):
            abbr, games, bye = future.result()
            found[abbr] = (games, bye)
    return found


def load_team_stats(team_id: str) -> dict | None:
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/statistics"
    try:
        payload = fetch_json(url)
    except Exception:
        return None
    results = payload.get("results") or {}
    own = index_categories(categories_of(results.get("stats")))
    opp = index_categories(categories_of(results.get("opponent")))
    passing = own.get("passing") or {}
    rushing = own.get("rushing") or {}
    misc = own.get("miscellaneous") or {}
    defense = own.get("defensive") or {}
    opp_pass = opp.get("passing") or {}
    opp_def = opp.get("defensive") or {}
    games = num_from(passing, "teamGamesPlayed") or num_from(rushing, "teamGamesPlayed") or 0
    sacks_for = num_from(defense, "sacks", 0) or 0
    sacks_allowed = num_from(passing, "sacks", 0)
    if sacks_allowed is None:
        sacks_allowed = num_from(opp_def, "sacks", 0) or 0
    return {
        "ypg": num_from(passing, "yardsPerGame"),
        "yapg": num_from(opp_pass, "yardsPerGame"),
        "ppg": num_from(passing, "totalPointsPerGame"),
        "papg": num_from(opp_pass, "totalPointsPerGame"),
        "third": num_from(misc, "thirdDownConvPct"),
        "thirdDisplay": (misc.get("thirdDownEff__display") if misc else None),
        "rz": num_from(misc, "redzoneTouchdownPct"),
        "to": num_from(misc, "turnOverDifferential"),
        "topSeconds": num_from(misc, "possessionTimeSeconds"),
        "sacksFor": sacks_for,
        "sacksAllowed": sacks_allowed or 0,
        "qbRating": num_from(passing, "QBRating"),
        "completion": num_from(passing, "completionPct"),
        "gp": games,
    }


def athlete_id(ref: str) -> str:
    path = (ref or "").split("?")[0].rstrip("/")
    return path.split("/")[-1] if path else ""


def roster_index(payload: dict) -> tuple[dict, list]:
    indexed = {}
    injuries = []
    for group in payload.get("athletes") or []:
        group_name = group.get("position") or ""
        for player in group.get("items") or []:
            position = (player.get("position") or {}).get("abbreviation") or ""
            headshot = (player.get("headshot") or {}).get("href") or ""
            info = {
                "id": str(player.get("id") or ""),
                "name": player.get("displayName") or player.get("fullName") or "",
                "position": position,
                "jersey": player.get("jersey") or "",
                "headshot": headshot,
            }
            if info["id"]:
                indexed[info["id"]] = info
            injury_rows = player.get("injuries") or []
            on_ir = group_name == "injuredReserveOrOut"
            if not injury_rows and not on_ir:
                continue
            status = "IR" if on_ir else ""
            comment = ""
            if injury_rows and isinstance(injury_rows[0], dict):
                item = injury_rows[0]
                status = item.get("status") or status or "Injured"
                details = item.get("details") if isinstance(item.get("details"), dict) else {}
                comment = item.get("shortComment") or item.get("longComment") or details.get("type") or ""
            injuries.append({
                "name": info["name"],
                "position": position,
                "status": status or "Out",
                "detail": comment,
            })
    return indexed, injuries


def leader_list(payload: dict, name: str) -> list:
    for category in payload.get("categories") or []:
        if category.get("name") == name:
            return category.get("leaders") or []
    return []


def pack_leader(row: dict, roster: dict, stat_label: str) -> dict:
    aid = athlete_id((row.get("athlete") or {}).get("$ref") or "")
    info = roster.get(aid, {})
    value = row.get("value")
    display_value = row.get("displayValue") or ""
    short = display_value
    if isinstance(value, (int, float)) and stat_label in {"YDS", "TKL", "INT", "SACK", "RTG"}:
        short = str(int(value)) if float(value).is_integer() else f"{float(value):.1f}"
    return {
        "id": aid,
        "name": info.get("name") or "Player",
        "position": info.get("position") or "",
        "jersey": info.get("jersey") or "",
        "headshot": info.get("headshot") or "",
        "line": display_value,
        "value": short,
        "statLabel": stat_label,
    }


def build_players(roster: dict, leaders: dict) -> dict:
    passing = leader_list(leaders, "passingLeader")
    rating_rows = {athlete_id((row.get("athlete") or {}).get("$ref") or ""): row for row in leader_list(leaders, "quarterbackRating")}
    quarterbacks = []
    qb_ids = set()
    if passing:
        qb = pack_leader(passing[0], roster, "RTG")
        rated = rating_rows.get(qb["id"])
        if rated and rated.get("value") is not None:
            qb["value"] = f"{float(rated['value']):.1f}"
            qb["statLabel"] = "RTG"
        qb["line"] = passing[0].get("displayValue") or qb["line"]
        quarterbacks.append(qb)
        qb_ids.add(qb["id"])

    skill = []
    seen = set(qb_ids)
    for row in leader_list(leaders, "rushingLeader")[:5]:
        player = pack_leader(row, roster, "YDS")
        if not player["id"] or player["id"] in seen:
            continue
        seen.add(player["id"])
        skill.append(player)
        if len(skill) == 4:
            break
    for row in leader_list(leaders, "receivingLeader")[:8]:
        player = pack_leader(row, roster, "YDS")
        if not player["id"] or player["id"] in seen:
            continue
        seen.add(player["id"])
        skill.append(player)
    skill.sort(key=lambda player: float(player["value"]) if str(player["value"]).replace(".", "", 1).isdigit() else 0, reverse=True)
    skill = skill[:8]

    defense = []
    defense_seen = {}
    for row in leader_list(leaders, "totalTackles")[:6]:
        player = pack_leader(row, roster, "TKL")
        if not player["id"]:
            continue
        defense_seen[player["id"]] = player
        defense.append(player)
    for row, label in (
        *[(item, "SACK") for item in leader_list(leaders, "sacks")[:4]],
        *[(item, "INT") for item in leader_list(leaders, "interceptions")[:4]],
    ):
        player = pack_leader(row, roster, label)
        if not player["id"]:
            continue
        if player["id"] in defense_seen:
            existing = defense_seen[player["id"]]
            extra = f"{player['value']} {label}"
            if extra not in existing["line"]:
                existing["line"] = f"{existing['line']} · {extra}" if existing["line"] else extra
            continue
        defense_seen[player["id"]] = player
        defense.append(player)
    return {
        "label": "Regular-season counting stats. Hover a label for the definition.",
        "quarterback": quarterbacks[:1],
        "skill": skill[:8],
        "defense": defense[:8],
    }


def fmt_clock(total_seconds: float | None, games: float) -> str:
    if not total_seconds or not games:
        return "—"
    per = int(round(total_seconds / games))
    return f"{per // 60}:{per % 60:02d}"


def local_dt(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return None


def fmt_when(iso: str, with_time: bool = True) -> str:
    moment = local_dt(iso)
    if not moment:
        return iso
    if with_time:
        return moment.strftime("%a, %b %-d · %-I:%M %p")
    return moment.strftime("%a, %b %-d")


def direction_for(kind: str, value: float | None) -> str:
    if value is None:
        return "flat"
    marks = {
        "diff": (0, 0),
        "margin": (0, 0),
        "third": (40, 34),
        "rz": (55, 40),
        "sack": (0, 0),
        "to": (0, 0),
        "top": (30, 28),
        "qb": (90, 80),
    }
    good, bad = marks.get(kind, (0, 0))
    if kind == "top":
        # value is minutes
        if value >= good:
            return "up"
        if value <= bad:
            return "down"
        return "flat"
    if value > good:
        return "up"
    if value < bad:
        return "down"
    return "flat"


CLUB_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WSH": "Washington Commanders",
}

# Bright colors that still read on the navy board: primary, accent, deep, powder.
THEMES = {
    "ARI": ("#97233F", "#FFB612", "#5c1024", "#ffd56a"),
    "ATL": ("#A71930", "#E6E6E6", "#6d0e1e", "#f2f2f2"),
    "BAL": ("#4d6ad1", "#C4A35A", "#241773", "#d7c48a"),
    "BUF": ("#3d7eff", "#C60C30", "#00338D", "#9ec2ff"),
    "CAR": ("#0085CA", "#B0B7BC", "#064e73", "#d5dde2"),
    "CHI": ("#E8571A", "#E6E6E6", "#0B162A", "#f0c2a8"),
    "CIN": ("#FB4F14", "#F0EDE6", "#8a2508", "#ffb199"),
    "CLE": ("#FF3C00", "#F5C518", "#311D00", "#ffb199"),
    "DAL": ("#4d8dff", "#B6BEC4", "#003594", "#d5dde2"),
    "DEN": ("#FB4F14", "#F2C14E", "#002244", "#ffb199"),
    "DET": ("#3aa0e0", "#B0B7BC", "#0076B6", "#c5e6f7"),
    "GB": ("#2f6f4e", "#FFB612", "#203731", "#ffe08a"),
    "HOU": ("#A71930", "#E6E6E6", "#03202F", "#f0b4be"),
    "IND": ("#3d6fbf", "#E6E6E6", "#002C5F", "#c5d4ee"),
    "JAX": ("#1aa3b5", "#D7A22A", "#006778", "#f0d48a"),
    "KC": ("#E31837", "#FFB81C", "#8e0e22", "#ffd56a"),
    "LV": ("#C5CED6", "#E6E6E6", "#000000", "#d5dde2"),
    "LAC": ("#0080C6", "#FFC20E", "#004e78", "#ffe08a"),
    "LAR": ("#4d8dff", "#FFA300", "#003594", "#ffd08a"),
    "MIA": ("#008E97", "#FC4C02", "#014E55", "#9EEBF0"),
    "MIN": ("#7a4ec4", "#FFC62F", "#4F2683", "#ffe08a"),
    "NE": ("#4a90d9", "#C60C30", "#002244", "#f0b4be"),
    "NO": ("#D3BC8D", "#E6E6E6", "#8a7350", "#f3ead4"),
    "NYG": ("#3d5ec9", "#C60C30", "#0B2265", "#f0b4be"),
    "NYJ": ("#1f8a68", "#E6E6E6", "#125740", "#b7e6d6"),
    "PHI": ("#0e7c86", "#C5CED6", "#004C54", "#d5dde2"),
    "PIT": ("#FFB612", "#E6E6E6", "#101820", "#ffe08a"),
    "SF": ("#E10600", "#C8B273", "#6e0000", "#e6d7a8"),
    "SEA": ("#69BE28", "#7eb6ff", "#002244", "#c6eea4"),
    "TB": ("#D50A0A", "#FF7900", "#6e0505", "#ffc08a"),
    "TEN": ("#4B92DB", "#E6E6E6", "#0C2340", "#c5ddf5"),
    "WSH": ("#8c2f2f", "#FFB612", "#5A1414", "#ffe08a"),
}

LEAGUE_PATH = ROOT / "data" / "league.json"
TEAMS_DIR = ROOT / "data" / "teams"


def division_short(name: str) -> str:
    return name.replace("AFC ", "").replace("NFC ", "")


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    red, green, blue = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def score_num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def attach_remaining(teams: dict, schedules: dict) -> None:
    for abbr, team in teams.items():
        rows, _bye = schedules.get(abbr, ([], None))
        left = [game for game in rows if not game["completed"]]
        team["gr"] = len(left) if rows else max(0, SEASON_GAMES - team["gp"])


def public_team(team: dict, **extra) -> dict:
    row = {
        "abbr": team["abbr"],
        "name": team["name"],
        "nickname": team["nickname"],
        "logo": team["logo"],
        "conference": team["conference"],
        "division": team["division"],
        "seed": team["seed"],
        "wins": team["wins"],
        "losses": team["losses"],
        "ties": team["ties"],
        "record": record_text(team["wins"], team["losses"], team["ties"]),
        "pct": round(team["pct"], 3),
        "pf": team["pf"],
        "pa": team["pa"],
        "diff": team["diff"],
        "ppg": round(team["pf"] / team["gp"], 1) if team["gp"] else None,
        "papg": round(team["pa"] / team["gp"], 1) if team["gp"] else None,
        "streak": team["streak"],
        "divisionRecord": team["divisionRecord"],
        "conferenceRecord": team["conferenceRecord"],
        "home": team["home"],
        "road": team["road"],
        "gr": team.get("gr"),
        "ypg": team.get("ypg"),
        "yapg": team.get("yapg"),
        "to": team.get("to"),
        "playoffPct": team.get("playoffPct"),
        "powerRank": team.get("powerRank"),
    }
    row.update(extra)
    return row


def path_label(team: dict) -> str:
    if team["seed"] <= 4:
        short = division_short(team["division"])
        return f"{short} champ"
    if team["seed"] <= 7:
        return "Wild card"
    return "Outside"


def apply_stats(teams: dict, stats_by_id: dict) -> None:
    for team in teams.values():
        stats = stats_by_id.get(team["id"]) or {}
        team["efficiency"] = stats or {}
        if not stats:
            continue
        if stats.get("ypg") is not None:
            team["ypg"] = round(stats["ypg"], 1)
        if stats.get("yapg") is not None:
            team["yapg"] = round(stats["yapg"], 1)
        if stats.get("to") is not None:
            team["to"] = int(round(stats["to"]))


def load_people(season: int, teams: dict) -> dict:
    found = {}

    def pull(abbr: str):
        team = teams[abbr]
        team_id = team["id"]
        empty = {
            "quarterback": [],
            "skill": [],
            "defense": [],
            "label": "Roster feed was unavailable on this refresh.",
        }
        try:
            roster_payload = fetch_json(
                "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/"
                f"teams/{team_id}/roster"
            )
            leaders_payload = fetch_json(
                "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
                f"seasons/{season}/types/2/teams/{team_id}/leaders"
            )
            roster, injuries = roster_index(roster_payload)
            return abbr, build_players(roster, leaders_payload), injuries
        except Exception as err:
            print(f"  roster {abbr} skipped: {err}", flush=True)
            return abbr, empty, []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(pull, abbr) for abbr in teams]
        for future in as_completed(futures):
            abbr, players, injuries = future.result()
            found[abbr] = {"players": players, "injuries": injuries}
    return found


def catalog_games(schedules: dict, teams: dict) -> list[dict]:
    seen = set()
    games = []
    for rows, _bye in schedules.values():
        for game in rows:
            if game["id"] in seen:
                continue
            home = game["home"]["abbr"]
            away = game["away"]["abbr"]
            if home not in teams or away not in teams:
                continue
            week = game.get("week")
            if isinstance(week, float):
                week = int(week)
            if not isinstance(week, int) or week < 1 or week > 18:
                continue
            seen.add(game["id"])
            games.append({
                "id": game["id"],
                "date": game["date"],
                "week": week,
                "home": home,
                "away": away,
                "homeScore": game["home"].get("score"),
                "awayScore": game["away"].get("score"),
                "neutral": game["neutral"],
                "sameDiv": teams[home]["division"] == teams[away]["division"] and teams[home]["division"] != "Other",
                "sameConf": teams[home]["conference"] == teams[away]["conference"],
                "p": win_prob(teams[home]["wp"], teams[away]["wp"], game["neutral"]),
                "venue": game["venue"],
                "broadcast": game["broadcast"],
                "detail": game["detail"],
                "state": game["state"],
                "completed": game["completed"],
                "name": game["name"],
            })
    games.sort(key=lambda game: (game.get("date") or "", game["id"]))
    return games


def choose_weeks(games: list[dict]) -> tuple[int, int]:
    weeks = sorted({game["week"] for game in games})
    current = None
    for week in weeks:
        slate = [game for game in games if game["week"] == week]
        if any(not game["completed"] for game in slate):
            current = week
            break
    if current is None:
        current = weeks[-1] if weeks else 1
    return current, max(current - 1, 0)


def form_for(abbr: str, rows: list[dict]) -> dict:
    done = []
    for game in rows:
        if not game["completed"]:
            continue
        home = game["home"]["abbr"]
        away = game["away"]["abbr"]
        if abbr not in (home, away):
            continue
        us = score_num(game["home"]["score"] if home == abbr else game["away"]["score"])
        them = score_num(game["away"]["score"] if home == abbr else game["home"]["score"])
        if us is None or them is None:
            continue
        done.append((game.get("date") or "", us, them))
    done.sort()
    last = done[-3:]
    wins = losses = ties = 0
    diff = 0.0
    for _date, us, them in last:
        diff += us - them
        if us > them:
            wins += 1
        elif us < them:
            losses += 1
        else:
            ties += 1
    return {
        "games": len(last),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "diff": int(round(diff)),
        "record": record_text(wins, losses, ties) if last else "—",
    }


def power_raw(team: dict, form: dict) -> float:
    base = (team["wp"] - 0.5) * 100
    recent = (form["diff"] / form["games"]) if form["games"] else 0.0
    return base * 0.72 + recent * 1.35


def power_index(raw: float) -> int:
    return int(max(1, min(99, round(50 + raw))))


def form_direction(diff: int) -> str:
    if diff > 0:
        return "up"
    if diff < 0:
        return "down"
    return "flat"


def simulate(teams: dict, games: list[dict]) -> dict[str, tuple[int, int, int]]:
    rng = random.Random(2026)
    conferences = {
        "AFC": [abbr for abbr, team in teams.items() if team["conference"] == "AFC"],
        "NFC": [abbr for abbr, team in teams.items() if team["conference"] == "NFC"],
    }
    divisions = {
        conf: {name: members for name, members in DIVISIONS.items() if name.startswith(conf)}
        for conf in ("AFC", "NFC")
    }
    base = {
        abbr: {
            "wins": team["wins"],
            "div": team["divWins"],
            "conf": team["confWins"],
            "diff": team["diff"],
        }
        for abbr, team in teams.items()
    }
    made = {abbr: [0, 0, 0] for abbr in teams}
    for _ in range(SIMS):
        state = {abbr: dict(row) for abbr, row in base.items()}
        for game in games:
            home = game["home"]
            away = game["away"]
            home_wins = rng.random() < game["p"]
            margin = max(1, int(round(abs(rng.gauss((game["p"] - 0.5) * 16, 7)))))
            winner, loser = (home, away) if home_wins else (away, home)
            state[winner]["wins"] += 1
            state[winner]["diff"] += margin
            state[loser]["diff"] -= margin
            if game["sameDiv"]:
                state[winner]["div"] += 1
            if game["sameConf"]:
                state[winner]["conf"] += 1

        def rank(abbr: str) -> tuple:
            row = state[abbr]
            return (row["wins"], row["div"], row["conf"], row["diff"])

        for conf, members_by_div in divisions.items():
            winners = set()
            for members in members_by_div.values():
                present = [abbr for abbr in members if abbr in state]
                if present:
                    winners.add(max(present, key=rank))
            pool = [abbr for abbr in conferences[conf] if abbr not in winners]
            pool.sort(key=rank, reverse=True)
            wildcard = set(pool[:3])
            for abbr in winners:
                made[abbr][0] += 1
                made[abbr][1] += 1
            for abbr in wildcard:
                made[abbr][0] += 1
                made[abbr][2] += 1
    return {abbr: (row[0], row[1], row[2]) for abbr, row in made.items()}


def load_baseline(current_week: int) -> dict:
    if not LEAGUE_PATH.exists():
        return {}
    try:
        old = json.loads(LEAGUE_PATH.read_text())
    except json.JSONDecodeError:
        return {}
    saved = old.get("rankBaseline") if isinstance(old.get("rankBaseline"), dict) else {}
    if old.get("rankBaselineWeek") == current_week and saved:
        return {abbr: int(rank) for abbr, rank in saved.items()}
    frozen = {}
    for row in old.get("powerRankings") or []:
        if row.get("abbr") and row.get("rank"):
            frozen[row["abbr"]] = int(row["rank"])
    return frozen


def side_block(teams: dict, abbr: str, score) -> dict:
    team = teams[abbr]
    return {
        "abbr": abbr,
        "name": team["name"],
        "nickname": team["nickname"],
        "logo": team["logo"],
        "record": record_text(team["wins"], team["losses"], team["ties"]),
        "score": "" if score in (None, "") else score,
    }


def game_card(teams: dict, game: dict) -> dict:
    home = side_block(teams, game["home"], game["homeScore"])
    away = side_block(teams, game["away"], game["awayScore"])
    home_score = score_num(game["homeScore"])
    away_score = score_num(game["awayScore"])
    if game["completed"] and home_score is not None and away_score is not None:
        home["winner"] = home_score > away_score
        away["winner"] = away_score > home_score
    if game["completed"]:
        status = "Final"
    elif game["state"] == "in":
        status = game["detail"] or "Live"
    else:
        status = fmt_when(game["date"])
    return {
        "id": game["id"],
        "date": game["date"],
        "week": game["week"],
        "status": status,
        "live": game["state"] == "in",
        "completed": game["completed"],
        "venue": game["venue"],
        "broadcast": game["broadcast"],
        "home": home,
        "away": away,
    }


def standings_rows(teams: dict, conference: str) -> tuple[list[dict], dict]:
    clubs = [team for team in teams.values() if team["conference"] == conference]
    clubs.sort(key=lambda team: (team["seed"], -team["wins"], team["losses"], -team["diff"]))
    cut = next((team for team in clubs if team["seed"] == 7), clubs[6] if len(clubs) > 6 else clubs[-1])
    rows = []
    for team in clubs:
        rows.append(public_team(
            team,
            gb=fmt_gb(games_back(team, cut)),
            path=path_label(team),
            inField=team["seed"] <= 7,
            isCut=team["seed"] == 7,
        ))
    return rows, cut


def build_league(ctx: dict) -> dict:
    teams = ctx["teams"]
    games = ctx["games"]
    forms = ctx["forms"]
    raw = ctx["raw"]
    ranks = ctx["ranks"]
    moves = ctx["moves"]
    current_week = ctx["current_week"]
    last_week = ctx["last_week"]
    order = ctx["order"]
    power_rows = []
    for abbr in order:
        team = teams[abbr]
        form = forms[abbr]
        row = public_team(team)
        row.update({
            "rank": ranks[abbr],
            "move": moves.get(abbr, 0),
            "power": power_index(raw[abbr]),
            "formRecord": form["record"],
            "formDiff": form["diff"],
            "formDirection": form_direction(form["diff"]),
        })
        power_rows.append(row)
    by_abbr = {row["abbr"]: row for row in power_rows}
    played = [abbr for abbr in teams if forms[abbr]["games"]]
    played.sort(key=lambda abbr: (forms[abbr]["diff"], forms[abbr]["wins"], -forms[abbr]["losses"]))
    up_abbrs = list(reversed(played[-4:]))
    up_set = set(up_abbrs)
    down_abbrs = [abbr for abbr in played if abbr not in up_set][:4]
    afc_rows, afc_cut = standings_rows(teams, "AFC")
    nfc_rows, nfc_cut = standings_rows(teams, "NFC")
    leaders = []
    clubs = []
    for members in DIVISIONS.values():
        present = [teams[abbr] for abbr in members if abbr in teams]
        for abbr in members:
            if abbr in teams:
                clubs.append({
                    "abbr": abbr,
                    "name": teams[abbr]["name"],
                    "nickname": teams[abbr]["nickname"],
                    "logo": teams[abbr]["logo"],
                })
        if not present:
            continue
        leader = min(present, key=lambda team: (team["seed"], -team["wins"], -team["diff"]))
        leaders.append(public_team(leader))
    this_week = [game_card(teams, game) for game in games if game["week"] == current_week]
    last_games = [game_card(teams, game) for game in games if last_week and game["week"] == last_week]
    byes = []
    for abbr, (_rows, bye) in ctx["schedules"].items():
        if bye == current_week and abbr in teams:
            byes.append({
                "abbr": abbr,
                "name": teams[abbr]["name"],
                "nickname": teams[abbr]["nickname"],
                "logo": teams[abbr]["logo"],
            })
    byes.sort(key=lambda team: team["name"])
    top = power_rows[0]
    hot = by_abbr[up_abbrs[0]] if up_abbrs else top
    cold = by_abbr[down_abbrs[0]] if down_abbrs else None
    afc_row = next(row for row in afc_rows if row["isCut"])
    nfc_row = next(row for row in nfc_rows if row["isCut"])
    if hot["formDiff"] > 0 and hot["abbr"] != top["abbr"]:
        headline = f"The {hot['nickname']} are the team on the rise"
    else:
        headline = f"The {top['nickname']} lead the power rankings"
    blurb = (
        f"{len(this_week)} games in week {current_week}. "
        f"The {top['nickname']} are No. 1 at {top['record']} with a {signed(top['diff'])} point differential. "
        f"The AFC's last playoff spot is the {afc_cut['nickname']} at {afc_row['record']}. "
        f"The NFC's last spot is the {nfc_cut['nickname']} at {nfc_row['record']}. "
    )
    if hot["formDiff"] > 0:
        blurb += (
            f"The {hot['nickname']} lead the heat check at {hot['formRecord']} "
            f"and {signed(hot['formDiff'])} points over the last three games."
        )
    elif cold:
        blurb += (
            f"The {cold['nickname']} are the coldest club at {signed(cold['formDiff'])} "
            "over the last three games."
        )
    ticker = [
        f"WEEK {current_week}",
        f"NO. 1 {top['abbr']} {top['record']}",
        f"AFC CUT {afc_cut['abbr']} {afc_row['record']}",
        f"NFC CUT {nfc_cut['abbr']} {nfc_row['record']}",
        f"HOT {hot['abbr']} {signed(hot['formDiff'])} LAST 3",
    ]
    ticker.extend(f"{row['rank']} {row['abbr']}" for row in power_rows[:5])
    return {
        "generatedAt": ctx["generated"],
        "season": ctx["season"],
        "week": current_week,
        "weekLabel": f"Week {current_week} · {ctx['season']}",
        "rankBaseline": ctx["baseline"],
        "rankBaselineWeek": current_week,
        "ticker": ticker,
        "narrative": {
            "kicker": f"Week {current_week}",
            "headline": headline,
            "blurb": blurb,
        },
        "chips": [
            {"label": "Week", "value": str(current_week)},
            {"label": "Games", "value": str(len(this_week))},
            {"label": "On bye", "value": str(len(byes)) if byes else "None"},
            {"label": "Hottest", "value": hot["abbr"]},
            {"label": "AFC cut", "value": f"{afc_cut['abbr']} {afc_row['record']}"},
            {"label": "NFC cut", "value": f"{nfc_cut['abbr']} {nfc_row['record']}"},
        ],
        "spotlight": {"top": top, "afc": afc_row, "nfc": nfc_row},
        "clubs": clubs,
        "powerRankings": power_rows,
        "rankingsBlurb": (
            "Point differential shrunk toward a league-average team, plus the margin over the last three games. "
            "Movement is since this week's order was frozen."
        ),
        "trending": {"up": [by_abbr[abbr] for abbr in up_abbrs], "down": [by_abbr[abbr] for abbr in down_abbrs]},
        "trendingBlurb": "Point differential over the last three games. Heating up is the best stretch. Cooling off is the worst.",
        "afc": afc_rows,
        "nfc": nfc_rows,
        "afcBlurb": "Seven AFC clubs play on. The line under the seventh seed is the cut line.",
        "nfcBlurb": "Seven NFC clubs play on. The line under the seventh seed is the cut line.",
        "leaders": leaders,
        "thisWeek": this_week,
        "lastWeek": last_games,
        "byes": byes,
        "weekBlurb": f"Week {current_week} kickoffs, with the score once a game is live or final.",
        "lastBlurb": f"Week {last_week} finals." if last_week else "No regular-season week before this one.",
    }


def build_focus(abbr: str, ctx: dict) -> dict:
    teams = ctx["teams"]
    club = teams[abbr]
    conf = club["conference"]
    division = club["division"]
    short = division_short(division)
    nick = club["nickname"]
    division_set = set(DIVISIONS[division])
    division_teams = [teams[code] for code in DIVISIONS[division] if code in teams]
    division_teams.sort(key=lambda team: (team["seed"], -team["wins"], -team["diff"]))
    leader = division_teams[0]
    conf_teams = [team for team in teams.values() if team["conference"] == conf]
    conf_teams.sort(key=lambda team: (team["seed"], -team["wins"], team["losses"], -team["diff"]))
    cut = next((team for team in conf_teams if team["seed"] == 7), conf_teams[6] if len(conf_teams) > 6 else conf_teams[-1])
    gb_cut = games_back(club, cut)
    gb_div = games_back(club, leader)
    in_field = club["seed"] <= 7
    club_max = club["wins"] + int(club.get("gr") or 0)
    teams_clear = [team for team in conf_teams if team["abbr"] != abbr and team["wins"] > club_max]
    eliminated = len(teams_clear) >= 7
    clinched = all(
        team["wins"] + int(team.get("gr") or 0) < club["wins"]
        for team in conf_teams
        if team["abbr"] != abbr
    )
    rivals = [team for team in division_teams if team["abbr"] != abbr]
    magic_rows = [(18 - club["wins"] - rival["losses"], rival) for rival in rivals]
    magic_rows.sort(key=lambda item: item[0], reverse=True)
    magic, magic_rival = magic_rows[0]
    elim_rows = [(18 - club["losses"] - rival["wins"], rival) for rival in rivals]
    elim_rows.sort(key=lambda item: item[0])
    elimination, elim_rival = elim_rows[0]
    rows, bye_week = ctx["schedules"].get(abbr, ([], None))
    record = record_text(club["wins"], club["losses"], club["ties"])

    def club_win_pct(opponent: str, club_home: bool, neutral: bool) -> int:
        opp = teams[opponent]
        if club_home:
            probability = win_prob(club["wp"], opp["wp"], neutral)
        else:
            probability = 1 - win_prob(opp["wp"], club["wp"], neutral)
        return int(round(probability * 100))

    schedule_cards = []
    recent = []
    for game in rows:
        home = game["home"]["abbr"]
        away = game["away"]["abbr"]
        club_home = home == abbr
        opponent = away if club_home else home
        opp = teams.get(opponent, {})
        us_score = game["home"]["score"] if club_home else game["away"]["score"]
        them_score = game["away"]["score"] if club_home else game["home"]["score"]
        card = {
            "id": game["id"],
            "date": game["date"],
            "week": game["week"],
            "isHome": club_home,
            "opponent": {
                "abbr": opponent,
                "name": opp.get("name") or game["away" if club_home else "home"]["name"],
                "nickname": opp.get("nickname") or "",
                "logo": opp.get("logo") or "",
                "record": record_text(opp["wins"], opp["losses"], opp["ties"]) if opp else "",
                "pct": opp.get("pct"),
            },
            "divisionGame": opponent in division_set,
            "conferenceGame": opp.get("conference") == conf,
            "venue": game["venue"],
            "broadcast": game["broadcast"],
            "detail": game["detail"],
            "live": game["state"] == "in",
            "final": game["completed"],
            "winPct": club_win_pct(opponent, club_home, game["neutral"]) if opponent in teams and not game["completed"] else None,
            "homeAbbr": home,
            "awayAbbr": away,
            "homeScore": game["home"]["score"],
            "awayScore": game["away"]["score"],
            "usScore": us_score,
            "themScore": them_score,
        }
        if game["completed"]:
            us_n = score_num(us_score)
            them_n = score_num(them_score)
            if us_n is None or them_n is None:
                us_n = them_n = 0
            card["result"] = "W" if us_n > them_n else "L" if us_n < them_n else "T"
            recent.append(card)
        else:
            schedule_cards.append(card)
    if bye_week:
        coming = [game["week"] for game in schedule_cards if game.get("week")]
        current_card_week = min(coming, default=bye_week)
        if bye_week >= current_card_week:
            schedule_cards.append({
                "bye": True,
                "week": bye_week,
                "date": "",
                "isHome": True,
                "opponent": {},
                "venue": "Open date",
                "broadcast": "",
                "winPct": None,
                "final": False,
                "live": False,
            })
    schedule_cards.sort(key=lambda game: (game.get("week") or 99, game.get("date") or ""))
    remaining_games = [game for game in schedule_cards if not game.get("bye") and not game.get("final")]
    sos_values = [game["opponent"].get("pct") for game in remaining_games if game["opponent"].get("pct") is not None]
    sos = sum(sos_values) / len(sos_values) if sos_values else None
    home_left = sum(1 for game in remaining_games if game["isHome"])
    division_left = sum(1 for game in remaining_games if game.get("divisionGame"))
    next_game = remaining_games[0] if remaining_games else None
    next_label = "Season complete"
    if next_game:
        moment = local_dt(next_game["date"])
        day = moment.strftime("%a") if moment else "Next"
        spot = "vs" if next_game["isHome"] else "@"
        next_label = f"{day} {spot} {next_game['opponent']['abbr']}"
    leaders = []
    for name in DIVISIONS:
        if not name.startswith(conf):
            continue
        members = [teams[code] for code in DIVISIONS[name] if code in teams]
        if not members:
            continue
        division_leader = min(members, key=lambda team: (team["seed"], -team["wins"], -team["diff"]))
        leaders.append(public_team(division_leader))

    def row_for(team: dict, pivot: dict) -> dict:
        return public_team(
            team,
            gb=fmt_gb(games_back(team, pivot)),
            gbValue=round(games_back(team, pivot), 2),
            path=path_label(team),
            inField=team["seed"] <= 7,
            isFocus=team["abbr"] == abbr,
            isCut=team["seed"] == 7,
        )

    conference_rows = [row_for(team, cut) for team in conf_teams]
    division_rows = [row_for(team, leader) for team in division_teams]
    for row, team in zip(division_rows, division_teams):
        row["isCut"] = False
        row["divisionCut"] = team["abbr"] == leader["abbr"]

    rooting = []
    horizon = now_et() + timedelta(days=12)
    candidates = []
    for game in ctx["games"]:
        if game["completed"]:
            continue
        moment = local_dt(game["date"])
        if not moment or moment > horizon:
            continue
        involved = {game["home"], game["away"]}
        if abbr in involved:
            priority = 0
        elif involved & division_set:
            priority = 1
        elif any(teams[code]["seed"] == 7 and teams[code]["conference"] == conf for code in involved):
            priority = 2
        elif any(teams[code]["conference"] == conf and teams[code]["seed"] <= 10 for code in involved):
            priority = 3
        else:
            continue
        candidates.append((moment, priority, game))
    candidates.sort(key=lambda item: (item[0], item[1]))
    for _moment, _priority, game in candidates[:8]:
        home = teams[game["home"]]
        away = teams[game["away"]]
        home_pct = int(round(game["p"] * 100))
        away_pct = 100 - home_pct
        if abbr in (game["home"], game["away"]):
            tag = f"{nick} game"
            tag_class = "jays"
            opp = away if game["home"] == abbr else home
            spot = "at home" if game["home"] == abbr else "on the road"
            note = f"The {nick} are {spot} against the {opp['nickname']}."
        else:
            notes = []
            for side in (away, home):
                if side["abbr"] in division_set and side["abbr"] != abbr:
                    notes.append(f"A {side['nickname']} loss helps the {short} race.")
                elif side["conference"] == conf and side["seed"] <= 7:
                    notes.append(f"The {side['nickname']} hold the No. {side['seed']} seed. A loss helps the cut line.")
            tag = "Need a loss" if notes else f"{conf} game"
            tag_class = "need" if notes else "race"
            note = " ".join(notes[:2]) or f"Two clubs still in the {conf} picture."
        rooting.append({
            "date": game["date"],
            "homeAbbr": home["abbr"],
            "awayAbbr": away["abbr"],
            "homeWinPct": home_pct,
            "awayWinPct": away_pct,
            "interest": tag,
            "tagClass": tag_class,
            "note": note,
            "live": game["state"] == "in",
        })

    h2h = []
    for game in recent:
        if game["opponent"]["abbr"] in division_set:
            h2h.append(
                f"{game['result']} {game['usScore']}–{game['themScore']} "
                f"{'vs' if game['isHome'] else '@'} {game['opponent']['abbr']}"
            )
    next_division = next((game for game in remaining_games if game.get("divisionGame")), None)
    if h2h:
        h2h_text = f"Head-to-head inside the {short}: " + "; ".join(h2h) + "."
    elif next_division:
        h2h_text = (
            f"No {division} games yet. The first is Week {next_division['week']} "
            f"{'vs' if next_division['isHome'] else '@'} {next_division['opponent']['abbr']}."
        )
    else:
        h2h_text = f"No {division} games left on the schedule."

    efficiency = club.get("efficiency") or {}
    ppg = efficiency.get("ppg")
    papg = efficiency.get("papg")
    third = efficiency.get("third")
    rz = efficiency.get("rz")
    sack_margin = None
    if efficiency:
        sack_margin = (efficiency.get("sacksFor") or 0) - (efficiency.get("sacksAllowed") or 0)
    turnover = efficiency.get("to")
    games_played = efficiency.get("gp") or club["gp"] or 0
    top_text = fmt_clock(efficiency.get("topSeconds"), games_played)
    top_minutes = None
    if efficiency.get("topSeconds") and games_played:
        top_minutes = (efficiency["topSeconds"] / games_played) / 60
    ypg = efficiency.get("ypg")
    yapg = efficiency.get("yapg")
    qb = efficiency.get("qbRating")

    if eliminated:
        headline = "See ya next season"
        kicker = "Mathematically out"
        blurb = f"The {nick} cannot catch seven {conf} teams even if they win out."
    elif clinched:
        headline = "January football"
        kicker = "Playoff berth clinched"
        blurb = f"The {nick} are in. They are the {conf} No. {club['seed']} seed at {record}."
    elif in_field:
        headline = f"Holding the No. {club['seed']} seed"
        kicker = f"Inside the {conf} field"
        if abs(gb_cut) < 0.05:
            blurb = f"The {nick} are {record} and currently in, sitting on the cut line."
        else:
            blurb = (
                f"The {nick} are {record} and currently in. "
                f"The cushion on the cut line is {gb_words(abs(gb_cut))}."
            )
    elif gb_div <= gb_cut:
        if abs(gb_div) < 0.05:
            headline = f"Even with the {short} lead"
        else:
            headline = f"{gb_words(gb_div).capitalize()} back of the {short}"
        kicker = f"{conf} playoff race"
        blurb = (
            f"The {nick} are {record} with a {signed(club['diff'])} point differential, "
            f"{gb_words(gb_div)} behind the {leader['nickname']} in the {division}, and "
            f"{gb_words(gb_cut)} off the last wild-card berth. {club.get('gr', 0)} games left"
        )
    else:
        headline = f"{gb_words(gb_cut).capitalize()} off the cut line"
        kicker = f"{conf} playoff race"
        blurb = (
            f"The {nick} are {record} with a {signed(club['diff'])} point differential, "
            f"{gb_words(gb_cut)} behind the last {conf} playoff spot, and "
            f"{gb_words(gb_div)} back of the {leader['nickname']} in the {short}. "
            f"{club.get('gr', 0)} games left"
        )
    if next_game and not eliminated and not clinched and not in_field:
        moment = local_dt(next_game["date"])
        day = moment.strftime("%A") if moment else "next"
        if next_game["isHome"]:
            blurb += f", starting {day} at home against the {next_game['opponent']['nickname']}."
        else:
            blurb += f", starting {day} at the {next_game['opponent']['nickname']}."
    elif not blurb.endswith("."):
        blurb += "."

    if in_field and not eliminated:
        primary = {"label": f"{conf} playoff seed", "value": f"#{club['seed']}", "sub": "Inside the field of seven", "heatLabel": "Season left"}
    elif eliminated:
        primary = {"label": "Playoff berth", "value": "OUT", "sub": "Cannot catch the field", "heatLabel": "Season left"}
    else:
        primary = {
            "label": "Games back of the cut line",
            "value": fmt_gb(gb_cut),
            "sub": f"of the No. 7 seed · {cut['abbr']} {record_text(cut['wins'], cut['losses'], cut['ties'])}",
            "heatLabel": "Season left",
        }
    games_left = int(club.get("gr") or 0)
    primary["heat"] = int(round(100 * games_left / SEASON_GAMES)) if SEASON_GAMES else 0
    primary["heatText"] = f"{games_left} left"
    if clinched and club["abbr"] == leader["abbr"] and magic <= 0:
        magic_meter = {"label": division, "value": "IN", "sub": "Division clinched on wins", "note": ""}
    elif eliminated:
        magic_meter = {"label": "Elimination", "value": "OUT", "sub": "The division and the wild card are both gone", "note": ""}
    else:
        magic_meter = {
            "label": f"Magic number to win the {short}",
            "value": "0" if magic <= 0 else str(magic),
            "sub": f"{abbr} wins + {magic_rival['abbr']} losses",
            "note": (
                f"The {magic_rival['nickname']} are the team to catch. "
                f"Elimination number vs the {elim_rival['nickname']} is {max(elimination, 0)}."
            ),
        }
    division_pct = club.get("divisionPct")
    wildcard_pct = club.get("wildcardPct")
    odds_note = (
        f"Division title in {division_pct:.1f}% of sims, wild card in {wildcard_pct:.1f}%. "
        "Point differential, shrunk toward average, plus home field. Not a betting line."
    )

    def kpi(stat: str, label: str, value, hint: str) -> dict:
        return {"stat": stat, "label": label, "value": value, "hint": hint}

    third_display = efficiency.get("thirdDisplay") or ("—" if third is None else f"{third:.0f}%")
    third_hint = (
        f"{third_display} · around 40% is average"
        if third_display and third_display != "—"
        else "Around 40% is average"
    )
    kpis = [
        kpi("W-L", "Record", record, club["streak"] if club["streak"] != "—" else "This season"),
        kpi("DIFF", "Point diff", signed(club["diff"]), "Points scored minus points allowed"),
        kpi("PPG", "Points / game", "—" if ppg is None else f"{ppg:.1f}", "League average sits near 22"),
        kpi("PA", "Points allowed", "—" if papg is None else f"{papg:.1f}", "Per game. Lower is the whole defense"),
        kpi("YPG", "Yards / game", "—" if ypg is None else f"{ypg:.1f}", "Total offense, pass plus rush"),
        kpi("YPG", "Yards allowed", "—" if yapg is None else f"{yapg:.1f}", "What the defense is giving up"),
        kpi("TO", "Turnover margin", "—" if turnover is None else signed(turnover), "Takeaways minus giveaways"),
        kpi("3rd", "Third down", "—" if third is None else f"{third:.0f}%", third_hint),
        kpi("RZ", "Red zone TDs", "—" if rz is None else f"{rz:.0f}%", "Trips inside the 20 that become touchdowns"),
        kpi("SACK", "Sack margin", "—" if sack_margin is None else signed(sack_margin), "Sacks recorded minus sacks allowed"),
        kpi("DIV", "Division", club["divisionRecord"], f"{division} record. First tiebreaker after head-to-head"),
        kpi("CONF", "Conference", club["conferenceRecord"], f"{conf} record. Matters once division record is tied"),
    ]
    scoring_margin = None if ppg is None or papg is None else ppg - papg
    trends = [
        {
            "stat": "DIFF",
            "label": "Point differential",
            "value": signed(club["diff"]),
            "detail": "The cleanest 'are they actually this good?' check.",
            "direction": direction_for("diff", club["diff"]),
        },
        {
            "stat": "PPG",
            "label": "Scoring margin / game",
            "value": "—" if scoring_margin is None else signed(round(scoring_margin, 1)),
            "detail": "—" if ppg is None else f"{ppg:.1f} scored, {papg:.1f} allowed.",
            "direction": direction_for("margin", scoring_margin),
        },
        {
            "stat": "3rd",
            "label": "Third down",
            "value": "—" if third is None else f"{third:.0f}%",
            "detail": third_display if third_display and third_display != "—" else "Conversions on third down.",
            "direction": direction_for("third", third),
        },
        {
            "stat": "RZ",
            "label": "Red zone TDs",
            "value": "—" if rz is None else f"{rz:.0f}%",
            "detail": "Touchdown rate inside the opponent 20.",
            "direction": direction_for("rz", rz),
        },
        {
            "stat": "SACK",
            "label": "Sack margin",
            "value": "—" if sack_margin is None else signed(sack_margin),
            "detail": "Pass rush minus pass protection.",
            "direction": direction_for("sack", sack_margin),
        },
        {
            "stat": "TOP",
            "label": "Time of possession",
            "value": top_text,
            "detail": "Per game. Thirty minutes is a split clock.",
            "direction": direction_for("top", top_minutes),
        },
    ]
    division_path = {
        "title": division,
        "value": "IN" if club["abbr"] == leader["abbr"] and club["seed"] <= 4 else f"{fmt_gb(gb_div)} GB",
        "detail": (
            f"The {leader['nickname']} lead at {record_text(leader['wins'], leader['losses'], leader['ties'])}. "
            f"The {nick} are {club['divisionRecord']} inside the division. Win the {short} and the seed is automatic."
        ),
        "in": club["seed"] <= 4,
    }
    wildcard_path = {
        "title": "Wild card",
        "value": "IN" if 5 <= club["seed"] <= 7 else ("Not needed" if club["seed"] <= 4 else f"{fmt_gb(gb_cut)} GB"),
        "detail": (
            f"The {cut['nickname']} hold the last berth at {record_text(cut['wins'], cut['losses'], cut['ties'])}. "
            "Three wild cards get in after the four division winners."
        ),
        "in": 5 <= club["seed"] <= 7,
    }
    projected = club["wins"] + games_left * club["wp"]
    power_rank = club.get("powerRank")
    chips = [
        {"label": "Record", "value": record},
        {"label": f"{conf} seed", "value": f"No. {club['seed']}"},
        {"label": "Power rank", "value": f"No. {power_rank}" if power_rank else "—"},
        {"label": "Streak", "value": club["streak"]},
        {"label": "Next", "value": next_label},
        {"label": "Point diff", "value": signed(club["diff"])},
        {"label": "Projected wins", "value": f"{projected:.1f}"},
    ]
    ticker = [
        f"{abbr} {record}",
        f"{conf} NO. {club['seed']}",
        f"POWER NO. {power_rank}" if power_rank else "POWER —",
        club["streak"],
        f"POINT DIFF {signed(club['diff'])}",
        f"{fmt_gb(gb_div)} GB OF {leader['abbr']} IN THE {short.upper()}",
        f"{fmt_gb(gb_cut)} GB OF THE CUT LINE",
        f"NEXT {next_label.upper()}",
    ]
    if bye_week:
        ticker.append(f"BYE WEEK {bye_week}")
    if qb is not None:
        ticker.append(f"PASSER RATING {qb:.1f}")
    people = ctx["people"].get(abbr) or {}
    players = people.get("players") or {
        "quarterback": [],
        "skill": [],
        "defense": [],
        "label": "Roster feed was unavailable on this refresh.",
    }
    primary_color, accent, deep, powder = THEMES.get(abbr, THEMES["MIA"])
    return {
        "generatedAt": ctx["generated"],
        "season": ctx["season"],
        "seasonGames": SEASON_GAMES,
        "team": abbr,
        "teamName": club["name"],
        "eliminated": eliminated,
        "clinched": clinched,
        "focus": {
            "abbr": abbr,
            "name": club["name"],
            "nickname": nick,
            "conference": conf,
            "division": division,
            "divisionShort": short,
            "logo": club["logo"],
        },
        "theme": {"primary": primary_color, "accent": accent, "deep": deep, "powder": powder},
        "rules": [f"Win the {short}", "Or grab a wild card", f"7 {conf} teams"],
        "headings": {
            "division": division,
            "leaders": "Division leaders",
            "leadersBlurb": f"These four are the automatic {conf} seeds. Everyone else is chasing the three wild cards.",
            "pathsBlurb": f"Win the {division}, or be one of the three best remaining clubs in the conference. The closer route is the one that matters.",
            "legendTeam": nick,
            "footer": f"Updated from ESPN’s public NFL feeds. Not affiliated with the NFL, the {club['name']}, or ESPN.",
            "footerTiny": (
                f"Seven {conf} teams qualify: four division winners and three wild cards. "
                "The playoff percentage is a season simulation from point differential and home field. It is not a betting line."
            ),
            "conclusion": f"The {club['name']} have been mathematically eliminated from the NFL playoffs.",
            "injuryBlurb": f"{nick} listed as injured or on injured reserve. A Tuesday practice note can move before Sunday.",
            "rootingBlurb": "Who needs to lose for the division or the cut line to get closer. Not a betting line, and not a live in-game number.",
        },
        "ticker": ticker,
        "narrative": {"kicker": kicker, "headline": headline, "blurb": blurb},
        "chips": chips,
        "meters": {"primary": primary, "third": magic_meter},
        "playoffOdds": {
            "percent": club.get("playoffPct"),
            "sims": SIMS,
            "note": odds_note,
            "divisionPercent": division_pct,
            "wildcardPercent": wildcard_pct,
        },
        "kpis": kpis,
        "trends": trends,
        "paths": {"division": division_path, "wildcard": wildcard_path},
        "tableBlurb": f"Seven {conf} clubs play on: four division winners and three wild cards. The line under the seventh seed is the whole race.",
        "legend": {"in": "In a playoff spot", "out": "Chasing"},
        "conference": conference_rows,
        "divisionTable": division_rows,
        "leaders": leaders,
        "compareTitle": division,
        "compare": [public_team(team) for team in division_teams],
        "remaining": {
            "games": len(remaining_games),
            "home": home_left,
            "away": len(remaining_games) - home_left,
            "division": division_left,
            "bye": bye_week,
            "sos": None if sos is None else round(sos, 3),
        },
        "schedule": schedule_cards,
        "rooting": rooting,
        "recent": recent,
        "recentBlurb": "The games already in the book.",
        "tiebreak": {
            "division": club["divisionRecord"],
            "conference": club["conferenceRecord"],
            "diff": signed(club["diff"]),
            "headToHead": h2h_text,
            "detail": (
                f"If the {short} finishes level, the NFL starts with head-to-head, then division record, "
                "then common games, then conference record. Point differential is the eye test. "
                "It is not the first tiebreaker."
            ),
            "elimination": max(elimination, 0),
            "elimRival": elim_rival["abbr"],
        },
        "injuries": people.get("injuries") or [],
        "players": players,
        "qbRating": None if qb is None else round(qb, 1),
    }


def ensure_pages() -> None:
    missing = [
        abbr
        for members in DIVISIONS.values()
        for abbr in members
        if abbr not in CLUB_NAMES or abbr not in THEMES
    ]
    if missing:
        raise RuntimeError(f"Missing club metadata: {missing}")
    template = (ROOT / "templates" / "team.html").read_text()
    for abbr, name in CLUB_NAMES.items():
        primary, accent, deep, powder = THEMES[abbr]
        replacements = {
            "{{PRIMARY_WASH}}": rgba(primary, 0.40),
            "{{ACCENT_WASH}}": rgba(accent, 0.24),
            "{{ACCENT_SOFT}}": rgba(accent, 0.16),
            "{{PRIMARY}}": primary,
            "{{ACCENT}}": accent,
            "{{DEEP}}": deep,
            "{{POWDER}}": powder,
            "{{ABBR}}": abbr,
            "{{SLUG}}": abbr.lower(),
            "{{NAME}}": name,
        }
        html = template
        for key, value in replacements.items():
            html = html.replace(key, value)
        dest = ROOT / "teams" / abbr.lower() / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_text() != html:
            dest.write_text(html)


def stable(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("generatedAt", None)
    return json.dumps(copy, sort_keys=True, separators=(",", ":"))


def unchanged(path: Path, payload: dict) -> bool:
    if not path.exists():
        return False
    try:
        previous = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False
    return stable(previous) == stable(payload)


def publish() -> None:
    print("Standings...", flush=True)
    season, teams = load_standings()
    print(f"Schedules for {len(teams)} teams...", flush=True)
    schedules = load_schedules(season, teams)
    attach_remaining(teams, schedules)
    print("Team stats...", flush=True)
    stats_by_id = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(load_team_stats, team["id"]): team["id"] for team in teams.values()}
        for future in as_completed(futures):
            stats_by_id[futures[future]] = future.result()
    apply_stats(teams, stats_by_id)
    print("Rosters and leaders...", flush=True)
    people = load_people(season, teams)
    print("Simulating the rest of the season...", flush=True)
    games = catalog_games(schedules, teams)
    remaining = [game for game in games if not game["completed"]]
    odds = simulate(teams, remaining)
    for abbr, (made, division_titles, wildcards) in odds.items():
        teams[abbr]["playoffPct"] = round(100 * made / SIMS, 2)
        teams[abbr]["divisionPct"] = round(100 * division_titles / SIMS, 2)
        teams[abbr]["wildcardPct"] = round(100 * wildcards / SIMS, 2)
    forms = {
        abbr: form_for(abbr, schedules.get(abbr, ([], None))[0])
        for abbr in teams
    }
    raw = {abbr: power_raw(teams[abbr], forms[abbr]) for abbr in teams}
    order = sorted(teams, key=lambda abbr: (-raw[abbr], -teams[abbr]["wins"], -teams[abbr]["diff"], abbr))
    ranks = {abbr: index for index, abbr in enumerate(order, start=1)}
    for abbr, rank in ranks.items():
        teams[abbr]["powerRank"] = rank
    current_week, last_week = choose_weeks(games)
    baseline = load_baseline(current_week)
    if not baseline:
        baseline = {abbr: ranks[abbr] for abbr in ranks}
    moves = {abbr: int(baseline.get(abbr, ranks[abbr])) - ranks[abbr] for abbr in ranks}
    ctx = {
        "season": season,
        "teams": teams,
        "schedules": schedules,
        "games": games,
        "forms": forms,
        "raw": raw,
        "ranks": ranks,
        "moves": moves,
        "order": order,
        "baseline": baseline,
        "people": people,
        "generated": now_et().isoformat(),
        "current_week": current_week,
        "last_week": last_week,
    }
    print(f"Building week {current_week}...", flush=True)
    league = build_league(ctx)
    payloads = [(LEAGUE_PATH, league)]
    for abbr in sorted(teams):
        payloads.append((TEAMS_DIR / f"{abbr.lower()}.json", build_focus(abbr, ctx)))
    if all(unchanged(path, payload) for path, payload in payloads):
        print("No standings or schedule changes.")
        return
    for path, payload in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    top = league["powerRankings"][0]
    print(
        f"Wrote league.json and {len(payloads) - 1} team files. "
        f"Week {league['week']}: No. 1 {top['abbr']} {top['record']}. "
        f"This week {len(league['thisWeek'])} games. Last week {len(league['lastWeek'])} finals."
    )


def main() -> None:
    ensure_pages()
    publish()


if __name__ == "__main__":
    main()
