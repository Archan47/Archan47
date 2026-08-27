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

query = r'''
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


data = graphql(
    query,
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

days = []

for week in calendar["weeks"]:
    for day in week["contributionDays"]:
        days.append(
            (
                day["date"],
                int(day["contributionCount"]),
            )
        )

days.sort()

counts = {
    date_string: count
    for date_string, count in days
}

cursor = local_today

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

longest_streak = 0
longest_start = None
longest_end = None

run_length = 0
run_start = None

for date_string, contribution_count in days:
    day_date = datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).date()

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

repos = [
    repo
    for repo in data["repositories"]["nodes"]
    if not repo["isFork"]
]

stars = sum(
    int(repo["stargazerCount"])
    for repo in repos
)

language_bytes = {}
language_colors = {}

for repo in repos:
    for edge in repo["languages"]["edges"]:
        language_name = edge["node"]["name"]

        language_bytes[language_name] = (
            language_bytes.get(language_name, 0)
            + int(edge["size"])
        )

        if edge["node"].get("color"):
            language_colors[language_name] = edge["node"]["color"]

total_language_bytes = (
    sum(language_bytes.values()) or 1
)

top_languages = sorted(
    language_bytes.items(),
    key=lambda item: item[1],
    reverse=True,
)[:7]

profile_name = data.get("name") or USERNAME

total_contributions = int(
    calendar["totalContributions"]
)

restricted_contributions = int(
    contrib.get("restrictedContributionsCount") or 0
)

commits = int(
    contrib["totalCommitContributions"]
)

pull_requests = int(
    contrib["totalPullRequestContributions"]
)

reviews = int(
    contrib["totalPullRequestReviewContributions"]
)

issues = int(
    contrib["totalIssueContributions"]
)

repos_contributed = int(
    contrib["totalRepositoriesWithContributedCommits"]
)

# Dynamic activity overview: commits, code reviews, issues and pull requests.
activity_total = commits + reviews + issues + pull_requests
if activity_total <= 0:
    activity_total = 1

commit_pct = commits / activity_total * 100
review_pct = reviews / activity_total * 100
issue_pct = issues / activity_total * 100
pr_pct = pull_requests / activity_total * 100

last_days = days[-31:]

max_count = max(
    [count for _, count in last_days]
    + [1]
)


def esc(value):
    return html.escape(str(value))


def format_date(date_value):
    if not date_value:
        return "—"

    return date_value.strftime(
        "%b %d"
    ).replace(
        " 0",
        " ",
    )


def range_text(start_date, end_date):
    if not start_date or not end_date:
        return "—"

    return (
        f"{format_date(start_date)} – "
        f"{format_date(end_date)}"
    )


WIDTH = 1360
HEIGHT = 620

BACKGROUND = "#0d1117"
TEXT = "#f0f6fc"
MUTED = "#c9d1d9"
BLUE = "#2f81f7"
GREEN = "#39d353"
GRID = "#18304a"
BORDER = "#30363d"

graph_x = 780
graph_y = 382
graph_width = 525
graph_height = 145

graph_points = []

for index, (_, contribution_count) in enumerate(last_days):
    x = (
        graph_x
        + (
            graph_width
            * index
            / max(
                1,
                len(last_days) - 1,
            )
        )
    )

    y = (
        graph_y
        + graph_height
        - (
            contribution_count
            / max_count
        )
        * graph_height
    )

    graph_points.append(
        f"{x:.1f},{y:.1f}"
    )

svg = []

svg.append(
    f'''<svg xmlns="http://www.w3.org/2000/svg"
width="{WIDTH}"
height="{HEIGHT}"
viewBox="0 0 {WIDTH} {HEIGHT}"
role="img"
aria-labelledby="title desc">

<title id="title">{esc(profile_name)} GitHub dashboard</title>

<desc id="desc">
GitHub statistics, activity overview, contribution streaks,
and recent contribution activity.
</desc>

<rect
  width="100%"
  height="100%"
  rx="14"
  fill="{BACKGROUND}"
  stroke="{BORDER}"
  stroke-width="2"
/>

<style>
  text {{
    font-family:
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      sans-serif;
  }}

  .title {{
    fill: {BLUE};
    font-size: 18px;
    font-weight: 600;
  }}

  .label {{
    fill: {MUTED};
    font-size: 14px;
    font-weight: 600;
  }}

  .value {{
    fill: {TEXT};
    font-size: 15px;
    font-weight: 700;
  }}

  .big {{
    fill: {TEXT};
    font-size: 34px;
    font-weight: 700;
  }}

  .small {{
    fill: {GREEN};
    font-size: 13px;
  }}

  .axis {{
    fill: {BLUE};
    font-size: 9px;
  }}
</style>
'''
)

svg.append(
    f'<text x="350" y="56" class="title">'
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

stats_y = 84

for icon, label, value in stats:
    svg.append(
        f'<text x="350" y="{stats_y}" '
        f'fill="{BLUE}" font-size="18">'
        f'{esc(icon)}'
        f'</text>'
    )

    svg.append(
        f'<text x="378" y="{stats_y}" class="label">'
        f'{esc(label)}'
        f'</text>'
    )

    svg.append(
        f'<text x="590" y="{stats_y}" class="value">'
        f'{value}'
        f'</text>'
    )

    stats_y += 25

svg.append(
    '<circle cx="700" cy="126" r="43" '
    'fill="none" stroke="#19324f" stroke-width="8"/>'
)

svg.append(
    f'<path d="M700 83 A43 43 0 0 1 738 105" '
    f'fill="none" stroke="{BLUE}" stroke-width="8" '
    f'stroke-linecap="round"/>'
)

svg.append(
    f'<text x="700" y="134" text-anchor="middle" '
    f'fill="{MUTED}" font-size="22" font-weight="700">'
    f'GH'
    f'</text>'
)

# ------------------------------------------------------------
# TOP RIGHT — DYNAMIC ACTIVITY OVERVIEW
# ------------------------------------------------------------
radar_cx = 1015
radar_cy = 150
radar_radius = 88

# Axes match GitHub's activity overview style:
# left = commits, top = code review, right = issues, bottom = pull requests.
activity_axes = [
    ("Commits", commit_pct, 180),
    ("Code review", review_pct, -90),
    ("Issues", issue_pct, 0),
    ("Pull requests", pr_pct, 90),
]

radar_points = []
for _, percentage, angle_deg in activity_axes:
    # sqrt scaling keeps small categories visible while preserving ranking.
    scaled = math.sqrt(max(0.0, min(percentage, 100.0)) / 100.0)
    radius = radar_radius * scaled
    angle = math.radians(angle_deg)
    x = radar_cx + math.cos(angle) * radius
    y = radar_cy + math.sin(angle) * radius
    radar_points.append(f"{x:.1f},{y:.1f}")

svg.append(
    '<text x="1015" y="44" text-anchor="middle" class="title">'
    'Activity Overview'
    '</text>'
)

# Cross axes.
svg.append(
    f'<line x1="{radar_cx-radar_radius}" y1="{radar_cy}" '
    f'x2="{radar_cx+radar_radius}" y2="{radar_cy}" '
    f'stroke="{GREEN}" stroke-width="2"/>'
)
svg.append(
    f'<line x1="{radar_cx}" y1="{radar_cy-radar_radius}" '
    f'x2="{radar_cx}" y2="{radar_cy+radar_radius}" '
    f'stroke="{GREEN}" stroke-width="2"/>'
)

# Filled activity shape.
svg.append(
    f'<polygon points="{" ".join(radar_points)}" '
    f'fill="#238636" fill-opacity="0.55" '
    f'stroke="{GREEN}" stroke-width="2"/>'
)

# Center + data points.
svg.append(
    f'<circle cx="{radar_cx}" cy="{radar_cy}" r="4" '
    f'fill="{TEXT}" stroke="{GREEN}" stroke-width="2"/>'
)
for point in radar_points:
    px, py = point.split(",")
    svg.append(
        f'<circle cx="{px}" cy="{py}" r="4.5" '
        f'fill="{TEXT}" stroke="{GREEN}" stroke-width="2"/>'
    )

# Labels and percentages.
svg.append(
    f'<text x="{radar_cx-radar_radius-18}" y="{radar_cy-8}" '
    f'text-anchor="end" fill="{MUTED}" font-size="13">'
    f'{commit_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx-radar_radius-18}" y="{radar_cy+13}" '
    f'text-anchor="end" fill="{MUTED}" font-size="14">Commits</text>'
)

svg.append(
    f'<text x="{radar_cx}" y="{radar_cy-radar_radius-25}" '
    f'text-anchor="middle" fill="{MUTED}" font-size="13">'
    f'{review_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx}" y="{radar_cy-radar_radius-6}" '
    f'text-anchor="middle" fill="{MUTED}" font-size="14">Code review</text>'
)

svg.append(
    f'<text x="{radar_cx+radar_radius+18}" y="{radar_cy-8}" '
    f'fill="{MUTED}" font-size="13">{issue_pct:.0f}%</text>'
)
svg.append(
    f'<text x="{radar_cx+radar_radius+18}" y="{radar_cy+13}" '
    f'fill="{MUTED}" font-size="14">Issues</text>'
)

svg.append(
    f'<text x="{radar_cx}" y="{radar_cy+radar_radius+22}" '
    f'text-anchor="middle" fill="{MUTED}" font-size="14">Pull requests</text>'
)
svg.append(
    f'<text x="{radar_cx}" y="{radar_cy+radar_radius+42}" '
    f'text-anchor="middle" fill="{MUTED}" font-size="13">'
    f'{pr_pct:.0f}%</text>'
)

svg.append(
    f'<line x1="40" y1="285" x2="1320" y2="285" '
    f'stroke="{BORDER}"/>'
)

highlight_centers = [
    215,
    435,
    655,
]

for divider_x in [
    325,
    545,
]:
    svg.append(
        f'<line x1="{divider_x}" y1="340" '
        f'x2="{divider_x}" y2="520" '
        f'stroke="{GREEN}" stroke-width="1"/>'
    )

svg.append(
    f'<text x="{highlight_centers[0]}" y="400" '
    f'text-anchor="middle" class="big">'
    f'{total_contributions}'
    f'</text>'
)

svg.append(
    f'<text x="{highlight_centers[0]}" y="446" '
    f'text-anchor="middle" fill="{TEXT}" font-size="17">'
    f'Total Contributions'
    f'</text>'
)

start_label = (
    range_start_local
    .date()
    .strftime("%b %d, %Y")
    .replace(" 0", " ")
)

svg.append(
    f'<text x="{highlight_centers[0]}" y="484" '
    f'text-anchor="middle" class="small">'
    f'{esc(start_label)} – Present'
    f'</text>'
)

current_center_x = highlight_centers[1]
current_center_y = 396
current_radius = 48

svg.append(
    f'<circle cx="{current_center_x}" cy="{current_center_y}" '
    f'r="{current_radius}" fill="none" '
    f'stroke="#19324f" stroke-width="8"/>'
)

dash_amount = max(
    15,
    min(
        290,
        current_streak * 28,
    ),
)

svg.append(
    f'<circle cx="{current_center_x}" cy="{current_center_y}" '
    f'r="{current_radius}" fill="none" '
    f'stroke="{BLUE}" stroke-width="8" '
    f'stroke-linecap="round" '
    f'stroke-dasharray="{dash_amount} 320" '
    f'transform="rotate(-90 '
    f'{current_center_x} {current_center_y})"/>'
)

svg.append(
    f'<text x="{current_center_x}" '
    f'y="{current_center_y + 11}" '
    f'text-anchor="middle" class="big">'
    f'{current_streak}'
    f'</text>'
)

svg.append(
    f'<text x="{current_center_x}" y="474" '
    f'text-anchor="middle" fill="{TEXT}" '
    f'font-size="17" font-weight="700">'
    f'Current Streak'
    f'</text>'
)

svg.append(
    f'<text x="{current_center_x}" y="508" '
    f'text-anchor="middle" class="small">'
    f'{esc(range_text(current_start, current_end))}'
    f'</text>'
)

svg.append(
    f'<text x="{highlight_centers[2]}" y="400" '
    f'text-anchor="middle" class="big">'
    f'{longest_streak}'
    f'</text>'
)

svg.append(
    f'<text x="{highlight_centers[2]}" y="446" '
    f'text-anchor="middle" fill="{TEXT}" font-size="17">'
    f'Longest Streak'
    f'</text>'
)

svg.append(
    f'<text x="{highlight_centers[2]}" y="484" '
    f'text-anchor="middle" class="small">'
    f'{esc(range_text(longest_start, longest_end))}'
    f'</text>'
)

svg.append(
    f'<text x="{graph_x + graph_width / 2}" '
    f'y="340" text-anchor="middle" class="title">'
    f'{esc(profile_name)}&#39;s Contribution Graph'
    f'</text>'
)

for index in range(6):
    horizontal_y = (
        graph_y
        + graph_height
        - graph_height
        * index
        / 5
    )

    axis_value = round(
        max_count
        * index
        / 5
    )

    svg.append(
        f'<line x1="{graph_x}" y1="{horizontal_y:.1f}" '
        f'x2="{graph_x + graph_width}" '
        f'y2="{horizontal_y:.1f}" '
        f'stroke="{GRID}" stroke-width="1" '
        f'stroke-dasharray="2 3"/>'
    )

    svg.append(
        f'<text x="{graph_x - 12}" '
        f'y="{horizontal_y + 3:.1f}" '
        f'text-anchor="end" class="axis">'
        f'{axis_value}'
        f'</text>'
    )

for index in range(
    0,
    len(last_days),
    5,
):
    x = (
        graph_x
        + graph_width
        * index
        / max(
            1,
            len(last_days) - 1,
        )
    )

    day_label = last_days[index][0][-2:]

    svg.append(
        f'<text x="{x:.1f}" '
        f'y="{graph_y + graph_height + 22}" '
        f'text-anchor="middle" class="axis">'
        f'{day_label}'
        f'</text>'
    )

svg.append(
    f'<polyline '
    f'points="{" ".join(graph_points)}" '
    f'fill="none" '
    f'stroke="{BLUE}" '
    f'stroke-width="2.5" '
    f'stroke-linejoin="round" '
    f'stroke-linecap="round"/>'
)

for point, (_, contribution_count) in zip(
    graph_points,
    last_days,
):
    x, y = point.split(",")

    svg.append(
        f'<circle cx="{x}" cy="{y}" '
        f'r="3.3" fill="{TEXT}">'
        f'<title>{contribution_count} contributions</title>'
        f'</circle>'
    )

svg.append("</svg>")

output_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "assets",
    "github-dashboard.svg",
)

os.makedirs(
    os.path.dirname(output_path),
    exist_ok=True,
)

with open(
    output_path,
    "w",
    encoding="utf-8",
) as file:
    file.write("\n".join(svg))

print(f"Wrote {output_path}")
print(f"Local date used for streak: {local_today}")
print(f"Total contributions: {total_contributions}")
print(
    "Restricted contributions visible to token: "
    f"{restricted_contributions}"
)
print(f"Current streak: {current_streak}")
print(
    "Activity percentages: "
    f"commits={commit_pct:.1f}%, "
    f"reviews={review_pct:.1f}%, "
    f"issues={issue_pct:.1f}%, "
    f"pull_requests={pr_pct:.1f}%"
)
