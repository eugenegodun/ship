#!/usr/bin/env bash
# Install the ship pipeline's Codex agent roles.
#
# Codex plugins cannot bundle custom agent roles, so the TOMLs in
# plugins/ship/codex-agents/ are copied into a Codex agents directory.
#
#   install-codex-agents.sh              copy into ${CODEX_HOME:-$HOME/.codex}/agents
#   install-codex-agents.sh --to DIR     copy into DIR (e.g. <repo>/.codex/agents)
#   install-codex-agents.sh --check      write nothing; exit 1 if any role is missing or stale
#
# Output: one line per role - "installed", "updated", "unchanged", or (check mode) "missing/stale".
# Exit codes: 0 all in place, 1 drift found (--check), 2 bad arguments.
# Re-run after every plugin update; restart the Codex session so it reloads the roles.
set -euo pipefail

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../codex-agents" && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/agents"
CHECK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --to) [ $# -ge 2 ] || { usage >&2; exit 2; }; DEST="$2"; shift 2 ;;
    --check) CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

status=0
for src in "$SRC"/ship-*.toml; do
  name="$(basename "$src")"
  dest="$DEST/$name"
  if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
    echo "unchanged  $name"
    continue
  fi
  if [ "$CHECK" = 1 ]; then
    echo "missing/stale  $name"
    status=1
    continue
  fi
  mkdir -p "$DEST"
  if [ -f "$dest" ]; then verb="updated"; else verb="installed"; fi
  cp "$src" "$dest"
  echo "$verb  $name -> $dest"
done

if [ "$CHECK" = 1 ] && [ "$status" != 0 ]; then
  echo "run: bash $SRC/../scripts/install-codex-agents.sh" >&2
fi
exit "$status"
