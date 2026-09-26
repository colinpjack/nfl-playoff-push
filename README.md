# The Push — NFL power rankings and playoff picture

A GitHub Pages site for the whole league. The home page is this week's power rankings and playoff picture: current standings, trending teams, the games on the slate, and last week's scores. Every club links to its own page, built the same way as the Dolphins dashboard: two routes into January, the cut line, the division, the schedule, and the football underneath the record.

## Pages

- `/` — this week's power rankings and playoff picture
- `/teams/mia/` — Miami, and the same path for all 32 clubs (`buf`, `kc`, `phi`, …)

## Enable it on GitHub

1. Push this project to a public GitHub repo (default branch `main`).
2. In the repo: **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: `/ (root)`
3. In **Settings → Actions → General**, allow GitHub Actions and permit the workflow to read and write contents so it can commit the JSON under `data/`.
4. Open **Actions → Update playoff dashboard → Run workflow** once so the first refresh is confirmed.

The public URL will be:

`https://<your-github-username>.github.io/nfl-playoff-push/`

## What updates

A scheduled GitHub Action runs `scripts/fetch_playoff_data.py`. It writes `data/league.json` and `data/teams/<club>.json` from ESPN's public NFL feeds. If nothing in the race changed, the workflow skips the commit.

Power rankings blend point differential, shrunk toward a league-average team, with the margin over the last three games. The playoff percentage is a 5,000-season simulation from that same model plus home field. It is not a betting line, and it is not an official NFL ranking.

## Local refresh

```bash
python3 scripts/fetch_playoff_data.py
python3 -m http.server 8080
```

Visit [http://localhost:8080](http://localhost:8080). Opening `index.html` as a file will block `fetch`.

## Notes

This is a fan dashboard, not an official NFL product.
