# Deploy — CI/CD to the Raspberry Pi

> **Status: live.** Running on `dalstonserver` (arm64) since 2026-06-29, currently
> **v1.1.0**. Daily 08:00 Europe/London scrape → Slack. Reachable on the tailnet at
> http://dalstonserver.tail824f04.ts.net:8765.

Trunk-based + tag-to-release + GHCR image + push-based (GitHub Actions over
Tailscale SSH) deploy. Defers to `constitution.md` for principles; this is the
operational runbook.

## Pipeline

```
feature branch ─PR─▶ [CI: ruff + pytest + eslint + frontend build] ─(required, green)─▶ squash to main
                                                                              │
git tag vX.Y.Z ─push─▶ Release workflow:  test ─▶ build-push (needs: test)    │
                       buildx linux/arm64 ─▶ ghcr.io/ssarunic/job-radar
                                                  :X.Y.Z  :sha-…  :latest      │
                          ─▶ deploy (needs: build-push): join tailnet ─▶ ssh   │
RPi:                          Pi `docker compose pull && up -d`  ◀─────────────┘
     (.env with secrets lives only on the Pi; never in git / never on a runner)
```

**Deploy is push-based** (the `deploy` job): the instant the image is in GHCR, the
runner joins the tailnet and SSHes into the Pi to `pull && up -d`, so a tag deploys
within seconds with no poll lag. There is **no Watchtower** — if the Pi is offline
when a tag builds, the `deploy` job fails; re-run it once the Pi is back
(`gh run rerun <run-id> --failed`) or push a new tag.

**CI gate:** `build-push` `needs: test`, `deploy` `needs: build-push`, and `main`
is branch-protected on the CI check — so only tested code reaches a tag, a failing
build is never published, and only a published image is ever deployed.

## Cutting a release (from your laptop)

```bash
git checkout main && git pull
git tag v1.0.0 && git push origin v1.0.0      # triggers test -> build -> push to GHCR
```
The `deploy` job copies the current `deploy/docker-compose.yml` to the Pi, then
SSHes in to `pull && up -d` within seconds of the image being published — so both
image changes and compose-level changes (new services, image swaps) deploy.
Roll back by retagging an older image to `:latest`, or pin the Pi to `:vX.Y.Z`.

## Push-based deploy (one-time secrets setup)

The `deploy` job needs three repo secrets (Settings → Secrets and variables →
Actions). Once set, every `vX.Y.Z` tag auto-deploys to the Pi.

1. **Tailscale OAuth client** — at <https://login.tailscale.com/admin/settings/oauth>,
   create a client with the **`devices:write`** scope (the GitHub Action joins an
   ephemeral, tagged node). Add the tag `tag:ci` to your tailnet ACL and grant it
   SSH/`:22` access to `dalstonserver`, e.g.:
   ```jsonc
   "tagOwners": { "tag:ci": ["autogroup:admin"] },
   "acls": [ { "action": "accept", "src": ["tag:ci"], "dst": ["dalstonserver:22"] } ]
   ```
   Store the client id/secret as `TS_OAUTH_CLIENT_ID` / `TS_OAUTH_SECRET`.

2. **Deploy SSH key** — generate a dedicated keypair, add the **public** key to the
   Pi and the **private** key as the `PI_SSH_KEY` secret:
   ```bash
   ssh-keygen -t ed25519 -f deploy_key -N '' -C 'gh-actions-deploy'
   ssh-copy-id -i deploy_key.pub "$DEPLOY_TARGET"   # or append to ~/.ssh/authorized_keys
   gh secret set PI_SSH_KEY < deploy_key
   gh secret set TS_OAUTH_CLIENT_ID   # paste when prompted
   gh secret set TS_OAUTH_SECRET
   rm deploy_key deploy_key.pub
   ```

If MagicDNS resolution flakes on the runner, replace `dalstonserver` in the
`deploy` job with the Pi's stable tailnet IP (`100.64.162.62`).

## One-time Pi setup (the `DEPLOY_TARGET` box)

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
docker compose --profile scheduler up -d        # web + daily scraper
```

Reachable on the tailnet at **http://dalstonserver.tail824f04.ts.net:8765**.
The scheduler runs `seek` **daily at 08:00 Europe/London** (override with
`SEEK_AT=HH:MM` / `SEEK_TZ=Area/City` in `.env`), notifying Slack only on
genuinely new/reopened roles, each deep-linked to its detail page via `WEB_BASE_URL`.

## Branch protection (one-time, after the first CI run names the check)

```bash
gh api -X PUT repos/ssarunic/job-radar/branches/main/protection \
  -F required_status_checks='{"strict":true,"contexts":["test"]}' \
  -F enforce_admins=false -F required_pull_request_reviews= -F restrictions=
```
