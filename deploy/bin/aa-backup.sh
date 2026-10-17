#!/bin/bash
# Nightly Alliance Auth backup (runbook 04 A; cron 03:30). Keeps 14 days in ~/backups:
#   aa-db-<stamp>.sql.gz      every database (auth, the plugins, grafana's metadata)
#   aa-config-<stamp>.tgz     .env, conf/, docker-compose.yml, the Discord bot (orlovbot/), the alliance
#                             site (alliance-site/) and ~/bin (this script), plus the crontab
#   aa-proxy-<stamp>.tgz      Nginx Proxy Manager: its proxy hosts (proxy-data) and the Let's Encrypt
#                             certificates (proxy-le), read straight from the two Docker volumes
# Installed copy: ~/bin/aa-backup.sh on the server. Source of truth: deploy/bin/aa-backup.sh in the repo.
set -e
cd "$HOME/aa-docker"
mkdir -p "$HOME/backups"
stamp=$(date +%F-%H%M)
docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > "$HOME/backups/aa-db-$stamp.sql.gz"
crontab -l > "$HOME/aa-docker/crontab.txt" 2>/dev/null || true
tar czf "$HOME/backups/aa-config-$stamp.tgz" --exclude=__pycache__ .env conf docker-compose.yml orlovbot alliance-site crontab.txt -C "$HOME" bin
docker run --rm -v aa-docker_proxy-data:/proxy-data:ro -v aa-docker_proxy-le:/proxy-le:ro -v "$HOME/backups":/out alpine tar czf "/out/aa-proxy-$stamp.tgz" -C / proxy-data proxy-le
find "$HOME/backups" -name 'aa-*' -mtime +14 -delete
echo "$(date '+%F %T') backup ok: aa-db-$stamp.sql.gz"
