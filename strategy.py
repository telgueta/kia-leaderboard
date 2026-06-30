#!/usr/bin/env python3
"""Plan estratégico: proyección de kicks y brecha al #1.

Uso:
    python3 strategy.py                          # proyección estándar
    python3 strategy.py --correction 200         # sumar pts que faltan a tu score
    python3 strategy.py --target-gap 0           # llegar empatado al inicio de x10
    python3 strategy.py --played-today            # ya jugaste hoy (no contar hoy como día futuro)
"""
import csv, os, sys
from collections import defaultdict

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.csv")

WEEKS = [
    ("2026-06-08", "2026-06-14", 1),
    ("2026-06-15", "2026-06-21", 2),
    ("2026-06-22", "2026-06-28", 3),
    ("2026-06-29", "2026-07-05", 4),
    ("2026-07-06", "2026-07-12", 5),
    ("2026-07-13", "2026-07-19", 10),
]

ME = "T. Elgueta"
LEADER = "A. Niccodemi"
X1_END = "2026-06-14"

def week_mult(day):
    for a, b, m in WEEKS:
        if a <= day <= b:
            return m
    return None

def remaining_schedule(after_date):
    """Días de juego restantes agrupados por semana/multiplicador."""
    from datetime import date, timedelta
    d = date.fromisoformat(after_date) + timedelta(days=1)
    end = date.fromisoformat("2026-07-19")
    schedule = []
    for wa, wb, mult in WEEKS:
        wa_d, wb_d = date.fromisoformat(wa), date.fromisoformat(wb)
        days_in_range = 0
        cur = max(d, wa_d)
        while cur <= min(end, wb_d):
            days_in_range += 1
            cur += timedelta(days=1)
        if days_in_range > 0:
            schedule.append((f"x{mult}", mult, days_in_range, str(wa_d), str(wb_d)))
    return schedule

def load():
    rows = []
    with open(HIST, newline="") as f:
        for r in csv.DictReader(f):
            r["rank"] = int(r["rank"])
            r["score"] = int(r["score"])
            rows.append(r)
    return rows

def player_score_on(by_day, name, day):
    for r in by_day.get(day, []):
        if r["name"] == name:
            return r["score"]
    return None

def estimate_total_kicks(score_x1_end, score_latest):
    """Total kicks estimados desde el inicio del concurso.

    x1 period: score = kicks (1 pt/kick)
    x2+ period (Jun 18 corregido): kicks = (score_latest - score_x1_end) / 2

    Esto funciona porque el score de Jun 18 tiene la corrección retroactiva.
    """
    kicks_x1 = score_x1_end or 0
    kicks_x2 = max(0, (score_latest - (score_x1_end or 0)) / 2)
    return kicks_x1, kicks_x2

def main():
    correction = 0
    played_today = False
    target_gap = None

    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--correction" and i + 1 < len(args):
            correction = int(args[i + 1])
        if a == "--played-today":
            played_today = True
        if a == "--target-gap" and i + 1 < len(args):
            target_gap = int(args[i + 1])

    rows = load()
    days = sorted({r["date"] for r in rows})
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)

    latest = days[-1]
    mult_now = week_mult(latest)

    # --- Scores ---
    me_latest = player_score_on(by_day, ME, latest)
    leader_latest = player_score_on(by_day, LEADER, latest)
    me_x1 = player_score_on(by_day, ME, X1_END)
    leader_x1 = player_score_on(by_day, LEADER, X1_END)

    if me_latest is None or leader_latest is None:
        sys.exit(f"No encuentro a {ME} o {LEADER} en el día {latest}.")

    me_real = me_latest + correction

    # --- Kicks totales ---
    me_kicks_x1, me_kicks_x2 = estimate_total_kicks(me_x1, me_real)
    ld_kicks_x1, ld_kicks_x2 = estimate_total_kicks(leader_x1, leader_latest)

    me_total_kicks = me_kicks_x1 + me_kicks_x2
    ld_total_kicks = ld_kicks_x1 + ld_kicks_x2

    # Días en cada período
    # x1: Jun 8-14 = 7 días
    # x2: Jun 15-latest
    from datetime import date
    x1_days = 7
    x2_days = (date.fromisoformat(latest) - date.fromisoformat("2026-06-14")).days
    if played_today:
        x2_days_played = x2_days
    else:
        x2_days_played = x2_days

    me_rate_x1 = me_kicks_x1 / x1_days if x1_days else 0
    me_rate_x2 = me_kicks_x2 / x2_days if x2_days else 0
    ld_rate_x1 = ld_kicks_x1 / x1_days if x1_days else 0
    ld_rate_x2 = ld_kicks_x2 / x2_days if x2_days else 0

    gap_pts = leader_latest - me_real
    gap_kicks = ld_total_kicks - me_total_kicks

    # --- Schedule restante ---
    after = latest if played_today else days[-1]
    schedule = remaining_schedule(after if played_today else
                                  # si no jugaste hoy, hoy cuenta como restante
                                  str(date.fromisoformat(latest) - __import__('datetime').timedelta(days=1)))

    total_remaining_days = sum(s[2] for s in schedule)
    pre_x10_days = sum(s[2] for s in schedule if s[1] < 10)
    x10_days = sum(s[2] for s in schedule if s[1] == 10)

    # --- Proyección si ambos mantienen su ritmo actual ---
    def project_score(current_score, kicks_per_day, sched):
        score = current_score
        for _, mult, ndays, _, _ in sched:
            score += kicks_per_day * mult * ndays
        return score

    me_projected = project_score(me_real, me_rate_x2, schedule)
    ld_projected = project_score(leader_latest, ld_rate_x2, schedule)

    # --- ¿Cuántas kicks/día extra necesitas? ---
    # Para cerrar el gap ANTES de x10:
    pre_x10_sched = [(n, m, d, a, b) for n, m, d, a, b in schedule if m < 10]
    pre_x10_weighted = sum(m * d for _, m, d, _, _ in pre_x10_sched)

    if pre_x10_weighted > 0:
        # extra kicks/día para cerrar gap completo antes de x10
        extra_for_zero = gap_pts / pre_x10_weighted
        # extra kicks/día para llegar con gap de target_gap antes de x10
        if target_gap is not None:
            extra_for_target = (gap_pts - target_gap) / pre_x10_weighted if gap_pts > target_gap else 0
    else:
        extra_for_zero = 0
        extra_for_target = 0

    # Durante x10: ¿cuántas kicks/día para cerrar el gap que quede?
    if x10_days > 0:
        kicks_x10_close = gap_pts / (10 * x10_days)
    else:
        kicks_x10_close = float('inf')

    # --- Escenarios: qué pasa si haces X kicks/día más que el líder ---
    scenarios_extra = [5, 10, 20, 30, 50]

    # --- Output ---
    print("=" * 65)
    print(f"  ESTRATEGIA KIA — {latest} (semana x{mult_now})")
    print("=" * 65)

    print(f"\n{'':>3}{'':>20}{'Score':>8}{'Kicks':>8}{'k/día x1':>10}{'k/día x2':>10}")
    print(f"{'#1':<3}{LEADER:<20}{leader_latest:>8}{ld_total_kicks:>8.0f}{ld_rate_x1:>10.0f}{ld_rate_x2:>10.0f}")
    me_label = f"{ME}" + (f" (+{correction})" if correction else "")
    print(f"{'#5':<3}{me_label:<20}{me_real:>8}{me_total_kicks:>8.0f}{me_rate_x1:>10.0f}{me_rate_x2:>10.0f}")
    print(f"\n  Brecha actual: {gap_pts} pts = {gap_kicks:.0f} kicks de diferencia acumulada")
    if correction:
        print(f"  (score oficial {me_latest} + {correction} corrección = {me_real})")

    print(f"\n--- Ritmo actual (semana x2: Jun 15-{latest}) ---")
    diff_rate = me_rate_x2 - ld_rate_x2
    if diff_rate > 0:
        print(f"  TÚ: {me_rate_x2:.0f} kicks/día  |  LÍDER: {ld_rate_x2:.0f} kicks/día")
        print(f"  -> Vas {diff_rate:.0f} kicks/día POR ENCIMA del líder")
    else:
        print(f"  TÚ: {me_rate_x2:.0f} kicks/día  |  LÍDER: {ld_rate_x2:.0f} kicks/día")
        print(f"  -> Vas {abs(diff_rate):.0f} kicks/día POR DEBAJO del líder")

    print(f"\n--- Calendario restante ({total_remaining_days} días) ---")
    print(f"  {'Semana':<8}{'Mult':>5}{'Días':>6}{'Rango':>25}")
    for name, mult, ndays, start, end in schedule:
        print(f"  {name:<8}{f'x{mult}':>5}{ndays:>6}   {start} → {end}")
    print(f"  {'TOTAL':<8}{'':>5}{total_remaining_days:>6}")
    print(f"  Pre-x10: {pre_x10_days} días  |  x10: {x10_days} días")

    print(f"\n--- Proyección al 19 de julio (manteniendo ritmo actual) ---")
    print(f"  Líder ({ld_rate_x2:.0f} k/día): {ld_projected:,.0f} pts")
    print(f"  Tú    ({me_rate_x2:.0f} k/día): {me_projected:,.0f} pts")
    gap_final = ld_projected - me_projected
    if gap_final > 0:
        print(f"  -> Aún te faltan {gap_final:,.0f} pts al final")
    else:
        print(f"  -> LO PASAS por {abs(gap_final):,.0f} pts al final!")

    print(f"\n--- ¿Cuántas kicks/día EXTRA necesitas sobre el líder? ---")
    print(f"  Para cerrar {gap_pts} pts de brecha:")
    print(f"")
    print(f"  Opción A — Cerrar TODO antes de x10 ({pre_x10_days} días):")
    print(f"    +{extra_for_zero:.1f} kicks/día sobre el líder = {ld_rate_x2 + extra_for_zero:.0f} kicks/día tuyas")
    print(f"")
    print(f"  Opción B — Dejar que x10 cierre la brecha ({x10_days} días):")
    print(f"    Si llegas con los mismos {gap_pts} pts: +{kicks_x10_close:.1f} kicks/día en x10")
    print(f"    (eso es {ld_rate_x2 + kicks_x10_close:.0f} kicks/día tuyas en esa semana)")

    print(f"\n--- Escenarios: kicks/día extra sobre líder ---")
    print(f"  {'Extra k/día':>12}{'Pts cerrados pre-x10':>22}{'Gap al iniciar x10':>20}{'k/día en x10':>14}")
    for extra in scenarios_extra:
        pts_closed_pre = extra * pre_x10_weighted
        gap_at_x10 = max(0, gap_pts - pts_closed_pre)
        kicks_in_x10 = gap_at_x10 / (10 * x10_days) if x10_days > 0 and gap_at_x10 > 0 else 0
        status = "PASADO" if gap_at_x10 == 0 else f"{gap_at_x10:.0f} pts"
        k10 = f"+{kicks_in_x10:.0f}" if gap_at_x10 > 0 else "0 :)"
        print(f"  +{extra:>10}  {pts_closed_pre:>20,.0f}  {status:>20}  {k10:>12}")

    print(f"\n--- Resumen para llegar relajado a x10 ---")
    target = 100  # llegar con <=100 pts de gap
    if pre_x10_weighted > 0:
        extra_relaxed = max(0, (gap_pts - target) / pre_x10_weighted)
    else:
        extra_relaxed = 0
    total_relaxed = ld_rate_x2 + extra_relaxed
    kicks_in_x10_relaxed = target / (10 * x10_days) if x10_days > 0 else 0
    print(f"  Meta: llegar a x10 con <= {target} pts de brecha")
    print(f"  Necesitas: +{extra_relaxed:.1f} kicks/día sobre el líder")
    print(f"  = {total_relaxed:.0f} kicks/día totales tuyas (líder hace ~{ld_rate_x2:.0f})")
    print(f"  En x10 cierras esos {target} pts con solo +{kicks_in_x10_relaxed:.1f} kicks/día extra")

    # Nota sobre turno doble
    print(f"\n--- Nota sobre el 'turno doble' ---")
    print(f"  El turno se reinicia a las ~21:00. Los promedios de kicks/día")
    print(f"  se calculan sobre ventanas de varios días, así que el efecto")
    print(f"  de jugar antes/después del reset se diluye en el promedio.")
    print(f"  Cada jugador tiene 1 turno real por ciclo de 24h.")

    # Top 5 kick rates
    print(f"\n--- Kick rates del Top 10 actual (semana x2) ---")
    top10 = sorted(by_day[latest], key=lambda r: r["rank"])[:10]
    print(f"  {'#':>3} {'Jugador':<22}{'Score':>7}{'Kicks x2':>10}{'k/día':>8}")
    for r in top10:
        s14 = player_score_on(by_day, r["name"], X1_END)
        if s14 is not None:
            kx2 = (r["score"] - s14) / 2
        else:
            # player wasn't in top 100 on Jun 14, estimate from first appearance
            kx2 = None
        rate = kx2 / x2_days if kx2 is not None and x2_days > 0 else None
        kx2_s = f"{kx2:.0f}" if kx2 is not None else "?"
        rate_s = f"{rate:.0f}" if rate is not None else "?"
        print(f"  {r['rank']:>3} {r['name']:<22}{r['score']:>7}{kx2_s:>10}{rate_s:>8}")

    print()

if __name__ == "__main__":
    main()
