/**
 * transshipment.js — where the plan's cargo changes ship, what it costs and between which services, from the run's
 * routed flows (network_ledger.plan.flows: segments [service, from, to]) and the dataset's port tariffs.
 *
 *   a transfer       = the port between two consecutive segments of a flow (cargo leaves one service, boards the next)
 *   transfer moves   = Σ flow TEU × transfers on its path (two transfers = two moves)
 *   cost at a hub    = moves there × the port's transshipment_cost per TEU
 *
 * This is the engine ledger's own rule (src/network/ledger.py: L.transshipment_cost += teu × port.transshipment_cost
 * for every transfer port), so the hubs sum to network_ledger.weekly_usd.transshipment_cost; `check` reports both.
 * Without tariffs (backend offline) the TEU side is complete and the per-hub cost is null.
 */

const n = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);

/**
 * flows: ledger flows; tariffs: { CODE: { transshipment_cost, name } } or null; ledgerCost: the ledger's weekly
 * transshipment cost (null when unknown); servicesById: Map id → service (for vessel class / region), optional.
 */
export function transshipmentModel({ flows = [], tariffs = null, ledgerCost = null } = {}) {
  const hubs = new Map();
  const pairs = new Map();
  const lanes = [];
  let servedTeu = 0; let transferTeu = 0; let moves = 0; let flowsWithTransfer = 0;
  let oneTransfer = 0; let twoPlus = 0; let cost = tariffs ? 0 : null;
  const hubOf = (code) => {
    if (!hubs.has(code)) {
      const t = tariffs?.[code];
      hubs.set(code, { code, name: t?.name || null, teu: 0, flows: 0, costPerTeu: t ? n(t.transshipment_cost) : null, cost: t ? 0 : null,
        pairs: new Map(), lanes: [], services: new Set() });
    }
    return hubs.get(code);
  };

  flows.forEach((f) => {
    const teu = n(f.teu);
    if (teu <= 0) return;
    servedTeu += teu;
    const segs = Array.isArray(f.segments) ? f.segments : [];
    if (segs.length < 2) return;
    flowsWithTransfer += 1;
    transferTeu += teu;
    if (segs.length === 2) oneTransfer += teu; else twoPlus += teu;
    const via = [];
    let laneCost = tariffs ? 0 : null;
    for (let k = 0; k < segs.length - 1; k++) {
      const [inSvc, , at] = segs[k];
      const outSvc = segs[k + 1][0];
      const h = hubOf(at);
      via.push(at);
      moves += teu;
      h.teu += teu; h.flows += 1;
      h.services.add(String(inSvc)); h.services.add(String(outSvc));
      const pk = `${inSvc}→${outSvc}`;
      h.pairs.set(pk, { from: String(inSvc), to: String(outSvc), teu: (h.pairs.get(pk)?.teu || 0) + teu });
      const gk = `${at}|${pk}`;
      pairs.set(gk, { hub: at, from: String(inSvc), to: String(outSvc), teu: (pairs.get(gk)?.teu || 0) + teu });
      if (tariffs) {
        const c = teu * (h.costPerTeu || 0);
        h.cost += c; cost += c; laneCost += c;
      }
    }
    const lane = { o: f.origin, d: f.destination, teu, via, services: segs.map((s) => String(s[0])), cost: laneCost };
    lanes.push(lane);
    via.forEach((code) => hubs.get(code).lanes.push(lane));
  });

  const hubList = [...hubs.values()].map((h) => ({
    ...h,
    services: [...h.services].sort(),
    pairs: [...h.pairs.values()].sort((a, b) => b.teu - a.teu),
    lanes: h.lanes.sort((a, b) => b.teu - a.teu),
    shareOfMoves: moves ? (h.teu / moves) * 100 : 0,
    shareOfCost: cost ? ((h.cost || 0) / cost) * 100 : null,
  })).sort((a, b) => b.teu - a.teu || a.code.localeCompare(b.code));

  const top3 = hubList.slice(0, 3).reduce((a, h) => a + h.teu, 0);
  return {
    hubs: hubList,
    pairs: [...pairs.values()].sort((a, b) => b.teu - a.teu),
    lanes: lanes.sort((a, b) => b.teu - a.teu),
    totals: {
      servedTeu, transferTeu, directTeu: servedTeu - transferTeu, moves, flows: flowsWithTransfer,
      share: servedTeu ? (transferTeu / servedTeu) * 100 : 0,
      oneTransfer, twoPlus, hubs: hubList.length,
      top3Share: moves ? (top3 / moves) * 100 : 0,
      cost, costPerMove: cost != null && moves ? cost / moves : null,
    },
    check: { computed: cost, ledger: ledgerCost == null ? null : n(ledgerCost),
      matches: cost != null && ledgerCost != null ? Math.abs(cost - n(ledgerCost)) <= Math.max(1, n(ledgerCost) * 1e-6) : null },
  };
}

/** One port's slice of the model (null when nothing changes ship there). */
export const hubAt = (model, code) => model?.hubs.find((h) => h.code === code) || null;
