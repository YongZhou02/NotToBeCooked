#!/usr/bin/env bash
# Ship the current commit to the OCI VM. Run from the repo root on your machine:
#
#     deploy/deploy.sh
#
# What it does, in order -- each step stops the script if it fails:
#   1. build the web app with the production API URL baked in
#   2. push this commit to the VM's repo as branch `deploy` and check it out
#   3. uv sync + alembic upgrade head on the VM
#   4. copy the built web app to /srv/nttbc/web
#   5. restart the API, then check https://.../api/health
#
# It never touches apps/api/.env on the VM; secrets stay where they are.
set -euo pipefail

HOST="${DEPLOY_HOST:-149.118.140.61}"
ORIGIN="https://149-118-140-61.sslip.io"
REPO_ON_VM="/home/opc/NotToBeCooked"

cd "$(git rev-parse --show-toplevel)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean; commit or stash first." >&2
  exit 1
fi
COMMIT="$(git rev-parse --short HEAD)"

echo "[1/5] build web ($COMMIT)"
# Vite inlines VITE_API_URL at build time (Gantt r67): setting it after the
# build does nothing, so it is passed here, not on the VM.
VITE_API_URL="$ORIGIN/api" pnpm --filter web build

echo "[2/5] push $COMMIT to the VM"
# Pushed to a ref outside refs/heads: once `deploy` is checked out on the VM,
# git refuses a push to it ("branch is currently checked out"), which is what
# the second deploy on 10 Oct hit. -B then moves `deploy` to the new commit.
git push --force "ssh://opc@$HOST$REPO_ON_VM" HEAD:refs/deploy/incoming
ssh "opc@$HOST" "cd $REPO_ON_VM && git checkout --force -B deploy refs/deploy/incoming && git log --oneline -1"

echo "[3/5] dependencies and migrations"
ssh "opc@$HOST" "cd $REPO_ON_VM/apps/api && ~/.local/bin/uv sync --frozen && ~/.local/bin/uv run --no-sync alembic upgrade head"

echo "[4/5] web files"
rsync -a --delete apps/web/dist/ "opc@$HOST:/srv/nttbc/web/"

echo "[5/5] restart API"
ssh "opc@$HOST" "systemctl --user restart nttbc-api.service"
for _ in $(seq 1 30); do
  if curl -fsS "$ORIGIN/api/health" >/dev/null 2>&1; then
    echo "OK: $ORIGIN is serving $COMMIT"
    exit 0
  fi
  sleep 2
done
echo "API did not answer $ORIGIN/api/health within 60 s; see: ssh opc@$HOST journalctl --user -u nttbc-api -n 50" >&2
exit 1
