/**
 * AgentTopology
 * --------------
 * Phase 10 — read-only representation of the multi-agent
 * pipeline that produced the current optimization run. The
 * visualization mirrors the actual architecture documented
 * in src/agents/* and src/validation/*:
 *
 *   Orchestrator
 *     → Coordinator
 *       → Regional Agents (×5)
 *     → Service Generation
 *     → MILP / GA Optimization
 *     → Validation (consensus + weight + archetype)
 *     → Iteration Selection
 *     → Final Decision
 *
 * Each node has a state drawn from the real pipeline state
 * (or the maritime telemetry roll-up). If a state is not
 * available the node renders as `unavailable` (quiet outline)
 * — it is never fabricated as `running` or `completed`.
 *
 * The arrows between nodes are static (the topology is
 * fixed by the architecture); only the node state colours
 * change as the system reports real state changes.
 *
 * Pure presentational. Parent supplies the per-node state
 * map; the topology itself never fetches.
 */

const NODES = [
  { id: 'orchestrator', name: 'Orchestrator', sub: 'pipeline entry' },
  { id: 'coordinator', name: 'Coordinator', sub: 'weights · decision' },
  { id: 'regionals', name: 'Regional Agents', sub: '×5 regions' },
  { id: 'service_gen', name: 'Service Generation', sub: 'GA / MILP inputs' },
  { id: 'optimization', name: 'Optimization', sub: 'MILP · ServiceGA' },
  { id: 'validation', name: 'Validation', sub: 'consensus · clamps' },
  { id: 'selection', name: 'Selection', sub: 'deterministic authority' },
  { id: 'decision', name: 'Final Decision', sub: 'maritime_intelligence' },
];

const STATE_CLASS = {
  running: 'running',
  ready: 'ready',
  idle: 'idle',
  completed: 'completed',
  degraded: 'degraded',
  unavailable: 'unavailable',
};

export default function AgentTopology({
  stateMap = {},
  liveArrow = false,
  compact = false,
}) {
  return (
    <div className="mc-topology">
      {NODES.map((node, idx) => {
        const st = (stateMap && stateMap[node.id]) || 'unavailable';
        const cls = STATE_CLASS[st] || 'unavailable';
        return (
          <div key={node.id} className="flex items-stretch">
            <div
              className={`mc-topology-node ${cls}`}
              style={compact ? { minWidth: 96, padding: '6px 10px' } : undefined}
            >
              <div className="name">{node.name}</div>
              <div className="sub">{node.sub}</div>
            </div>
            {idx < NODES.length - 1 && (
              <div
                className={`mc-topology-arrow${liveArrow ? ' live' : ''}`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
