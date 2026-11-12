#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards from the public GitHub REST API."""
import json, os, urllib.request, urllib.error, urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USER = "naveen-elayaraja"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path("assets")
OUT.mkdir(exist_ok=True)
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "profile-stats-generator"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))

def svg_card(title, subtitle, body, width=495, height=190):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="#0d1117" stroke="#30363d"/>
<text x="24" y="34" fill="#58a6ff" font-family="Segoe UI,Arial,sans-serif" font-size="17" font-weight="700">{escape(title)}</text>
<text x="24" y="56" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="11">{escape(subtitle)}</text>
{body}</svg>'''

user = get(f"https://api.github.com/users/{USER}")
repos = get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=updated")
repos = [r for r in repos if not r.get("fork")]
stars = sum(r.get("stargazers_count", 0) for r in repos)
forks = sum(r.get("forks_count", 0) for r in repos)

# Search API totals include public pull requests authored by this account.
# Keep PRs separate from commits: one pull request may contain multiple commits.
def search_pr_count(filters):
    query = urllib.parse.quote(f"author:{USER} type:pr {filters}".strip())
    try:
        return get(f"https://api.github.com/search/issues?q={query}&per_page=1").get("total_count", 0)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return None

prs_opened = search_pr_count("")
prs_merged = search_pr_count("is:merged")
metrics = [
    ("PUBLIC REPOSITORIES", str(user.get("public_repos", 0))),
    ("FOLLOWERS", str(user.get("followers", 0))),
    ("STARS EARNED", str(stars)),
    ("FORKS", str(forks)),
    ("PULL REQUESTS", "—" if prs_opened is None else str(prs_opened)),
    ("PRS MERGED", "—" if prs_merged is None else str(prs_merged)),
]
parts = []
for i, (label, value) in enumerate(metrics):
    x = 24 + (i % 2) * 232
    y = 96 + (i // 2) * 52
    parts.append(f'<text x="{x}" y="{y}" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="11">{label}</text><text x="{x}" y="{y+25}" fill="#f0f6fc" font-family="Segoe UI,Arial,sans-serif" font-size="23" font-weight="700">{value}</text>')
(OUT / "github-stats.svg").write_text(svg_card("GitHub overview", "Live public-account metrics · updated daily", "".join(parts), height=250), encoding="utf-8")

language_bytes = Counter()
for repo in repos:
    if repo.get("size", 0) == 0:
        continue
    try:
        data = get(repo["languages_url"])
        language_bytes.update(data)
    except (urllib.error.URLError, TimeoutError, ValueError):
        continue
top = language_bytes.most_common(6)
total = sum(language_bytes.values()) or 1
lang_parts = []
y = 91
for name, amount in top:
    pct = amount * 100 / total
    lang_parts.append(f'<text x="24" y="{y}" fill="#c9d1d9" font-family="Segoe UI,Arial,sans-serif" font-size="12">{escape(name)}</text><text x="455" y="{y}" text-anchor="end" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="12">{pct:.1f}%</text>')
    lang_parts.append(f'<rect x="24" y="{y+9}" width="431" height="7" rx="3" fill="#21262d"/><rect x="24" y="{y+9}" width="{431*pct/100:.1f}" height="7" rx="3" fill="#3fb950"/>')
    y += 30
if not top:
    lang_parts.append('<text x="24" y="100" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="13">Language data is not available yet.</text>')
(OUT / "top-languages.svg").write_text(svg_card("Most used languages", "Calculated from language bytes across public, non-fork repositories", "".join(lang_parts), height=270), encoding="utf-8")

# GitHub's public events feed gives a recent activity snapshot (not lifetime commits).
events = get(f"https://api.github.com/users/{USER}/events/public?per_page=100")
today = datetime.now(timezone.utc).date()
days = [today - timedelta(days=i) for i in range(29, -1, -1)]
counts = Counter()
for event in events:
    try:
        day = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).date()
        if day in days:
            counts[day] += 1
    except (KeyError, ValueError):
        pass
max_count = max(counts.values(), default=1)
bars = []
for i, day in enumerate(days):
    count = counts[day]
    h = 12 + 55 * count / max_count if count else 3
    x = 25 + i * 14
    bars.append(f'<rect x="{x}" y="{112-h:.1f}" width="8" height="{h:.1f}" rx="2" fill="{ "#3fb950" if count else "#30363d" }"><title>{day.isoformat()}: {count} public events</title></rect>')
bars.append(f'<text x="25" y="137" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">{days[0].strftime("%b %d")}</text>')
bars.append(f'<text x="430" y="137" text-anchor="end" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">{today.strftime("%b %d")}</text>')
bars.append('<text x="24" y="160" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">Recent public GitHub events · not a complete contribution count</text>')
(OUT / "activity-graph.svg").write_text(svg_card("Recent GitHub activity", "Daily public-event activity over the last 30 days", "".join(bars), width=495, height=180), encoding="utf-8")
print("Generated GitHub stats, language, and activity SVG cards.")
