#!/usr/bin/env bash
# Pipeline diario local (via launchd): fetch -> update -> commit+push a main.
# La rutina cloud de las 06:00 clona el repo ya al día y publica el artifact
# (la nube no puede pushear a main — solo el Mac tiene credenciales de escritura).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

./fetch.sh
python3 update.py > /dev/null

git add history.csv artifact.html snapshots/ 2>/dev/null
if ! git diff --cached --quiet; then
  git commit -m "data: $(date '+%Y-%m-%d %H:%M')" --quiet
  if ! git push --quiet origin main; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') WARN: git push falló (se reintenta en la próxima corrida)" >> fetch.log
  fi
fi
