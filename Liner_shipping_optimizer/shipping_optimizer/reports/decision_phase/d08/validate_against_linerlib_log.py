"""Validate the canal-fee rule against the LINERLIB authors' own best WorldSmall solution (primary-source output).
rule: fee = sum over the legs of the CLOSED rotation of (IsPanama x panamaFee + IsSuez x suezFee) of the class, once per weekly rotation."""
import re, sys, json
import pandas as pd
LOG = r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\results\BrouerDesaulniersPisinger2014\WorldSmall_Best_Base.log"
R = r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\data\raw\WorldSmall"
dist = pd.read_csv(R + r"\dist_dense.csv", sep="\t")
flag = {(r.fromUNLOCODe, r.ToUNLOCODE): (int(r.IsPanama), int(r.IsSuez)) for r in dist.itertuples()}
fl = pd.read_csv(R + r"\fleet_data.csv", sep="\t").set_index("Capacity FFE")
t = open(LOG, encoding="utf8", errors="replace").read()
blocks = re.split(r"\nservice \d+ service id \d+\n", t)[1:]
ok = bad = 0
tot_log = tot_rule = 0.0
unknown = []
for i, b in enumerate(blocks):
    cap = int(re.search(r"capacity (\d+)", b).group(1))
    ports = re.findall(r"^\d+\t(\w+)\t", b, flags=re.M)
    legs = list(zip(ports, ports[1:] + ports[:1]))
    pan = sum(flag.get(l, (0, 0))[0] for l in legs); sue = sum(flag.get(l, (0, 0))[1] for l in legs)
    lp = re.search(r"Panama canal traversed (\d+)", b); ls = re.search(r"Suez canal traversed (\d+)", b)
    lp = int(lp.group(1)) if lp else 0; ls = int(ls.group(1)) if ls else 0
    lc = re.search(r"Canal Cost ([\d.e+]+)", b); lc = float(lc.group(1)) if lc else 0.0
    pf = fl.loc[cap, "panamaFee"]; sf = fl.loc[cap, "suezFee"]
    rule = (pan * (0 if pd.isna(pf) else pf)) + sue * sf
    if pan and pd.isna(pf):
        unknown.append((i, cap, pan))
    same = (pan, sue) == (lp, ls) and abs(rule - lc) < 1.0
    ok += same; bad += (not same); tot_log += lc; tot_rule += rule
    if not same:
        print("MISMATCH service", i, cap, "rule", (pan, sue, rule), "log", (lp, ls, lc))
print(f"services {len(blocks)}  traversal counts and canal cost equal: {ok}  differ: {bad}")
print(f"sum canal cost: log {tot_log:,.0f}  rule {tot_rule:,.0f}   (log objective line: Canal costs 1.39351e+07)")
print("services using Panama with a blank fee (Post/Super-panamax):", unknown)
