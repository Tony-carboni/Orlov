#!/usr/bin/env bash
# Server, from cron on 10 and 11 November 2026 (owner's request, 2026-11-09): once ESI and EVE Ref know the four
# Fractured Skies navy attack battlecruisers, reload the Shipyard catalog, fill in their LP store offers and refresh.
# Runs at most once (marker file); every run logs to ~/logs/fractured-skies-bcs.log. Remove the cron lines afterwards.
set -u
cd "$HOME/aa-docker" || exit 1
MARKER="$HOME/aa-docker/.fractured_skies_bcs_done"
SCRIPTS="$HOME/aa-docker/scripts"
DC="docker compose --env-file=.env"
MANAGE="python /home/allianceauth/myauth/manage.py"
log() { echo "$(date -u '+%F %T') $*"; }

[ -f "$MARKER" ] && exit 0
log "checking ESI and EVE Ref"
if ! $DC exec -T allianceauth_gunicorn python -I - < "$SCRIPTS/fractured_skies_bcs_check.py"; then
  log "not ready yet"
  exit 0
fi

log "ready: backup, catalog reload, LP offers, refresh"
"$HOME/bin/aa-backup.sh" || { log "backup failed, stopping"; exit 1; }
$DC exec -T allianceauth_gunicorn $MANAGE shipyard_load_ships --no-seed || { log "shipyard_load_ships failed"; exit 1; }
$DC exec -T allianceauth_gunicorn $MANAGE shell < "$SCRIPTS/fractured_skies_bcs_add.py" | grep '^OUT' || { log "add script failed"; exit 1; }
$DC exec -T allianceauth_gunicorn $MANAGE shipyard_refresh || log "shipyard_refresh returned an error (the hourly beat task will catch up)"
touch "$MARKER"
log "done; the four ships are on the dashboard"
