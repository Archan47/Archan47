#!/usr/bin/env python3

import os
import json
import html
import math
import urllib.request
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

USERNAME = os.getenv("PROFILE_USERNAME", "Archan47")
TOKEN = os.environ["GH_TOKEN"]

# ------------------------------------------------------------
# TIMEZONE / DATE RANGE
# ------------------------------------------------------------
LOCAL_TZ = ZoneInfo("Asia/Kolkata")
local_now = datetime.now(LOCAL_TZ)
local_today = local_now.date()

range_start_local = datetime.combine(
    local_today - timedelta(days=364),
    time.min,
    tzinfo=LOCAL_TZ,
)
range_end_local = datetime.combine(
    local_today,
    time.max,
    tzinfo=LOCAL_TZ,
)

range_start_utc = range_start_local.astimezone(timezone.utc)
range_end_utc = range_end_local.astimezone(timezone.utc)

# ------------------------------------------------------------
# GITHUB GRAPHQL QUERY
# ------------------------------------------------------------
QUERY = r"""
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name

    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      restrictedContributionsCount

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

    repositories(
      first: 100,
      ownerAffiliations: OWNER,
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        isFork
        stargazerCount
      }
    }
  }
}
"""


def graphql(query_text, variables):
    body = json.dumps(
        {
            "query": query_text,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Archan47-profile-dashboard",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]


def esc(value):
    return html.escape(str(value))


def format_date(date_value):
    if not date_value:
        return "—"
    return date_value.strftime("%b %d").replace(" 0", " ")


def range_text(start_date, end_date):
    if not start_date or not end_date:
        return "—"
    return f"{format_date(start_date)} – {format_date(end_date)}"


# ------------------------------------------------------------
# FETCH DATA
# ------------------------------------------------------------
data = graphql(
    QUERY,
    {
        "login": USERNAME,
        "from": range_start_utc.isoformat(),
        "to": range_end_utc.isoformat(),
    },
)["user"]

if not data:
    raise RuntimeError(f"GitHub user {USERNAME!r} was not found")

contrib = data["contributionsCollection"]
calendar = contrib["contributionCalendar"]

# ------------------------------------------------------------
# CONTRIBUTION DAYS
# ------------------------------------------------------------
days = []
for week in calendar["weeks"]:
    for day in week["contributionDays"]:
        days.append((day["date"], int(day["contributionCount"])))

days.sort()

counts = {date_string: count for date_string, count in days}

# ------------------------------------------------------------
# CURRENT STREAK
# ------------------------------------------------------------
cursor = local_today

# If there is no contribution today, continue streak check from yesterday.
if counts.get(cursor.isoformat(), 0) == 0:
    cursor -= timedelta(days=1)

current_end = cursor
current_streak = 0

while counts.get(cursor.isoformat(), 0) > 0:
    current_streak += 1
    cursor -= timedelta(days=1)

current_start = cursor + timedelta(days=1)

if current_streak == 0:
    current_start = None
    current_end = None

# ------------------------------------------------------------
# LONGEST STREAK
# ------------------------------------------------------------
longest_streak = 0
longest_start = None
longest_end = None

run_length = 0
run_start = None

for date_string, contribution_count in days:
    day_date = datetime.strptime(date_string, "%Y-%m-%d").date()

    if contribution_count > 0:
        if run_length == 0:
            run_start = day_date

        run_length += 1

        if run_length > longest_streak:
            longest_streak = run_length
            longest_start = run_start
            longest_end = day_date
    else:
        run_length = 0
        run_start = None

# ------------------------------------------------------------
# PROFILE STATS
# ------------------------------------------------------------
repos = [repo for repo in data["repositories"]["nodes"] if not repo["isFork"]]
stars = sum(int(repo["stargazerCount"]) for repo in repos)

profile_name = data.get("name") or USERNAME
total_contributions = int(calendar["totalContributions"])
restricted_contributions = int(contrib.get("restrictedContributionsCount") or 0)

commits = int(contrib["totalCommitContributions"])
pull_requests = int(contrib["totalPullRequestContributions"])
reviews = int(contrib["totalPullRequestReviewContributions"])
issues = int(contrib["totalIssueContributions"])
repos_contributed = int(contrib["totalRepositoriesWithContributedCommits"])

# ------------------------------------------------------------
# ACTIVITY OVERVIEW PERCENTAGES
# ------------------------------------------------------------
activity_total = commits + pull_requests + reviews + issues
if activity_total <= 0:
    activity_total = 1

commit_pct = commits / activity_total * 100
review_pct = reviews / activity_total * 100
issue_pct = issues / activity_total * 100
pr_pct = pull_requests / activity_total * 100

# ------------------------------------------------------------
# RECENT CONTRIBUTION GRAPH (LAST 31 DAYS)
# ------------------------------------------------------------
last_days = days[-31:]
max_count = max([count for _, count in last_days] + [1])

# ------------------------------------------------------------
# SVG SETTINGS
# ------------------------------------------------------------
WIDTH = 1400
HEIGHT = 720

BACKGROUND = "#0d1117"
TEXT = "#f0f6fc"
MUTED = "#8b949e"
BLUE = "#2f81f7"
GREEN = "#39d353"
GREEN_FILL = "#238636"
GRID = "#18304a"
BORDER = "#30363d"
PANEL = "#0a1523"

# Top-left stats panel
stats_title_x = 310
stats_left_x = 305
stats_label_x = 333
stats_value_x = 565
gh_cx = 700
gh_cy = 148

# Top-right activity overview
radar_cx = 1115
radar_cy = 175
radar_radius = 120

# Middle divider
divider_y = 322

# Bottom left metrics
left_metric_centers = [230, 470, 690]
metrics_top_y = 420
metrics_mid_y = 485
metrics_bottom_y = 525

# Bottom right graph
graph_x = 785
graph_y = 410
graph_width = 555
graph_height = 180

# ------------------------------------------------------------
# BUILD CONTRIBUTION GRAPH POINTS
# ------------------------------------------------------------
graph_points = []

for index, (_, contribution_count) in enumerate(last_days):
    x = graph_x + (graph_width * index / max(1, len(last_days) - 1))
    y = graph_y + graph_height - (contribution_count / max_count) * graph_height
    graph_points.append(f"{x:.1f},{y:.1f}")

# ------------------------------------------------------------
# BUILD RADAR / CROSS GRAPH POINTS
# ------------------------------------------------------------
# Directions:
# Commits = left
# Code review = top
# Issues = right
# Pull requests = bottom
radar_points = []

for _, percentage, angle_deg in [
    ("Commits", commit_pct, -180),
    ("Code review", review_pct, -90),
    ("Issues", issue_pct, 0),
    ("Pull requests", pr_pct, 90),
]:
    normalized = math.sqrt(max(0.0, min(percentage, 100.0)) / 100.0)
    radius = radar_radius * normalized
    angle = math.radians(angle_deg)

    x = radar_cx + math.cos(angle) * radius
    y = radar_cy + math.sin(angle) * radius
    radar_points.append(f"{x:.1f},{y:.1f}")

# ------------------------------------------------------------
# BUILD SVG
# ------------------------------------------------------------
svg = []

svg.append(
    f'''<svg xmlns="http://www.w3.org/2000/svg"
width="{WIDTH}"
height="{HEIGHT}"
viewBox="0 0 {WIDTH} {HEIGHT}"
role="img"
aria-labelledby="title desc">

<title id="title">{esc(profile_name)} GitHub dashboard</title>
<desc id="desc">GitHub statistics, activity overview, contribution streaks, and recent contribution activity.</desc>

<rect width="100%" height="100%" rx="14" fill="{BACKGROUND}" stroke="{BORDER}" stroke-width="2"/>

<style>
  text {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}

  .title {{
    fill: {BLUE};
    font-size: 22px;
    font-weight: 700;
  }}

  .label {{
    fill: #c9d1d9;
    font-size: 16px;
    font-weight: 600;
  }}

  .value {{
    fill: {TEXT};
    font-size: 17px;
    font-weight: 700;
  }}

  .big {{
    fill: {TEXT};
    font-size: 44px;
    font-weight: 700;
  }}

  .metric-title {{
    fill: {TEXT};
    font-size: 19px;
    font-weight: 700;
  }}

  .small {{
    fill: {GREEN};
    font-size: 14px;
    font-weight: 600;
  }}

  .axis {{
    fill: {BLUE};
    font-size: 10px;
  }}

  .radar-label {{
    fill: #c9d1d9;
    font-size: 18px;
    font-weight: 500;
  }}

  .radar-pct {{
    fill: {TEXT};
    font-size: 15px;
    font-weight: 700;
  }}
</style>
'''
)

# Soft panel backgrounds
svg.append(f'<rect x="55" y="35" width="620" height="240" rx="12" fill="{PANEL}" opacity="0.22"/>')
svg.append(f'<rect x="725" y="35" width="620" height="240" rx="12" fill="{PANEL}" opacity="0.22"/>')

# ------------------------------------------------------------
# TOP LEFT — GITHUB STATS
# ------------------------------------------------------------
svg.append(
    f'<text x="{stats_title_x}" y="62" class="title">'
    f'{esc(profile_name)}&#39;s GitHub Stats'
    f'</text>'
)

stats = [
    ("★", "Total Stars Earned:", stars),
    ("↻", "Commits (last year):", commits),
    ("⑂", "Pull Requests (last year):", pull_requests),
    ("◌", "Reviews (last year):", reviews),
    ("!", "Issues (last year):", issues),
    ("▣", "Repos contributed to:", repos_contributed),
]

stats_y = 98

for icon, label, value in stats:
    svg.append(
        f'<text x="{stats_left_x}" y="{stats_y}" fill="{BLUE}" font-size="18">{esc(icon)}</text>'
    )
    svg.append(
        f'<text x="{stats_label_x}" y="{stats_y}" class="label">{esc(label)}</text>'
    )
    svg.append(
        f'<text x="{stats_value_x}" y="{stats_y}" class="value">{value}</text>'
    )
    stats_y += 29

# GH ring
svg.append(
    f'<circle cx="{gh_cx}" cy="{gh_cy}" r="46" fill="none" stroke="#19324f" stroke-width="9"/>'
)
svg.append(
    f'<path d="M{gh_cx} {gh_cy-46} A46 46 0 0 1 {gh_cx+39} {gh_cy-20}" '
    f'fill="none" stroke="{BLUE}" stroke-width="9" stroke-linecap="round"/>'
)
svg.append(
    f'<text x="{gh_cx}" y="{gh_cy+8}" text-anchor="middle" fill="#c9d1d9" font-size="22" font-weight="700">GH</text>'
)

# ------------------------------------------------------------
# TOP RIGHT — ACTIVITY OVERVIEW
# ------------------------------------------------------------
svg.append(
    f'<text x="{radar_cx}" y="62" text-anchor="middle" class="title">Activity Overview</text>'
)

# Axis lines
svg.append(
    f'<line x1="{radar_cx-radar_radius}" y1="{radar_cy}" x2="{radar_cx+radar_radius}" y2="{radar_cy}" stroke="{GREEN}" stroke-width="2.2"/>'
)
svg.append(
    f'<line x1="{radar_cx}" y1="{radar_cy-radar_radius}" x2="{radar_cx}" y2="{radar_cy+radar_radius}" stroke="{GREEN}" stroke-width="2.2"/>'
)

# Filled polygon
svg.append(
    f'<polygon points="{" ".join(radar_points)}" fill="{GREEN_FILL}" fill-opacity="0.55" stroke="{GREEN}" stroke-width="2.4"/>'
)

# Center point
svg.append(
    f'<circle cx="{radar_cx}" cy="{radar_cy}" r="4" fill="{TEXT}" stroke="{GREEN}" stroke-width="2"/>'
)

# Data points
for point in radar_points:
    px, py = point.split(",")
    svg.append(
        f'<circle cx="{px}" cy="{py}" r="5" fill="{TEXT}" stroke="{GREEN}" stroke-width="2"/>'
    )

# Labels and percentages
svg.append(
    f'<text x="{radar_cx-radar_radius-30}" y="{radar_cy-8}" text-anchor="end" class="radar-pct">{commit_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx-radar_radius-30}" y="{radar_cy+15}" text-anchor="end" class="radar-label">Commits</text>'
)

svg.append(
    f'<text x="{radar_cx}" y="{radar_cy-radar_radius-18}" text-anchor="middle" class="radar-pct">{review_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx}" y="{radar_cy-radar_radius+6}" text-anchor="middle" class="radar-label">Code review</text>'
)

svg.append(
    f'<text x="{radar_cx+radar_radius+30}" y="{radar_cy-8}" class="radar-pct">{issue_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx+radar_radius+30}" y="{radar_cy+15}" class="radar-label">Issues</text>'
)

svg.append(
    f'<text x="{radar_cx}" y="{radar_cy+radar_radius+28}" text-anchor="middle" class="radar-label">Pull requests</text>'
)
svg.append(
    f'<text x="{radar_cx}" y="{radar_cy+radar_radius+52}" text-anchor="middle" class="radar-pct">{pr_pct:.0f}%</text>'
)

# ------------------------------------------------------------
# DIVIDER
# ------------------------------------------------------------
svg.append(
    f'<line x1="50" y1="{divider_y}" x2="1350" y2="{divider_y}" stroke="{BORDER}"/>'
)

# ------------------------------------------------------------
# BOTTOM LEFT — CONTRIBUTION METRICS
# ------------------------------------------------------------
for divider_x in [350, 590]:
    svg.append(
        f'<line x1="{divider_x}" y1="372" x2="{divider_x}" y2="548" stroke="{GREEN}" stroke-width="1.2"/>'
    )

# Total Contributions
svg.append(
    f'<text x="{left_metric_centers[0]}" y="{metrics_top_y}" text-anchor="middle" class="big">{total_contributions}</text>'
)
svg.append(
    f'<text x="{left_metric_centers[0]}" y="{metrics_mid_y}" text-anchor="middle" class="metric-title">Total Contributions</text>'
)

start_label = range_start_local.date().strftime("%b %d, %Y").replace(" 0", " ")
svg.append(
    f'<text x="{left_metric_centers[0]}" y="{metrics_bottom_y}" text-anchor="middle" class="small">{esc(start_label)} – Present</text>'
)

# Current Streak
current_center_x = left_metric_centers[1]
current_center_y = 416
current_radius = 50

svg.append(
    f'<circle cx="{current_center_x}" cy="{current_center_y}" r="{current_radius}" fill="none" stroke="#19324f" stroke-width="9"/>'
)

dash_amount = max(18, min(310, current_streak * 30))

svg.append(
    f'<circle cx="{current_center_x}" cy="{current_center_y}" r="{current_radius}" '
    f'fill="none" stroke="{BLUE}" stroke-width="9" stroke-linecap="round" '
    f'stroke-dasharray="{dash_amount} 330" transform="rotate(-90 {current_center_x} {current_center_y})"/>'
)

svg.append(
    f'<text x="{current_center_x}" y="{current_center_y + 13}" text-anchor="middle" class="big">{current_streak}</text>'
)
svg.append(
    f'<text x="{current_center_x}" y="{metrics_mid_y}" text-anchor="middle" class="metric-title">Current Streak</text>'
)
svg.append(
    f'<text x="{current_center_x}" y="{metrics_bottom_y}" text-anchor="middle" class="small">{esc(range_text(current_start, current_end))}</text>'
)

# Longest Streak
svg.append(
    f'<text x="{left_metric_centers[2]}" y="{metrics_top_y}" text-anchor="middle" class="big">{longest_streak}</text>'
)
svg.append(
    f'<text x="{left_metric_centers[2]}" y="{metrics_mid_y}" text-anchor="middle" class="metric-title">Longest Streak</text>'
)
svg.append(
    f'<text x="{left_metric_centers[2]}" y="{metrics_bottom_y}" text-anchor="middle" class="small">{esc(range_text(longest_start, longest_end))}</text>'
)

# ------------------------------------------------------------
# BOTTOM RIGHT — CONTRIBUTION GRAPH
# ------------------------------------------------------------
svg.append(
    f'<text x="{graph_x + graph_width / 2}" y="382" text-anchor="middle" class="title">{esc(profile_name)}&#39;s Contribution Graph</text>'
)

# Horizontal grid lines + y-axis labels
for index in range(6):
    horizontal_y = graph_y + graph_height - graph_height * index / 5
    axis_value = round(max_count * index / 5)

    svg.append(
        f'<line x1="{graph_x}" y1="{horizontal_y:.1f}" x2="{graph_x + graph_width}" y2="{horizontal_y:.1f}" '
        f'stroke="{GRID}" stroke-width="1" stroke-dasharray="2 3"/>'
    )
    svg.append(
        f'<text x="{graph_x - 14}" y="{horizontal_y + 3:.1f}" text-anchor="end" class="axis">{axis_value}</text>'
    )

# X-axis labels
for index in range(0, len(last_days), 5):
    x = graph_x + graph_width * index / max(1, len(last_days) - 1)
    day_label = last_days[index][0][-2:]

    svg.append(
        f'<text x="{x:.1f}" y="{graph_y + graph_height + 24}" text-anchor="middle" class="axis">{day_label}</text>'
    )

# Contribution line
svg.append(
    f'<polyline points="{" ".join(graph_points)}" fill="none" stroke="{BLUE}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
)

# Contribution points
for point, (_, contribution_count) in zip(graph_points, last_days):
    x, y = point.split(",")
    svg.append(
        f'<circle cx="{x}" cy="{y}" r="3.5" fill="{TEXT}"><title>{contribution_count} contributions</title></circle>'
    )

svg.append("</svg>")

# ------------------------------------------------------------
# WRITE SVG
# ------------------------------------------------------------
output_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "assets",
    "github-dashboard.svg",
)

os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "w", encoding="utf-8") as file:
    file.write("\n".join(svg))

print(f"Wrote {output_path}")
print(f"Local date used for streak: {local_today}")
print(f"Total contributions: {total_contributions}")
print(f"Restricted contributions visible to token: {restricted_contributions}")
print(f"Current streak: {current_streak}")
print(
    "Activity percentages: "
    f"commits={commit_pct:.1f}%, "
    f"reviews={review_pct:.1f}%, "
    f"issues={issue_pct:.1f}%, "
    f"pull_requests={pr_pct:.1f}%"
)
