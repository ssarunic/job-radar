# Daily use

## The daily rhythm

Every morning (08:00 by default) JobRadar re-scans every company you follow.
If you set up Slack, you get one message per day: new roles (linked straight
into your dashboard), or a short "all quiet" heartbeat so you know it ran.

You can also scan any time with the **↻ Refresh** button in the top bar.

## The Jobs list

The home page lists every tracked role, most senior first. Filters at the top:

- **Status** — open / applied / rejected / suspected filled / closed
- **Min seniority** — hide everything below a rank
- **Search** — free text over company + title
- **Sort** — by seniority or by newest first

Click a role for the full ad text, captured the day it was found. Filters and
your scroll position live in the page URL, so opening a role and going back
returns you exactly where you were.

On the role page, **⧉ Copy Markdown** copies the whole role as plain Markdown
(all the facts, the ad text and your notes) — handy for pasting into Claude or
any AI assistant — and **⬇ .md** downloads the same thing as a file.

## Notes, "applied" and "rejected"

On a role's detail page you can **✓ Mark applied** (and unmark it),
**✕ Mark rejected** when an application didn't work out (this also adds a
dated "Rejected …" line to your notes; unmarking puts the role back to
applied) and **edit My notes** (Markdown supported). All of these are yours:
JobRadar never overwrites them, even if the ad changes or the posting closes —
an applied or rejected role keeps that status forever unless you change it.

Under the hood each role is a plain Markdown file in your data volume
(`jobs/<company>/<role>--<id>.md`) — notes live under `## My notes` and the
applied flag is `status: applied` in the frontmatter, so everything is equally
editable with a text editor if you prefer.

## What the statuses mean

- **open** — the role was on the company's board at the last scan.
- **suspected filled** — the role vanished from the board and stayed gone for
  two consecutive scans. Postings sometimes flicker (site errors, reposts), so
  one miss isn't enough.
- **closed** — still gone the scan after that. If it ever reappears on the
  board, it reopens automatically.
- **applied** — set by you (the "Mark applied" button); never changed
  automatically.
- **rejected** — set by you (the "Mark rejected" button) when a company turns
  your application down; never changed automatically, even if the ad is still
  up. Filter the list by "Rejected" to review them.

## The Companies page

Lists everyone you follow, with open-role counts. By default it shows only
companies that currently have matching roles — switch the filter to "All
companies" to see the rest. Unfollow keeps the company greyed-out with its
history rather than deleting anything.

## Activity

The Activity page is the run history: what every scan added, closed, or
reopened, so you can always answer "what changed and when".

## Settings

The Settings page shows the rules JobRadar is searching with: which roles
(minimum seniority, title words it skips), which locations (your home city,
the places you accept, whether remote roles count) and how many companies you
follow. It is read-only until you press **Edit**; **Save** keeps your changes
and **Cancel** discards them. Changes take effect from the next scan — roles
already on your list stay as they are. A few rarely-changed options are shown
there but set in a file; see [Configuration](configuration.md).
