#!/usr/bin/env python3
"""Analiza el histórico del leaderboard de 'Domina tu Mundial'.

Uso:
    python3 analyze.py            # resumen del último día + movimientos
    python3 analyze.py --top 20   # cambia cuántos del top mostrar
    python3 analyze.py --me "Mi Nombre"   # sigue tu propia posición
"""
import csv, sys, os
from collections import defaultdict

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.csv")

# Multiplicador de puntos por kick según semana (de las bases)
WEEKS = [
    ("2026-06-08", "2026-06-14", 1),
    ("2026-06-15", "2026-06-21", 2),
    ("2026-06-22", "2026-06-28", 3),
    ("2026-06-29", "2026-07-05", 4),
    ("2026-07-06", "2026-07-12", 5),
    ("2026-07-13", "2026-07-19", 10),
]

def week_mult(day):
    for a, b, m in WEEKS:
        if a <= day <= b:
            return m
    return None

def load():
    rows = []
    if not os.path.exists(HIST):
        sys.exit("No hay history.csv todavía. Corre fetch.sh primero.")
    with open(HIST, newline="") as f:
        for r in csv.DictReader(f):
            r["rank"] = int(r["rank"]); r["score"] = int(r["score"])
            rows.append(r)
    return rows

def main():
    top_n = 15
    me = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])
        if a == "--me" and i + 1 < len(args):
            me = args[i + 1]

    rows = load()
    days = sorted({r["date"] for r in rows})
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)

    last = days[-1]
    mult = week_mult(last)
    print(f"=== Leaderboard al {last}  (semana actual: x{mult} pts/kick) ===\n")

    cur = sorted(by_day[last], key=lambda r: r["rank"])
    # mapa nombre->score del día anterior para deltas
    prev = {r["name"]: r["score"] for r in by_day[days[-2]]} if len(days) >= 2 else {}
    prev_rank = {r["name"]: r["rank"] for r in by_day[days[-2]]} if len(days) >= 2 else {}

    print(f"{'#':>3} {'Jugador':<22} {'Pts':>6} {'+día':>6} {'Δpos':>5}")
    for r in cur[:top_n]:
        d = r["score"] - prev[r["name"]] if r["name"] in prev else None
        dp = prev_rank[r["name"]] - r["rank"] if r["name"] in prev_rank else None
        ds = f"+{d}" if d is not None else "—"
        dps = (f"+{dp}" if dp > 0 else str(dp)) if dp is not None else "—"
        star = "  <- TÚ" if me and me.lower() in r["name"].lower() else ""
        print(f"{r['rank']:>3} {r['name'][:22]:<22} {r['score']:>6} {ds:>6} {dps:>5}{star}")

    leader = cur[0]
    print(f"\nLíder: {leader['name']} con {leader['score']} pts.")

    if len(days) >= 2:
        # ganancia diaria del líder (y promedio top 10) para proyectar
        gains = [r["score"] - prev[r["name"]] for r in cur[:10] if r["name"] in prev]
        gains = [g for g in gains if g >= 0]
        if gains:
            print(f"Ganancia de hoy — líder: +{cur[0]['score']-prev.get(cur[0]['name'],cur[0]['score'])} | "
                  f"promedio top10: +{sum(gains)//len(gains)}")

    if me:
        mine = next((r for r in cur if me.lower() in r["name"].lower()), None)
        if mine:
            gap = leader["score"] - mine["score"]
            kicks_hoy = -(-gap // mult)  # ceil
            print(f"\nTU POSICIÓN: #{mine['rank']} con {mine['score']} pts.")
            if mine["name"] in prev:
                dme = mine["score"] - prev[mine["name"]]
                pr = prev_rank.get(mine["name"])
                mov = f"  (#{pr} → #{mine['rank']})" if pr else ""
                print(f"Tu cambio desde ayer: +{dme} pts{mov}")
            print(f"Brecha con el #1: {gap} pts = ~{kicks_hoy} kicks a x{mult} (valor de esta semana).")
            if mult < 10:
                print(f"En la última semana (x10) esa misma brecha serían ~{-(-gap//10)} kicks.")
        else:
            print(f"\n'{me}' no aparece en el top 100 todavía.")

    print(f"\n({len(days)} día(s) registrados: {days[0]} → {days[-1]})")

if __name__ == "__main__":
    main()
