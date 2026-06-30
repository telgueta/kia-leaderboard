#!/usr/bin/env python3
"""
update.py — Actualiza artifact.html con los últimos datos de history.csv
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
DAYS_ES = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']
MONTHS_ES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

MOVE_FROM_RD = '2026-06-25'
MOVE_TO_RD = '2026-06-20'
MOVE_AMT = 498
CORR_RD = '2026-06-15'
CORR_AMT = 200
FLAGS_AD = ['2026-06-14']
SKIP_AD = ['2026-06-15', '2026-06-16', '2026-06-17']


def activity_date(rd):
    return (datetime.strptime(rd, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')


def mult_for(ad):
    week = (datetime.strptime(ad, '%Y-%m-%d') - WEEK1_START).days // 7
    return WEEK_MULTS[min(max(week, 0), len(WEEK_MULTS) - 1)]


def compute():
    rows = []
    with open(HIST) as f:
        for r in csv.DictReader(f):
            rows.append(r)

    rdates = sorted(set(r['date'] for r in rows))
    adates = [activity_date(rd) for rd in rdates]

    latest = rdates[-1]
    top = sorted(
        [(r['name'], int(r['rank']), int(r['score']))
         for r in rows if r['date'] == latest],
        key=lambda x: x[1])[:10]

    scores = {n: {} for n, _, _ in top}
    for r in rows:
        if r['name'] in scores:
            scores[r['name']][r['date']] = int(r['score'])

    players = []
    for name, rk, tot in top:
        gain, cum = [], []
        last = 0
        for rd in rdates:
            sc = scores[name].get(rd)
            if sc is None:
                gain.append(None)
                cum.append(None)
            else:
                gain.append(sc - last)
                cum.append(sc)
                last = sc

        p = dict(name=name, rk=rk, tot=tot, me=name == ME, gain=gain, cum=cum)

        if name == ME:
            if MOVE_FROM_RD in rdates and MOVE_TO_RD in rdates:
                fi, ti = rdates.index(MOVE_FROM_RD), rdates.index(MOVE_TO_RD)
                gain[ti] = (gain[ti] or 0) + MOVE_AMT
                gain[fi] -= MOVE_AMT
                run = 0
                for i in range(len(cum)):
                    if gain[i] is not None:
                        run += gain[i]
                        cum[i] = run

            gc = list(gain)
            ci = rdates.index(CORR_RD) if CORR_RD in rdates else None
            if ci is not None:
                gc[ci] = (gc[ci] or 0) + CORR_AMT
            cc, run = [], 0
            for g in gc:
                if g is not None:
                    run += g
                    cc.append(run)
                else:
                    cc.append(None)
            p['gainCorr'] = gc
            p['cumCorr'] = cc

        players.append(p)

    dates = []
    for ad in adates:
        d = datetime.strptime(ad, '%Y-%m-%d')
        dates.append(dict(n=str(d.day), w=DAYS_ES[d.weekday()]))

    mults = [mult_for(ad) for ad in adates]
    flags = [adates.index(a) for a in FLAGS_AD if a in adates]
    skip = [adates.index(a) for a in SKIP_AD if a in adates]

    me_p = next(p for p in players if p['me'])
    max_cum = me_p['cumCorr'][-1]

    return dict(dates=dates, mults=mults, players=players, max_cum=max_cum,
                flags=flags, skip=skip, latest=latest)


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
    lines.append('')
    lines.append('var P = [')
    for i, p in enumerate(d['players']):
        comma = ',' if i < len(d['players']) - 1 else ''
        me = 'true' if p['me'] else 'false'
        lines.append("  {name:'%s', rk:%d, tot:%d, me:%s," % (p['name'], p['rk'], p['tot'], me))
        lines.append('   cum:%s,' % jsa(p['cum']))
        if p['me']:
            lines.append('   gain:%s,' % jsa(p['gain']))
            lines.append('   cumCorr:%s,' % jsa(p['cumCorr']))
            lines.append('   gainCorr:%s}%s' % (jsa(p['gainCorr']), comma))
        else:
            lines.append('   gain:%s}%s' % (jsa(p['gain']), comma))
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

    with open(HTML_PATH, 'w') as f:
        f.write(html)

    print('%s: OK — #1 %s = %d | corregido = %d' % (
        d['latest'], d['players'][0]['name'], d['players'][0]['tot'], d['max_cum']))


if __name__ == '__main__':
    data = compute()
    update_html(data)
