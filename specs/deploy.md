# Deploy — CI/CD to the Raspberry Pi

Trunk-based + tag-to-release + GHCR image + pull-based (Watchtower) deploy.
Defers to `constitution.md` for principles; this is the operational runbook.

## Pipeline

```
feature branch ─PR─▶ [CI: pytest + frontend build] ─(required, green)─▶ squash to main
                                                                              │
git tag vX.Y.Z ─push─▶ Release workflow:  test ─▶ build-push (needs: test)    │
                       buildx linux/arm64 ─▶ ghcr.io/ssarunic/job-search-assistant
                                                  :X.Y.Z  :sha-…  :latest      │
RPi: Watchtower polls GHCR ─▶ pulls :latest ─▶ recreates web + scraper ────────┘
     (.env with secrets lives only on the Pi; never in git / never on a runner)
```

**CI gate:** `build-push` `needs: test`, and `main` is branch-protected on the CI
check — so only tested code reaches a tag, and a failing build is never published.

## Cutting a release (from your laptop)

```bash
git checkout main && git pull
git tag v1.0.0 && git push origin v1.0.0      # triggers test -> build -> push to GHCR
```
Watchtower on the Pi picks up the new `:latest` within its poll interval (5 min).
Roll back by retagging an older image to `:latest`, or pin the Pi to `:vX.Y.Z`.

## One-time Pi setup (`ssarunic@dalstonserver`)

Docker + Compose + Tailscale are already installed. Then:

```bash
# 1. Auth to GHCR (PAT with read:packages scope; create at github.com/settings/tokens)
echo "$GHCR_PAT" | docker login ghcr.io -u ssarunic --password-stdin

# 2. Project dir + compose
mkdir -p ~/job-radar && cd ~/job-radar
#   copy deploy/docker-compose.yml here (scp from laptop or curl from the repo)

# 3. Secrets/config — create .env (NOT in git)
cat > .env <<'EOF'
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
WEB_BASE_URL=http://dalstonserver.tail824f04.ts.net:8765
ANTHROPIC_API_KEY=
EOF

# 4. Seed the store QUIETLY first (the web service has no webhook env, so no Slack
#    blast for the initial ~20 existing roles), then bring everything up.
docker compose run --rm web seek
docker compose --profile scheduler up -d        # web + daily scraper + watchtower
```

Reachable on the tailnet at **http://dalstonserver.tail824f04.ts.net:8765**.
The scheduler runs `seek` **daily at 08:00 Europe/London** (override with
`SEEK_AT=HH:MM` / `SEEK_TZ=Area/City` in `.env`), notifying Slack only on
genuinely new/reopened roles, each deep-linked to its detail page via `WEB_BASE_URL`.

## Branch protection (one-time, after the first CI run names the check)

```bash
gh api -X PUT repos/ssarunic/job-search-assistant/branches/main/protection \
  -F required_status_checks='{"strict":true,"contexts":["test"]}' \
  -F enforce_admins=false -F required_pull_request_reviews= -F restrictions=
```
