import json, glob, os, statistics
rows = {}
for f in sorted(glob.glob('outputs/FR*_seed*_R_cbc120.json')):
    name = os.path.basename(f)[:-5]
    tag = name.split('_')[0]
    d = json.load(open(f, encoding='utf-8'))
    seed = d['seed']
    r = d['runs'][0]
    led = r.get('ledger') or {}
    diag = r.get('diag') or {}
    rows.setdefault(tag, {})[seed] = (led.get('profit'), led.get('coverage_pct'), led.get('services'), r.get('status'), diag.get('kept'), (led.get('reconciliation') or {}).get('flow_reoptimisation', {}).get('gain_usd'))
tags = ['FRprod', 'FRcov25', 'FRcov30', 'FRcov35', 'FRlex0', 'FRlex5', 'FRlex10']
print('seed | ' + ' | '.join(tags))
for s in (0, 1, 2):
    cells = []
    for t in tags:
        x = rows.get(t, {}).get(s)
        cells.append('-' if not x or x[0] is None else f'{x[0]/1e6:.2f}M {x[1]:.1f}% {x[2]}s {x[3][:4]} {x[4] or ""}')
    print(f'{s} | ' + ' | '.join(cells))
for t in tags:
    xs = [v for v in rows.get(t, {}).values() if v[0] is not None]
    if xs:
        print(f'{t:8s} n={len(xs)} profit mean {statistics.mean(v[0] for v in xs)/1e6:.2f} M, coverage mean {statistics.mean(v[1] for v in xs):.1f} %')
# reference: M3 R and M5 F1 on the same seeds
for tag, pat in (('M3 R (ctl3)', 'outputs/M3_seed{}_R_cbc120.json'), ('M5 F1 (ctl4)', 'outputs/M5_seed{}_F1_cbc120.json')):
    print(tag, [round(json.load(open(pat.format(s), encoding='utf-8'))['runs'][0]['ledger']['profit']/1e6, 2) for s in (0, 1, 2)])
