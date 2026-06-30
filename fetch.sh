#!/bin/zsh
# Captura del leaderboard público de "Domina tu Mundial" (KIA).
# Datos públicos (el ranking es público según las bases). Solo lectura, sin login.
# Guarda el snapshot crudo del día + acumula un histórico long-format en history.csv.
#
# El ciclo del concurso gira en torno al reset del turno diario (~21:00). El leaderboard
# mantiene los números congelados dentro de un mismo día calendario, pero el refresh real
# puede ocurrir en el corte de las 21:00. Por eso: (a) se captura varias veces al día
# (incluyendo antes/después de las 21:00) y (b) si los datos de una fecha CAMBIAN entre
# capturas, se ACTUALIZA la fila en vez de ignorarla (antes solo saltaba si la fecha existía).

set -e
DIR="${KIA_DIR:-$(cd "$(dirname "$0")" && pwd)}"
SNAP="$DIR/snapshots"
HIST="$DIR/history.csv"
URL="https://dominatumundialkia.cl/api/game/leaderboard"
RAW="$DIR/.lb_tmp.json"

mkdir -p "$SNAP"

if ! curl -sfL "$URL" -H "Accept: application/json" -o "$RAW"; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: no se pudo descargar el leaderboard" >> "$DIR/fetch.log"
  exit 1
fi

python3 - "$RAW" "$SNAP" "$HIST" "$DIR/fetch.log" <<'PY'
import json, sys, os, csv, datetime

raw_path, snap_dir, hist_path, log_path = sys.argv[1:5]
with open(raw_path) as f:
    d = json.load(f)

updated = d.get("updatedAt") or ""
try:
    day = datetime.datetime.strptime(updated, "%d-%m-%Y").strftime("%Y-%m-%d")
except ValueError:
    day = datetime.date.today().isoformat()

entries = d.get("entries", [])
new_rows = [[day, e.get("rank"), e.get("name"), e.get("score")] for e in entries]

# Snapshot crudo del día (el último gana). Se guarda con marca de hora por si el dato
# cambia dentro del mismo día (corte 21:00) y queremos inspeccionar despues.
with open(os.path.join(snap_dir, f"{day}.json"), "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

# Leer histórico existente
rows = []
if os.path.exists(hist_path):
    with open(hist_path, newline="") as f:
        for r in csv.reader(f):
            if r and r[0] != "date":
                rows.append(r)

# ¿Qué teníamos para ESTE día?
old_for_day = [[r[0], int(r[1]), r[2], int(r[3])] for r in rows if r[0] == day]
new_norm    = [[r[0], int(r[1]), r[2], int(r[3])] for r in new_rows]

def key(r): return (r[1], r[2], r[3])   # (rank, name, score)
changed = sorted(map(key, old_for_day)) != sorted(map(key, new_norm))

if not old_for_day:
    action = "registrado (fecha nueva)"
elif changed:
    action = "ACTUALIZADO (los datos cambiaron)"
else:
    action = "sin cambios"

if not old_for_day or changed:
    # reconstruir: todas las filas de otras fechas + las nuevas de este día, ordenado
    rebuilt = [r for r in rows if r[0] != day] + [[str(c) for c in r] for r in new_rows]
    rebuilt.sort(key=lambda r: (r[0], int(r[1])))
    with open(hist_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "rank", "name", "score"])
        w.writerows(rebuilt)

leader = entries[0] if entries else {}
with open(log_path, "a") as f:
    f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} OK {day} {action} "
            f"| {len(entries)} jugadores | #1 {leader.get('name')} = {leader.get('score')}\n")
print(f"{day}: {action} — {len(entries)} jugadores — #1 {leader.get('name')} = {leader.get('score')}")
PY

rm -f "$RAW"
