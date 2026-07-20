#!/usr/bin/env python3
"""
update.py — Actualiza artifact.html con los últimos datos de history.csv

history.csv contiene la DATA CRUDA de la API (tal cual los snapshots).
Toda la corrección/normalización se aplica aquí al generar el artifact:

1. T. Elgueta (bespoke): movimientos puntuales conocidos + reclamo +200.
2. Rivales: la API a veces reporta en lote (días en 0 o negativos seguidos
   de un día gigante). Esos BLOQUES anómalos se redistribuyen en kicks
   interpolando desde los días contiguos reales. Los días con data real
   NO se tocan. Los días estimados se marcan (est) en el artifact.

Uso: python3 update.py
"""
import csv, re
from datetime import datetime, timedelta

import os as _os
DIR = _os.environ.get('KIA_DIR') or _os.path.dirname(_os.path.abspath(__file__))
HIST = f'{DIR}/history.csv'
HTML_PATH = f'{DIR}/artifact.html'

ME = 'T. Elgueta'
WEEK1_START = datetime(2026, 6, 8)
WEEK_MULTS = [1, 2, 3, 4, 5, 10]
CONTEST_END_AD = '2026-07-19'   # último día de actividad del concurso
DAYS_ES = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']
MONTHS_ES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

# ── Correcciones bespoke de T. Elgueta ──
# (from_report_date, to_report_date, puntos): mueve puntos entre jornadas.
MOVES = [
    ('2026-06-25', '2026-06-20', 498),    # refund retroactivo del 19 jun
    ('2026-07-01', '2026-07-02', 1138),   # split del lote 30 jun / 1 jul
]
CORR_RD = '2026-06-15'   # reclamo: +200 del 14 jun nunca registrado
CORR_AMT = 200
FLAGS_AD = ['2026-06-14']
SKIP_AD = ['2026-06-15', '2026-06-16', '2026-06-17']
ME_EST_AD = ['2026-06-30', '2026-07-01']  # días del split (estimados 50/50)

# Días de actividad ANULADOS por la organización (sanción, detectada 20 jul):
# el snapshot siguiente llegó en 0 y los puntos nunca se devolvieron.
# El 0 es real — NO se estima ni se redistribuye con el día siguiente.
SANCTION_AD = {
    'E. Torres':   ['2026-07-14'],
    'A. Madrid':   ['2026-07-14'],
    'F. madrid':   ['2026-07-14'],
    'P. Sanhueza': ['2026-07-15'],
}


def activity_date(rd):
    return (datetime.strptime(rd, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')


def mult_for(ad):
    week = (datetime.strptime(ad, '%Y-%m-%d') - WEEK1_START).days // 7
    return WEEK_MULTS[min(max(week, 0), len(WEEK_MULTS) - 1)]


def redistribute(scores, mults, sanc=()):
    """Redistribuye bloques anómalos (días sin data / gain<=0 + día de
    aterrizaje del lote) manteniendo intactos los días con data real.

    scores: lista de score acumulado (int) o None si el jugador no aparece
    ese día. sanc: índices anulados por sanción — su 0 es real y se
    preserva tal cual. Devuelve (gains, cums, est_idx).
    """
    n = len(scores)

    gain = [None] * n
    last = 0
    for i in range(n):
        if scores[i] is not None:
            gain[i] = scores[i] - last
            last = scores[i]

    lead = 0
    while lead < n and scores[lead] is None:
        lead += 1

    kick = [None if gain[i] is None else gain[i] / mults[i] for i in range(n)]

    # 1. Marcar anómalos: sin data o gain <= 0 (nunca el primer día observado,
    #    que acumula todo el arranque del concurso).
    anom = [False] * n
    for i in range(lead + 1, n):
        if (gain[i] is None or gain[i] <= 0) and i not in sanc:
            anom[i] = True

    # 2. Cada corrida anómala absorbe el siguiente día positivo (ahí aterrizó
    #    el lote acumulado).
    i = lead + 1
    while i < n:
        if anom[i]:
            j = i
            while j < n and anom[j]:
                j += 1
            if j < n and j not in sanc:
                anom[j] = True
            i = j + 1
        else:
            i += 1

    # Mediana de kicks de los días limpios (referencia global del jugador)
    clean = sorted(kick[i] for i in range(lead, n) if not anom[i] and kick[i] and kick[i] > 0)
    med = clean[len(clean) // 2] if clean else 100.0

    def blocks_from(marks):
        out, i = [], lead + 1
        while i < n:
            if marks[i]:
                s = i
                while i < n and marks[i]:
                    i += 1
                out.append((s, i - 1))
            else:
                i += 1
        return out

    def block_rate(s, e):
        base = scores[s - 1] if s > 0 and scores[s - 1] is not None else 0
        endv = None
        for j in range(e, s - 1, -1):
            if scores[j] is not None:
                endv = scores[j]
                break
        total = (endv - base) if endv is not None else 0
        w = sum(mults[s:e + 1])
        return total, (total / w if w else 0)

    # 3. Extensión hacia atrás: si el día previo al bloque es un spike
    #    (lote que llegó un día ANTES del zero), se incorpora al bloque.
    #    Condición doble: muy por sobre el rate del bloque Y sobre la mediana.
    changed = True
    while changed:
        changed = False
        for s, e in blocks_from(anom):
            p = s - 1
            if p <= lead or anom[p] or kick[p] is None:
                continue
            _, rate = block_rate(s, e)
            if kick[p] > 2 * max(rate, 1) and kick[p] > 1.5 * med:
                anom[p] = True
                changed = True

    # 4. Redistribuir cada bloque: rate objetivo interpolado entre los
    #    vecinos limpios, escalado para calzar EXACTO con el total oficial.
    est = [i for i in range(n) if anom[i]]
    new_scores = list(scores)

    for s, e in blocks_from(anom):
        base = new_scores[s - 1] if s > 0 and new_scores[s - 1] is not None else 0
        endv = None
        for j in range(e, s - 1, -1):
            if scores[j] is not None:
                endv = scores[j]
                break
        if endv is None or endv - base <= 0:
            # bloque sin puntos que repartir (jugador realmente inactivo):
            # rellenar plano para no dejar huecos
            for j in range(s, e + 1):
                new_scores[j] = base
            continue
        total = endv - base

        kb = ka = None
        for j in range(s - 1, lead - 1, -1):
            if not anom[j] and kick[j] is not None and kick[j] > 0:
                kb = kick[j]
                break
        for j in range(e + 1, n):
            if not anom[j] and kick[j] is not None and kick[j] > 0:
                ka = kick[j]
                break
        if kb is None and ka is None:
            kb = ka = med
        elif kb is None:
            kb = ka
        elif ka is None:
            ka = kb

        L = e - s + 1
        rates = [kb + (ka - kb) * (idx + 1) / (L + 1) for idx in range(L)]
        weight = sum(rates[idx] * mults[s + idx] for idx in range(L))
        scale = total / weight if weight else 0

        run = float(base)
        for idx in range(L - 1):
            run += rates[idx] * mults[s + idx] * scale
            new_scores[s + idx] = round(run)
        new_scores[e] = endv

    # Recalcular gains/cums finales
    gains, cums = [], []
    last = 0
    started = False
    for i in range(n):
        if new_scores[i] is None:
            gains.append(None)
            cums.append(None)
        else:
            gains.append(new_scores[i] - (last if started else 0))
            cums.append(new_scores[i])
            last = new_scores[i]
            started = True

    return gains, cums, est


def compute():
    rows = []
    with open(HIST) as f:
        for r in csv.DictReader(f):
            rows.append(r)

    rdates = sorted(set(r['date'] for r in rows))
    adates = [activity_date(rd) for rd in rdates]
    mults = [mult_for(ad) for ad in adates]

    latest = rdates[-1]
    top = sorted(
        [(r['name'], int(r['rank']), int(r['score']))
         for r in rows if r['date'] == latest],
        key=lambda x: x[1])[:25]

    # ranking completo de ayer (para detectar entradas al top 10 y movimientos)
    yranks = {}
    if len(rdates) >= 2:
        for r in rows:
            if r['date'] == rdates[-2]:
                yranks[r['name']] = int(r['rank'])

    scores = {n: {} for n, _, _ in top}
    for r in rows:
        if r['name'] in scores:
            scores[r['name']][r['date']] = int(r['score'])

    players = []
    for name, rk, tot in top:
        sc = [scores[name].get(rd) for rd in rdates]

        if name == ME:
            gain, cum = [], []
            last = 0
            for s in sc:
                if s is None:
                    gain.append(None)
                    cum.append(None)
                else:
                    gain.append(s - last)
                    cum.append(s)
                    last = s
            # Movimientos conocidos (aplican al registrado y al corregido)
            for frd, trd, amt in MOVES:
                if frd in rdates and trd in rdates:
                    fi, ti = rdates.index(frd), rdates.index(trd)
                    gain[ti] = (gain[ti] or 0) + amt
                    gain[fi] = (gain[fi] or 0) - amt
            run = 0
            for i in range(len(cum)):
                if gain[i] is not None:
                    run += gain[i]
                    cum[i] = run
            # Reclamo +200 (solo en el corregido)
            gc = list(gain)
            if CORR_RD in rdates:
                ci = rdates.index(CORR_RD)
                gc[ci] = (gc[ci] or 0) + CORR_AMT
            cc, run = [], 0
            for g in gc:
                if g is not None:
                    run += g
                    cc.append(run)
                else:
                    cc.append(None)
            est = [adates.index(a) for a in ME_EST_AD if a in adates]
            p = dict(name=name, rk=rk, tot=tot, me=True,
                     gain=gain, cum=cum, gainCorr=gc, cumCorr=cc, est=est,
                     sanc=[])
        else:
            sanc = [adates.index(a) for a in SANCTION_AD.get(name, ())
                    if a in adates]
            gain, cum, est = redistribute(sc, mults, sanc)
            p = dict(name=name, rk=rk, tot=tot, me=False,
                     gain=gain, cum=cum, est=est, sanc=sanc)

        players.append(p)

    dates = []
    for ad in adates:
        d = datetime.strptime(ad, '%Y-%m-%d')
        dates.append(dict(n=str(d.day), w=DAYS_ES[d.weekday()]))

    flags = [adates.index(a) for a in FLAGS_AD if a in adates]
    skip = [adates.index(a) for a in SKIP_AD if a in adates]

    # Días de actividad restantes del concurso (después del último dato)
    rem = []
    d = datetime.strptime(adates[-1], '%Y-%m-%d') + timedelta(days=1)
    end = datetime.strptime(CONTEST_END_AD, '%Y-%m-%d')
    while d <= end:
        ad = d.strftime('%Y-%m-%d')
        rem.append(dict(n=str(d.day), w=DAYS_ES[d.weekday()], m=mult_for(ad)))
        d += timedelta(days=1)

    me_p = next(p for p in players if p['me'])
    max_cum = me_p['cumCorr'][-1]

    return dict(dates=dates, mults=mults, players=players, max_cum=max_cum,
                flags=flags, skip=skip, latest=latest, rem=rem, yranks=yranks,
                adates=adates)


def gen_day_summary(d):
    """Genera el análisis de la última jornada: (items_html, items_texto)."""
    players = d['players']
    mults = d['mults']
    li = len(mults) - 1
    m = mults[li]
    yr = d['yranks']
    me = next(p for p in players if p['me'])
    rivals = [p for p in players if not p['me']]
    w_rem = sum(r['m'] for r in d['rem'])

    def kicks_series(p):
        g = p['gainCorr'] if p['me'] else p['gain']
        return [None if g[i] is None else g[i] / mults[i] for i in range(len(g))]

    def clean_med(p, upto):
        ks = kicks_series(p)
        v = sorted(k for i, k in enumerate(ks[:upto])
                   if k is not None and k > 0 and i not in p['est'])
        return v[len(v) // 2] if v else 0

    items = []  # (emoji, html, txt)

    # 1. Mi jornada
    ks_me = kicks_series(me)
    k_me = round(ks_me[li] or 0)
    prev7 = [k for k in ks_me[max(0, li - 7):li] if k is not None]
    avg7 = sum(prev7) / len(prev7) if prev7 else 0
    best_prev = max((k for i, k in enumerate(ks_me[:li])
                     if k is not None and i not in me['est'] and i not in d['skip']),
                    default=0)
    tag = ''
    if li not in me['est'] and k_me > best_prev:
        tag = ' — <b>nuevo récord personal</b>'
    elif avg7:
        pct = (k_me / avg7 - 1) * 100
        tag = ' (%+.0f%% vs tu promedio 7d de %d)' % (pct, round(avg7))
    items.append(('⚽', 'T&uacute;: <b>%d kicks</b> (+%s pts)%s' % (
        k_me, fmt_n(me['gainCorr'][li] or 0), tag),
        'Tú: %d kicks (+%d pts)%s' % (k_me, me['gainCorr'][li] or 0,
                                      tag.replace('<b>', '').replace('</b>', ''))))

    # 2. Brecha con el #2 y equivalente en kicks/día
    p2 = rivals[0]
    gap = me['tot'] - p2['tot']
    ygap = (me['cum'][li - 1] or 0) - (p2['cum'][li - 1] or 0) if li >= 1 else gap
    dgap = gap - ygap
    items.append(('🛡', 'Colch&oacute;n vs %s: <b>%s pts</b> (%s%s ayer) &mdash; equivale a %.1f kicks/d&iacute;a de margen' % (
        p2['name'], fmt_n(gap), '+' if dgap >= 0 else '', fmt_n(dgap), gap / w_rem if w_rem else 0),
        'Colchón vs %s: %d pts (%+d vs ayer) — %.1f kicks/día de margen' % (
        p2['name'], gap, dgap, gap / w_rem if w_rem else 0)))

    # 3. Rendimientos fuera de lo normal / récords / lotes
    hot = []
    for p in rivals:
        if p['rk'] > 12:  # el resumen narra la pelea de arriba; la tabla ya muestra 25
            continue
        ks = kicks_series(p)
        k = ks[li]
        if k is None:
            continue
        k = round(k)
        med = clean_med(p, li)
        best_prev = max((round(x) for i, x in enumerate(ks[:li])
                         if x is not None and i not in p['est'] and i not in d['skip']),
                        default=0)
        if li in p.get('sanc', ()):
            items.append(('⚖️', '%s: d&iacute;a <b>anulado por la organizaci&oacute;n</b> (sanci&oacute;n)' % p['name'],
                          '%s: día ANULADO por la organización (sanción)' % p['name']))
        elif li in p['est']:
            items.append(('📦', '%s recibi&oacute; <b>lote</b>: ~%d kicks/d&iacute;a estimados' % (p['name'], k),
                          '%s recibió lote: ~%d kicks/día estimados' % (p['name'], k)))
        elif k == 0:
            items.append(('👀', '%s report&oacute; <b>0</b> &mdash; atento a un lote ma&ntilde;ana' % p['name'],
                          '%s reportó 0 — atento a un lote mañana' % p['name']))
        elif k > best_prev * 1.05 and k > 200:
            items.append(('🚨', '<b>%s: r&eacute;cord personal</b> — %d kicks (su techo previo era %d, norma %d)' % (
                p['name'], k, best_prev, round(med)),
                '%s: RÉCORD personal — %d kicks (techo previo %d, norma %d)' % (p['name'], k, best_prev, round(med))))
        elif med and k > 1.18 * med:
            hot.append((k / med, p['name'], k, round(med)))

    hot.sort(reverse=True)
    for ratio, name, k, med in hot[:3]:
        pct = round((ratio - 1) * 100)
        sev = '🔥' if ratio <= 1.4 else '🚨'
        items.append((sev, '%s hizo <b>%d kicks</b>, +%d%% sobre su norma de %d' % (name, k, pct, med),
                      '%s hizo %d kicks, +%d%% sobre su norma de %d' % (name, k, pct, med)))
    if len(hot) > 3:
        rest = len(hot) - 3
        items.append(('📈', 'Jornada caliente: otros %d rivales tambi&eacute;n sobre su norma (+18%% o m&aacute;s)' % rest,
                      'Jornada caliente: otros %d rivales también sobre su norma' % rest))

    # 4. Movimientos en el top 10 y entradas nuevas
    for p in players:
        prev_rk = yr.get(p['name'])
        if prev_rk is None and yr and p['rk'] <= 10:
            items.append(('🆕', '<b>%s</b> entr&oacute; al top 10 (no estaba en el ranking ayer)' % p['name'],
                          '%s entró al top 10 (nuevo)' % p['name']))
        elif prev_rk is not None and prev_rk > 10 and p['rk'] <= 10:
            items.append(('🆕', '<b>%s</b> entr&oacute; al top 10 (era #%d ayer)' % (p['name'], prev_rk),
                          '%s entró al top 10 (era #%d)' % (p['name'], prev_rk)))
        elif prev_rk is not None and abs(prev_rk - p['rk']) >= 2 and not p['me'] \
                and min(p['rk'], prev_rk) <= 10:
            arrow = '&#9650;' if p['rk'] < prev_rk else '&#9660;'
            items.append(('↕️', '%s %s #%d &rarr; #%d' % (p['name'], arrow, prev_rk, p['rk']),
                          '%s: #%d → #%d' % (p['name'], prev_rk, p['rk'])))

    ad = datetime.strptime(d['adates'][-1], '%Y-%m-%d')
    head_html = 'Actividad del %d de %s (multiplicador &times;%d)' % (ad.day, MONTHS_ES[ad.month], m)
    head_txt = 'Actividad del %d de %s (x%d)' % (ad.day, MONTHS_ES[ad.month], m)

    html = '<p class="daysum-head">%s</p>\n  <ul class="daysum">\n' % head_html
    for emoji, h, _ in items[:9]:
        html += '    <li><span class="ds-ico">%s</span><span>%s</span></li>\n' % (emoji, h)
    html += '  </ul>'
    txt = head_txt + '\n' + '\n'.join('- %s' % t for _, _, t in items[:9])
    return html, txt


def fmt_n(n):
    return '{:,}'.format(n).replace(',', '.')


def jsa(arr):
    return '[' + ','.join('null' if v is None else str(v) for v in arr) + ']'


def gen_js(d):
    lines = []
    items = ["{n:'%s',w:'%s'}" % (x['n'], x['w']) for x in d['dates']]
    rows4 = [','.join(items[i:i + 4]) for i in range(0, len(items), 4)]
    lines.append('var DATES = [')
    for i, c in enumerate(rows4):
        lines.append('  ' + c + (',' if i < len(rows4) - 1 else ''))
    lines.append('];')
    lines.append('')
    lines.append('var MULT = %s;' % jsa(d['mults']))
    lines.append('var FLAGS = %s;' % jsa(d['flags']))
    lines.append('var SKIP_MAX = %s;' % jsa(d['skip']))
    ritems = ["{n:'%s',w:'%s',m:%d}" % (x['n'], x['w'], x['m']) for x in d['rem']]
    rrows = [','.join(ritems[i:i + 4]) for i in range(0, len(ritems), 4)]
    lines.append('var REM = [')
    for i, c in enumerate(rrows):
        lines.append('  ' + c + (',' if i < len(rrows) - 1 else ''))
    lines.append('];')
    lines.append('')
    lines.append('var P = [')
    for i, p in enumerate(d['players']):
        comma = ',' if i < len(d['players']) - 1 else ''
        me = 'true' if p['me'] else 'false'
        lines.append("  {name:'%s', rk:%d, tot:%d, me:%s," % (p['name'], p['rk'], p['tot'], me))
        lines.append('   cum:%s,' % jsa(p['cum']))
        lines.append('   gain:%s,' % jsa(p['gain']))
        if p['me']:
            lines.append('   cumCorr:%s,' % jsa(p['cumCorr']))
            lines.append('   gainCorr:%s,' % jsa(p['gainCorr']))
        lines.append('   est:%s, sanc:%s}%s' % (jsa(p['est']), jsa(p.get('sanc', [])), comma))
    lines.append('];')
    lines.append('')
    lines.append('var MAX_CUM = %d;' % d['max_cum'])
    return '\n'.join(lines)


def gen_pills(d):
    pills = []
    for p in d['players']:
        if not p['me'] and len(p['gain']) > 3 and p['gain'][3] is not None and p['gain'][3] > 0:
            short = p['name'].split('. ', 1)[-1] if '. ' in p['name'] else p['name']
            pills.append((short, p['gain'][3]))
    pills.sort(key=lambda x: -x[1])
    return '[' + ','.join("{n:'%s',v:%d}" % (n, v) for n, v in pills) + ']'


def update_html(d):
    with open(HTML_PATH) as f:
        html = f.read()

    dt = datetime.strptime(d['latest'], '%Y-%m-%d')
    date_str = '%d %s %d' % (dt.day, MONTHS_ES[dt.month], dt.year)
    html = re.sub(r'(<p class="date-tag">).*?(</p>)', r'\g<1>%s\g<2>' % date_str, html)

    me = next(p for p in d['players'] if p['me'])
    corr = me['cumCorr'][-1]
    cur_fmt = '{:,}'.format(me['tot']).replace(',', '.')
    cor_fmt = '{:,}'.format(corr).replace(',', '.')
    html = re.sub(r'(impact-card current.*?impact-score">)[\d.]+(\s*pts)',
                  r'\g<1>%s\2' % cur_fmt, html, count=1, flags=re.DOTALL)
    html = re.sub(r'(impact-card corrected.*?impact-score">)[\d.]+(\s*pts)',
                  r'\g<1>%s\2' % cor_fmt, html, count=1, flags=re.DOTALL)

    js_data = gen_js(d)
    html = re.sub(r'// __DATA_START__\n.*?// __DATA_END__',
                  '// __DATA_START__\n' + js_data + '\n// __DATA_END__',
                  html, flags=re.DOTALL)

    pills = gen_pills(d)
    html = re.sub(r"var d3=\[.*?\];", 'var d3=%s;' % pills, html)

    sum_html, sum_txt = gen_day_summary(d)
    html = re.sub(r'<!-- DAYSUM_START -->.*?<!-- DAYSUM_END -->',
                  '<!-- DAYSUM_START -->\n  ' + sum_html + '\n  <!-- DAYSUM_END -->',
                  html, flags=re.DOTALL)

    with open(HTML_PATH, 'w') as f:
        f.write(html)

    print('%s: OK — #1 %s = %d | corregido = %d' % (
        d['latest'], d['players'][0]['name'], d['players'][0]['tot'], d['max_cum']))
    print()
    print(sum_txt)


if __name__ == '__main__':
    data = compute()
    update_html(data)
