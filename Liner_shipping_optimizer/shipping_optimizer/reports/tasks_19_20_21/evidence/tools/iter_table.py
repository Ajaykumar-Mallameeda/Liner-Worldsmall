import json, glob, os, statistics
rows = {}
for f in sorted(glob.glob('outputs/M9_seed*_cbc120.json')):
    d = json.load(open(f, encoding='utf-8'))
    var = os.path.basename(f).split('_')[2]
    its = d['runs']
    best = d.get('best') or {}
    rows.setdefault(var, {})[d['seed']] = (
        [r.get('profit') for r in its], [r.get('coverage_pct') for r in its], best.get('profit'), best.get('coverage_pct'), best.get('iteration'),
        [r.get('feedback_elites') for r in its], sum(r.get('violations') or 0 for r in its))
for var in sorted(rows):
    print('==', var)
    for s in sorted(rows[var]):
        p, c, bp, bc, bi, fe, vi = rows[var][s]
        print(' seed', s, 'iters', ['%.2f' % (x / 1e6) if x is not None else None for x in p], 'cov', ['%.1f' % x if x is not None else None for x in c],
              'best it%s %.2f M %.1f %%' % (bi, (bp or 0) / 1e6, bc or 0), 'elites', fe, 'viol', vi)
    bps = [v[2] for v in rows[var].values() if v[2] is not None]
    bcs = [v[3] for v in rows[var].values() if v[3] is not None]
    print(' mean best-of-3: profit %.2f M, coverage %.1f %% (n=%d)' % (statistics.mean(bps) / 1e6, statistics.mean(bcs), len(bps)))
base = rows.get('D', {})
for var in ('DEL', 'DELOP'):
    ds = [(rows[var][s][2] - base[s][2]) / 1e6 for s in rows.get(var, {}) if s in base and rows[var][s][2] is not None and base[s][2] is not None]
    if ds:
        print(var, 'vs D paired best-of-3 profit: mean %+.2f M, seeds better %d/%d' % (statistics.mean(ds), sum(1 for x in ds if x > 0), len(ds)))
