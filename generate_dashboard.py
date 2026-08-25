#!/usr/bin/env python3
import os
import json
import html
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME = os.getenv("PROFILE_USERNAME", "Archan47")
TOKEN = os.environ["GH_TOKEN"]

now = datetime.now(timezone.utc)
start = now - timedelta(days=364)

query = r'''
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        isFork
        stargazerCount
        languages(first: 10) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
'''

def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Archan47-profile-dashboard",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())
    if "errors" in result:
        raise RuntimeError(result["errors"])
    return result["data"]

data = graphql(query, {
    "login": USERNAME,
    "from": start.isoformat(),
    "to": now.isoformat(),
})["user"]

if not data:
    raise RuntimeError(f"GitHub user {USERNAME!r} was not found")

contrib = data["contributionsCollection"]
calendar = contrib["contributionCalendar"]

days = []
for week in calendar["weeks"]:
    for day in week["contributionDays"]:
        days.append((day["date"], int(day["contributionCount"])))
days.sort()

counts = {d: c for d, c in days}
today = now.date()
cursor = today
if counts.get(cursor.isoformat(), 0) == 0:
    cursor -= timedelta(days=1)

current_streak = 0
current_end = cursor
while counts.get(cursor.isoformat(), 0) > 0:
    current_streak += 1
    cursor -= timedelta(days=1)
current_start = cursor + timedelta(days=1)

longest = 0
longest_start = None
longest_end = None
run = 0
run_start = None
for d, c in days:
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    if c > 0:
        if run == 0:
            run_start = dt
        run += 1
        if run > longest:
            longest = run
            longest_start = run_start
            longest_end = dt
    else:
        run = 0
        run_start = None

repos = [r for r in data["repositories"]["nodes"] if not r["isFork"]]
stars = sum(int(r["stargazerCount"]) for r in repos)

language_bytes = {}
language_colors = {}
for repo in repos:
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        language_bytes[name] = language_bytes.get(name, 0) + int(edge["size"])
        if edge["node"].get("color"):
            language_colors[name] = edge["node"]["color"]

total_language_bytes = sum(language_bytes.values()) or 1
top_languages = sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)[:7]

last_days = days[-31:]
max_count = max([c for _, c in last_days] + [1])

def esc(s):
    return html.escape(str(s))

def fmt_date(d):
    if not d:
        return "—"
    return d.strftime("%b %d").replace(" 0", " ")

def range_text(a, b):
    if not a or not b:
        return "—"
    return f"{fmt_date(a)} – {fmt_date(b)}"

name = data.get("name") or USERNAME
total_contributions = int(calendar["totalContributions"])
commits = int(contrib["totalCommitContributions"])
prs = int(contrib["totalPullRequestContributions"])
issues = int(contrib["totalIssueContributions"])
repos_contributed = int(contrib["totalRepositoriesWithContributedCommits"])

W, H = 1360, 620
bg = "#0d1117"
text = "#f0f6fc"
muted = "#c9d1d9"
blue = "#2f81f7"
green = "#39d353"
grid = "#18304a"
border = "#30363d"

gx, gy, gw, gh = 780, 382, 525, 145
points = []
for i, (_, count) in enumerate(last_days):
    x = gx + (gw * i / max(1, len(last_days) - 1))
    y = gy + gh - (count / max_count) * gh
    points.append(f"{x:.1f},{y:.1f}")

svg = []
svg.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">{esc(name)} GitHub dashboard</title>
<desc id="desc">GitHub statistics, top languages, contribution streaks, and recent contribution activity.</desc>
<rect width="100%" height="100%" rx="14" fill="{bg}" stroke="{border}" stroke-width="2"/>
<style>
  text {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .title {{ fill:{blue}; font-size:18px; font-weight:600; }}
  .label {{ fill:{muted}; font-size:14px; font-weight:600; }}
  .value {{ fill:{text}; font-size:15px; font-weight:700; }}
  .big {{ fill:{text}; font-size:34px; font-weight:700; }}
  .small {{ fill:{green}; font-size:13px; }}
  .axis {{ fill:{blue}; font-size:9px; }}
</style>
''')

svg.append(f'<text x="350" y="56" class="title">{esc(name)}&#39;s GitHub Stats</text>')
stats = [
    ("★", "Total Stars Earned:", stars),
    ("↻", "Commits (last year):", commits),
    ("⑂", "Pull Requests (last year):", prs),
    ("!", "Issues (last year):", issues),
    ("▣", "Repos contributed to:", repos_contributed),
]
y = 92
for icon, label, value in stats:
    svg.append(f'<text x="350" y="{y}" fill="{blue}" font-size="18">{esc(icon)}</text>')
    svg.append(f'<text x="378" y="{y}" class="label">{esc(label)}</text>')
    svg.append(f'<text x="590" y="{y}" class="value">{value}</text>')
    y += 28

svg.append(f'<circle cx="700" cy="126" r="43" fill="none" stroke="#19324f" stroke-width="8"/>')
svg.append(f'<path d="M700 83 A43 43 0 0 1 738 105" fill="none" stroke="{blue}" stroke-width="8" stroke-linecap="round"/>')
svg.append(f'<text x="700" y="134" text-anchor="middle" fill="{muted}" font-size="22" font-weight="700">GH</text>')

svg.append(f'<text x="852" y="56" class="title">Most Used Languages</text>')
bar_x, bar_y, bar_w = 852, 82, 270
cursor_x = bar_x
for name_lang, size in top_languages:
    pct = size / total_language_bytes
    seg = max(2, bar_w * pct)
    color = language_colors.get(name_lang, blue)
    svg.append(f'<rect x="{cursor_x:.1f}" y="{bar_y}" width="{seg:.1f}" height="9" rx="3" fill="{color}"/>')
    cursor_x += seg

fallback_colors = ["#e34c26","#f1e05a","#3572A5","#563d7c","#DA5B0B","#89e051","#00ADD8"]
for idx, (lang, size) in enumerate(top_languages):
    col = idx % 2
    row = idx // 2
    x = 852 + col * 185
    y = 123 + row * 29
    color = language_colors.get(lang, fallback_colors[idx % len(fallback_colors)])
    pct = size / total_language_bytes * 100
    svg.append(f'<circle cx="{x+6}" cy="{y-4}" r="6" fill="{color}"/>')
    svg.append(f'<text x="{x+20}" y="{y}" fill="{muted}" font-size="13">{esc(lang)} {pct:.2f}%</text>')

svg.append(f'<line x1="40" y1="285" x2="1320" y2="285" stroke="{border}"/>')

left_centers = [215, 435, 655]
for x in [325, 545]:
    svg.append(f'<line x1="{x}" y1="340" x2="{x}" y2="520" stroke="{green}" stroke-width="1"/>')

svg.append(f'<text x="{left_centers[0]}" y="400" text-anchor="middle" class="big">{total_contributions}</text>')
svg.append(f'<text x="{left_centers[0]}" y="446" text-anchor="middle" fill="{text}" font-size="17">Total Contributions</text>')
svg.append(f'<text x="{left_centers[0]}" y="484" text-anchor="middle" class="small">{esc(start.date().strftime("%b %d, %Y").replace(" 0", " "))} – Present</text>')

cx, cy, r = left_centers[1], 396, 48
svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#19324f" stroke-width="8"/>')
svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{blue}" stroke-width="8" stroke-linecap="round" stroke-dasharray="{max(15, min(290, current_streak*28))} 320" transform="rotate(-90 {cx} {cy})"/>')
svg.append(f'<text x="{cx}" y="{cy+11}" text-anchor="middle" class="big">{current_streak}</text>')
svg.append(f'<text x="{cx}" y="474" text-anchor="middle" fill="{text}" font-size="17" font-weight="700">Current Streak</text>')
svg.append(f'<text x="{cx}" y="508" text-anchor="middle" class="small">{esc(range_text(current_start, current_end))}</text>')

svg.append(f'<text x="{left_centers[2]}" y="400" text-anchor="middle" class="big">{longest}</text>')
svg.append(f'<text x="{left_centers[2]}" y="446" text-anchor="middle" fill="{text}" font-size="17">Longest Streak</text>')
svg.append(f'<text x="{left_centers[2]}" y="484" text-anchor="middle" class="small">{esc(range_text(longest_start, longest_end))}</text>')

svg.append(f'<text x="{gx + gw/2}" y="340" text-anchor="middle" class="title">{esc(name)}&#39;s Contribution Graph</text>')
for i in range(6):
    yline = gy + gh - gh * i / 5
    val = round(max_count * i / 5)
    svg.append(f'<line x1="{gx}" y1="{yline:.1f}" x2="{gx+gw}" y2="{yline:.1f}" stroke="{grid}" stroke-width="1" stroke-dasharray="2 3"/>')
    svg.append(f'<text x="{gx-12}" y="{yline+3:.1f}" text-anchor="end" class="axis">{val}</text>')
for i in range(0, len(last_days), 5):
    x = gx + gw * i / max(1, len(last_days)-1)
    label = last_days[i][0][-2:]
    svg.append(f'<text x="{x:.1f}" y="{gy+gh+22}" text-anchor="middle" class="axis">{label}</text>')

svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{blue}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
for p, (_, count) in zip(points, last_days):
    x, y = p.split(",")
    svg.append(f'<circle cx="{x}" cy="{y}" r="3.3" fill="{text}"><title>{count} contributions</title></circle>')

svg.append('</svg>')

out = os.path.join(os.path.dirname(__file__), "..", "assets", "github-dashboard.svg")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(svg))

print(f"Wrote {out}")
