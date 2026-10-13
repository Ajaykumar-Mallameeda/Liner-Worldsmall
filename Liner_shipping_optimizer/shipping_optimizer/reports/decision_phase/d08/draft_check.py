import re, json, glob
import pandas as pd
R = r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer"
D = R + r"\data\raw\WorldSmall"
dist = pd.read_csv(D + r"\dist_dense.csv", sep="\t")
edge_draft = {(r.fromUNLOCODe, r.ToUNLOCODE): float(r.Draft) for r in dist.itertuples()}
port_draft = pd.read_csv(D + r"\ports.csv", sep="\t").set_index("UNLocode").Draft.to_dict()
fl = pd.read_csv(D + r"\fleet_data.csv", sep="\t")
cls_draft = {r["Vessel class"]: float(r["draft"]) for r in fl.to_dict("records")}
cap_draft = {int(r["Capacity FFE"]): float(r["draft"]) for r in fl.to_dict("records")}
print("class drafts", cls_draft)
print("edge draft distribution:", pd.Series(list(edge_draft.values())).describe().round(1).to_dict())
def violations(ports, d):
    legs = list(zip(ports, ports[1:] + ports[:1]))
    e = [l for l in legs if edge_draft.get(l, 99) < d]
    p = [x for x in ports if port_draft.get(x, 99) < d]
    return e, p
# 1. authors' solution
t = open(r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\results\BrouerDesaulniersPisinger2014\WorldSmall_Best_Base.log", encoding="utf8", errors="replace").read()
blocks = re.split(r"\nservice \d+ service id \d+\n", t)[1:]
nv = 0
for b in blocks:
    cap = int(re.search(r"capacity (\d+)", b).group(1)); ports = re.findall(r"^\d+\t(\w+)\t", b, flags=re.M)
    e, p = violations(ports, cap_draft[cap]); nv += bool(e or p)
print(f"authors' best base solution: {len(blocks)} services, with an edge/port draft violation: {nv}")
# 2. our recorded plans
for f in sorted(glob.glob(R + r"\reports\issue8_final\paired\outputs\F_*_seed*.json"))[:40]:
    sel = json.load(open(f))["runs"][-1]["selected"]
    n = 0; ex = None
    for s in sel:
        e, p = violations(list(s["ports"]), cls_draft[s["class"]])
        if e or p:
            n += 1; ex = ex or (s["id"], s["class"], e[:2], p[:2])
    print(f.split("\\")[-1], "services", len(sel), "with draft violation", n, ex if n else "")
