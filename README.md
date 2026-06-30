# Seguimiento del Leaderboard — "Domina tu Mundial" (KIA)

Registra automáticamente, cada día, el ranking público del concurso para ver cómo se
mueven los demás jugadores. Solo lee datos públicos (`/api/game/leaderboard`), sin login.

## Qué hace

- **`fetch.sh`** — descarga el leaderboard (top 100), guarda el snapshot crudo del día en
  `snapshots/AAAA-MM-DD.json` y acumula un histórico en `history.csv`
  (formato largo: `date,rank,name,score`). Es idempotente: si corre dos veces el mismo día,
  no duplica filas.
- **`analyze.py`** — resume el último día y, cuando haya ≥2 días, muestra cuánto subió cada
  jugador (`+día`) y cómo cambió su posición (`Δpos`), más la brecha con el líder traducida
  a kicks según el multiplicador de la semana.
- **`launchd`** (`~/Library/LaunchAgents/cl.kia.leaderboard.plist`) — corre `fetch.sh` solo
  cada día a las 09:00. El ranking se actualiza a las 00:00, así que a las 09:00 ya está fresco.

## Uso diario

```bash
# Ver el estado actual y los movimientos
python3 ~/kia-leaderboard/analyze.py

# Mostrar más puestos del top
python3 ~/kia-leaderboard/analyze.py --top 25

# Seguir tu propia posición y la brecha con el #1 (en kicks)
python3 ~/kia-leaderboard/analyze.py --me "Tu Apellido"
```

## Forzar una captura manual (sin esperar a las 09:00)

```bash
~/kia-leaderboard/fetch.sh
# o vía launchd:
launchctl start cl.kia.leaderboard
```

## Multiplicador por semana (de las bases, ya integrado en analyze.py)

| Semana | Fechas              | Pts/kick |
|--------|---------------------|----------|
| 1      | 08–14 jun           | 1        |
| 2      | 15–21 jun           | 2        |
| 3      | 22–28 jun           | 3        |
| 4      | 29 jun – 05 jul     | 4        |
| 5      | 06–12 jul           | 5        |
| 6      | 13–19 jul           | 10       |

## Detener / quitar el seguimiento automático

```bash
launchctl unload ~/Library/LaunchAgents/cl.kia.leaderboard.plist
rm ~/Library/LaunchAgents/cl.kia.leaderboard.plist   # eliminar del todo
```

Los datos ya capturados quedan en `history.csv` y `snapshots/` aunque desactives el job.

## Nota

El ranking es público según las bases del concurso (sección 7). Esto solo observa y archiva
esa información pública para análisis; no interactúa con el juego ni con tu cuenta.
