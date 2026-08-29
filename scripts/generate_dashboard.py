#!/usr/bin/env python3

import os
import json
import html
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
    tzinfo=LOCAL_TZ
)

range_end_local = datetime.combine(
    local_today,
    time.max,
    tzinfo=LOCAL_TZ
)

range_start_utc = range_start_local.astimezone(timezone.utc)
range_end_utc = range_end_local.astimezone(timezone.utc)


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name

    contributionsCollection(from: $from, to: $to) {

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
  }
}
"""


def graphql(query, variables):

    body = json.dumps({
        "query": query,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Archan47-profile-dashboard"
        }
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]


data = graphql(
    QUERY,
    {
        "login": USERNAME,
        "from": range_start_utc.isoformat(),
        "to": range_end_utc.isoformat()
    }
)["user"]


profile_name = data.get("name") or USERNAME

calendar = (
    data["contributionsCollection"]
    ["contributionCalendar"]
)


# --------------------------------------------------
# CONTRIBUTION DAYS
# --------------------------------------------------

days = []

for week in calendar["weeks"]:

    for day in week["contributionDays"]:

        days.append(
            (
                day["date"],
                int(day["contributionCount"])
            )
        )


days.sort()

counts = {
    date: count
    for date, count in days
}


# --------------------------------------------------
# TOTAL CONTRIBUTIONS
# --------------------------------------------------

total_contributions = int(
    calendar["totalContributions"]
)


# --------------------------------------------------
# CURRENT STREAK
# --------------------------------------------------

cursor = local_today

# If no contribution today yet,
# keep checking from yesterday.
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


# --------------------------------------------------
# LONGEST STREAK
# --------------------------------------------------

longest_streak = 0

longest_start = None
longest_end = None

run = 0
run_start = None


for date_string, count in days:

    day_date = datetime.strptime(
        date_string,
        "%Y-%m-%d"
    ).date()

    if count > 0:

        if run == 0:
            run_start = day_date

        run += 1

        if run > longest_streak:

            longest_streak = run

            longest_start = run_start
            longest_end = day_date

    else:

        run = 0
        run_start = None


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def esc(value):
    return html.escape(str(value))


def format_date(value):

    if not value:
        return "—"

    return value.strftime(
        "%b %d"
    ).replace(
        " 0",
        " "
    )


def date_range(start, end):

    if not start or not end:
        return "—"

    return (
        f"{format_date(start)}"
        f" – "
        f"{format_date(end)}"
    )


# --------------------------------------------------
# CONTRIBUTION GRAPH
# --------------------------------------------------

last_days = days[-31:]

max_count = max(
    [count for _, count in last_days]
    + [1]
)


WIDTH = 1200
HEIGHT = 360


BACKGROUND = "#0d1117"
TEXT = "#f0f6fc"

BLUE = "#2f81f7"
GREEN = "#39d353"

GRID = "#18304a"
BORDER = "#30363d"


graph_x = 690
graph_y = 85

graph_width = 455
graph_height = 185


graph_points = []


for index, (_, count) in enumerate(last_days):

    x = (
        graph_x
        +
        graph_width
        * index
        / max(
            1,
            len(last_days) - 1
        )
    )

    y = (
        graph_y
        +
        graph_height
        -
        (
            count
            / max_count
        )
        * graph_height
    )

    graph_points.append(
        f"{x:.1f},{y:.1f}"
    )


# --------------------------------------------------
# SVG
# --------------------------------------------------

svg = []


svg.append(
    f"""
<svg
xmlns="http://www.w3.org/2000/svg"
width="{WIDTH}"
height="{HEIGHT}"
viewBox="0 0 {WIDTH} {HEIGHT}"
>

<rect
width="100%"
height="100%"
rx="12"
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

.big {{
fill:{TEXT};
font-size:36px;
font-weight:700;
}}

.label {{
fill:{TEXT};
font-size:15px;
font-weight:600;
}}

.date {{
fill:{GREEN};
font-size:11px;
}}

.title {{
fill:{BLUE};
font-size:17px;
font-weight:600;
}}

.axis {{
fill:{BLUE};
font-size:8px;
}}

</style>
"""
)


# --------------------------------------------------
# METRIC POSITIONS
# --------------------------------------------------

positions = [
    130,
    340,
    550
]


# separators

svg.append(
    f"""
<line
x1="235"
y1="65"
x2="235"
y2="285"
stroke="{GREEN}"
/>
"""
)


svg.append(
    f"""
<line
x1="445"
y1="65"
x2="445"
y2="285"
stroke="{GREEN}"
/>
"""
)


# --------------------------------------------------
# TOTAL CONTRIBUTIONS
# --------------------------------------------------

svg.append(
    f"""
<text
x="{positions[0]}"
y="130"
text-anchor="middle"
class="big"
>
{total_contributions}
</text>
"""
)


svg.append(
    f"""
<text
x="{positions[0]}"
y="180"
text-anchor="middle"
class="label"
>
Total Contributions
</text>
"""
)


start_label = (
    range_start_local
    .date()
    .strftime("%b %d, %Y")
    .replace(" 0", " ")
)


svg.append(
    f"""
<text
x="{positions[0]}"
y="220"
text-anchor="middle"
class="date"
>
{start_label} – Present
</text>
"""
)


# --------------------------------------------------
# CURRENT STREAK
# --------------------------------------------------

circle_x = positions[1]
circle_y = 120

radius = 45


svg.append(
    f"""
<circle
cx="{circle_x}"
cy="{circle_y}"
r="{radius}"
fill="none"
stroke="#19324f"
stroke-width="8"
/>
"""
)


dash = max(
    15,
    min(
        280,
        current_streak * 28
    )
)


svg.append(
    f"""
<circle
cx="{circle_x}"
cy="{circle_y}"
r="{radius}"
fill="none"
stroke="{BLUE}"
stroke-width="8"
stroke-linecap="round"
stroke-dasharray="{dash} 300"
transform="rotate(-90 {circle_x} {circle_y})"
/>
"""
)


svg.append(
    f"""
<text
x="{circle_x}"
y="{circle_y + 12}"
text-anchor="middle"
class="big"
>
{current_streak}
</text>
"""
)


svg.append(
    f"""
<text
x="{circle_x}"
y="205"
text-anchor="middle"
class="label"
>
Current Streak
</text>
"""
)


svg.append(
    f"""
<text
x="{circle_x}"
y="240"
text-anchor="middle"
class="date"
>
{date_range(current_start, current_end)}
</text>
"""
)


# --------------------------------------------------
# LONGEST STREAK
# --------------------------------------------------

svg.append(
    f"""
<text
x="{positions[2]}"
y="130"
text-anchor="middle"
class="big"
>
{longest_streak}
</text>
"""
)


svg.append(
    f"""
<text
x="{positions[2]}"
y="180"
text-anchor="middle"
class="label"
>
Longest Streak
</text>
"""
)


svg.append(
    f"""
<text
x="{positions[2]}"
y="220"
text-anchor="middle"
class="date"
>
{date_range(longest_start, longest_end)}
</text>
"""
)


# --------------------------------------------------
# CONTRIBUTION GRAPH TITLE
# --------------------------------------------------

svg.append(
    f"""
<text
x="{graph_x + graph_width / 2}"
y="45"
text-anchor="middle"
class="title"
>
{esc(profile_name)}'s Contribution Graph
</text>
"""
)


# --------------------------------------------------
# GRAPH GRID
# --------------------------------------------------

for index in range(6):

    y = (
        graph_y
        +
        graph_height
        -
        graph_height
        * index
        / 5
    )

    value = round(
        max_count
        * index
        / 5
    )

    svg.append(
        f"""
<line
x1="{graph_x}"
y1="{y}"
x2="{graph_x + graph_width}"
y2="{y}"
stroke="{GRID}"
stroke-dasharray="2 3"
/>
"""
    )

    svg.append(
        f"""
<text
x="{graph_x - 10}"
y="{y + 3}"
text-anchor="end"
class="axis"
>
{value}
</text>
"""
    )


# --------------------------------------------------
# X AXIS
# --------------------------------------------------

for index in range(
    0,
    len(last_days),
    5
):

    x = (
        graph_x
        +
        graph_width
        * index
        / max(
            1,
            len(last_days) - 1
        )
    )

    day = last_days[index][0][-2:]

    svg.append(
        f"""
<text
x="{x}"
y="{graph_y + graph_height + 22}"
text-anchor="middle"
class="axis"
>
{day}
</text>
"""
    )


# --------------------------------------------------
# GRAPH LINE
# --------------------------------------------------

svg.append(
    f"""
<polyline
points="{" ".join(graph_points)}"
fill="none"
stroke="{BLUE}"
stroke-width="2.5"
stroke-linejoin="round"
stroke-linecap="round"
/>
"""
)


# graph points

for point, (_, count) in zip(
    graph_points,
    last_days
):

    x, y = point.split(",")

    svg.append(
        f"""
<circle
cx="{x}"
cy="{y}"
r="3"
fill="{TEXT}"
>
<title>
{count} contributions
</title>
</circle>
"""
    )


svg.append("</svg>")


# --------------------------------------------------
# SAVE
# --------------------------------------------------

output = os.path.join(
    os.path.dirname(__file__),
    "..",
    "assets",
    "github-dashboard.svg"
)


os.makedirs(
    os.path.dirname(output),
    exist_ok=True
)


with open(
    output,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "\n".join(svg)
    )


print(
    f"Generated {output}"
)

print(
    f"Total contributions: {total_contributions}"
)

print(
    f"Current streak: {current_streak}"
)

print(
    f"Longest streak: {longest_streak}"
)
