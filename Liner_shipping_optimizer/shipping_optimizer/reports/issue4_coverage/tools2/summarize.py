import sys, pandas as pd
d = pd.read_csv(sys.argv[1]); base = sys.argv[2]
pd.set_option('display.width', 250)
agg = d.groupby('arm').agg(n=('seed','count'), profit_M=('profit_usd_wk', lambda s: s.mean()/1e6), pmin=('profit_usd_wk', lambda s: s.min()/1e6),
      pmax=('profit_usd_wk', lambda s: s.max()/1e6), margin=('margin_pct','mean'), cov=('coverage_pct','mean'), served=('served_teu','mean'),
      svc=('services','mean'), dep=('departures_per_week','mean'), ves=('vessels_used','mean'), idle=('idle_vessels','mean'), lf_leg=('load_factor_leg','mean'),
      lf_net=('load_factor_network','mean'), cps=('cost_per_served_teu','mean'), gap=('gap_pct','mean'), wall=('stage_wall_sec','mean'),
      p90=('transit_p90_max_d','max'), tviol=('transit_violations','sum'), lviol=('ledger_violations','sum'), valid=('ledger_valid','sum'))
print(agg.round(3).to_string())
b = d[d.arm == base].set_index('seed')
for a in sorted(set(d.arm) - {base}):
    x = d[d.arm == a].set_index('seed')
    dp = (x.profit_usd_wk - b.profit_usd_wk) / 1e6
    dc = x.coverage_pct - b.coverage_pct
    print(f"{a} - {base}: dProfit mean {dp.mean():+.2f} M (min {dp.min():+.2f}, max {dp.max():+.2f}), higher {int((dp>0).sum())}/{len(dp)}; dCov {dc.mean():+.2f} pp ({int((dc>0).sum())}/{len(dc)} higher)")
