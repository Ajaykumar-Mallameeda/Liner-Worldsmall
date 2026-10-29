/**
 * transshipmentData — the transshipment model (utils/transshipment.js) of the plan on screen, shared by the
 * Transshipment tab, the map's hub layer, the port drawer, the guided tour and the PDF report.
 *
 * Flows: the ledger of exactly this plan (portFlows.ledgerForServices; none → status 'no_flows', nothing is guessed
 * from another plan). Tariffs: the dataset's port records from /api/datasets/<dataset>/demand (cached); without
 * the backend the TEU figures stand and the per-port cost waits ('no_tariffs').
 */
import { useEffect, useMemo, useState } from 'react';
import { fetchDemand, ledgerForServices, datasetOf } from '../utils/portFlows.js';
import { transshipmentModel } from '../utils/transshipment.js';

export function useTransshipment(optimizationState) {
  const services = optimizationState?.global?.selected_services;
  const dataset = datasetOf(optimizationState);
  const [tariffs, setTariffs] = useState(undefined);   // undefined loading · null unavailable · object
  useEffect(() => {
    let cancelled = false;
    setTariffs(undefined);
    fetchDemand(dataset).then((d) => { if (!cancelled) setTariffs(d?.ports || null); });
    return () => { cancelled = true; };
  }, [dataset]);
  const ledger = useMemo(() => ledgerForServices(optimizationState, services), [optimizationState, services]);
  return useMemo(() => {
    if (!ledger) return { status: 'no_flows', model: null, ledger: null, dataset, engine: null };
    const model = transshipmentModel({ flows: ledger.plan.flows, tariffs: tariffs || null, ledgerCost: ledger.weekly_usd?.transshipment_cost ?? null });
    const engine = ledger.strategy_report?.extended_metrics?.transshipment || null;
    const status = tariffs === undefined ? 'loading_tariffs' : tariffs === null ? 'no_tariffs' : 'ok';
    return { status, model, ledger, dataset, engine, assumptions: ledger.assumptions || {} };
  }, [ledger, tariffs, dataset]);
}
