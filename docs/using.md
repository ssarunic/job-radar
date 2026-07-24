# Daily use

## The daily rhythm

Every morning (08:00 by default) JobRadar re-scans every company you follow.
If you set up Slack, you get one message per day: new roles (linked straight
into your dashboard), or a short "all quiet" heartbeat so you know it ran.

You can also scan any time with the **↻ Refresh** button in the top bar.

## The Jobs list

The home page lists every tracked role, most senior first. Filters at the top:

- **Status** — open / applied / suspected filled / closed
- **Min seniority** — hide everything below a rank
- **Search** — free text over company + title
- **Sort** — by seniority or by newest first

Click a role for the full ad text, captured the day it was found. Filters and
your scroll position live in the page URL, so opening a role and going back
returns you exactly where you were.

## Notes and "applied"

Each role is a plain Markdown file in your data volume
(`jobs/<company>/<role>--<id>.md`). Two parts of it belong to you, and JobRadar
never overwrites them, even if the ad changes or closes:

- **`## My notes`** — free text; anything you write there is shown on the
  role's detail page.
- **`status: applied`** — set it in the file's frontmatter to mark a role
  applied; the applied status then shows in the UI's status filter.

Editing happens in the file for now (any text editor); the web UI displays
both but doesn't yet edit them.

## What the statuses mean

- **open** — the role was on the company's board at the last scan.
- **suspected filled** — the role vanished from the board and stayed gone for
  two consecutive scans. Postings sometimes flicker (site errors, reposts), so
  one miss isn't enough.
- **closed** — still gone the scan after that. If it ever reappears on the
  board, it reopens automatically.
- **applied** — set by you (in the role's file — see "Notes and applied"
  above); never changed automatically.

## The Companies page

Lists everyone you follow, with open-role counts. By default it shows only
companies that currently have matching roles — switch the filter to "All
companies" to see the rest. Unfollow keeps the company greyed-out with its
history rather than deleting anything.

## Activity

The Activity page is the run history: what every scan added, closed, or
reopened, so you can always answer "what changed and when".
