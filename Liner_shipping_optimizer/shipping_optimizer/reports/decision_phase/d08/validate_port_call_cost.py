import re, pandas as pd
LOG = r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\results\BrouerDesaulniersPisinger2014\WorldSmall_Best_Base.log"
D = r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\data\raw\WorldSmall"
ports = pd.read_csv(D + r"\ports.csv", sep="\t").set_index("UNLocode")
t = open(LOG, encoding="utf8", errors="replace").read()
blocks = re.split(r"\nservice \d+ service id \d+\n", t)[1:]
ok = 0; tot_log = tot_cap = tot_zero = 0.0
for i, b in enumerate(blocks):
    cap = int(re.search(r"capacity (\d+)", b).group(1))
    pl = [x for x in re.findall(r"^\d+\t(\w+)\t", b, flags=re.M)]
    log = float(re.search(r"Port call cost ([\d.e+]+)", b).group(1))
    cap_based = sum(ports.loc[p, "PortCallCostFixed"] + ports.loc[p, "PortCallCostPerFFE"] * cap for p in pl)
    fixed_only = sum(ports.loc[p, "PortCallCostFixed"] for p in pl)
    tot_log += log; tot_cap += cap_based; tot_zero += fixed_only
    ok += abs(cap_based - log) <= 0.01 * log
print(f"services {len(blocks)}; capacity-based rule (fixed + perFFE x capacity per call) within 1 percent: {ok}")
print(f"sum port call cost: log {tot_log:,.0f}  capacity-based rule {tot_cap:,.0f}  fixed-only {tot_zero:,.0f}  (objective line 5.56584e+06)")
