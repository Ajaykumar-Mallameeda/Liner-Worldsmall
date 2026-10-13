const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

// Load pipeline data — THE RUNTIME TRUTH
const pipelineData = JSON.parse(fs.readFileSync(path.join(__dirname, '../pipeline_output.json'), 'utf8'));

// Create WebSocket server
const wss = new WebSocket.Server({ port: 8000 });

console.log('Mock WebSocket server started on port 8000');
console.log(`Loaded runtime: ${pipelineData.summary_metrics.total_services} services, ` +
  `$${(pipelineData.summary_metrics.weekly_profit / 1e6).toFixed(1)}M weekly profit, ` +
  `${pipelineData.summary_metrics.coverage.toFixed(1)}% coverage`);

wss.on('connection', (ws) => {
  console.log('Client connected');

  // Build region data from runtime truth — matches backend snake_case
  const regions = {};
  pipelineData.regional_results.forEach(r => {
    const regionId = r.region.toLowerCase().replace(/\s+/g, '_');
    regions[regionId] = {
      region: r.region,
      weekly_profit: r.weekly_profit,
      annual_profit: r.annual_profit,
      coverage_percent: r.coverage_percent,
      services_generated: r.services_generated,
      services_filtered: r.services_filtered,
      services_selected: r.services_selected,
      profit_margin_pct: r.profit_margin_pct,
      operating_cost: r.operating_cost,
      fuel_cost: r.fuel_cost,
      transship_cost: r.transship_cost,
      port_cost: r.port_cost,
      total_cost: r.total_cost,
      uncovered_teu: r.uncovered_teu,
      satisfied_demand: r.satisfied_demand,
      unserved_demand: r.unserved_demand,
      hub_ports: r.hub_ports,
      strategy: r.strategy,
      explanation: r.explanation,
      total_demand: r.total_demand,
      profit_per_service: r.profit_per_service,
      cost_per_service: r.cost_per_service,
      status: r.status,
      selected_services: r.selected_services || [],
    };
  });

  // Send initial state with ALL runtime truth fields
  const initialState = {
    type: 'initial_state',
    data: {
      status: pipelineData.status,
      orchestrator: pipelineData.orchestrator,
      executive_summary: pipelineData.executive_summary || '',
      problem_stats: {
        ports: 435,
        lanes: 9622,
        services: 1200,
        weekly_demand: pipelineData.summary_metrics.satisfied_demand + pipelineData.summary_metrics.unserved_demand,
      },
      // summary_metrics — THE RUNTIME TRUTH for global values
      summary_metrics: pipelineData.summary_metrics,
      // decision_output — coordinator/feedback data
      decision_output: pipelineData.decision_output,
      // test_scorecard — quality metrics
      test_scorecard: pipelineData.test_scorecard,
      // llm_runtime_metrics — AI usage stats
      llm_runtime_metrics: pipelineData.llm_runtime_metrics,
      // regional_results — complete region data (back end snake_case format)
      regional_results: pipelineData.regional_results,
      // iteration_audit — iteration history
      iteration_audit: pipelineData.iteration_audit,
      // selected_services — all selected service routes for map
      selected_services: pipelineData.selected_services,
      // health_status
      health_status: pipelineData.health_status,
      // consensus_result
      consensus_result: pipelineData.consensus_result,
      // shared_context
      shared_context: pipelineData.shared_context,
      // Corridors (derived from selected services)
      corridors: (pipelineData.selected_services || []).slice(0, 20).map(s => ({
        from: s.ports?.[0] || '',
        to: s.ports?.[s.ports.length - 1] || '',
        teu: Math.round(s.load || 0),
        region: s.region?.toLowerCase() || 'asia',
        color: getRegionColor(s.region),
        active: true
      })),
      // Also provide camelCase metrics field for backwards compatibility
      metrics: {
        weeklyProfit: pipelineData.summary_metrics.weekly_profit,
        annualProfit: pipelineData.summary_metrics.annual_profit,
        coverage: pipelineData.summary_metrics.coverage,
        totalServices: pipelineData.summary_metrics.total_services,
        operatingCost: pipelineData.summary_metrics.operating_cost,
        runtime: pipelineData.summary_metrics.total_runtime,
        convergenceScore: pipelineData.decision_output?.feedback?.convergence_score || 0.97,
      },
    }
  };

  ws.send(JSON.stringify(initialState));

  // Simulate live updates
  let updateCount = 0;
  const updateInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      const stageNames = ['Data Loading', 'Regional Selection', 'Service Generation', 'Vessel Assignment', 'Profit Optimization'];
      const update = {
        type: 'pipeline_update',
        data: {
          stage: stageNames[updateCount % 5],
          progress: ((updateCount % 5) + 1) * 20,
          iteration: Math.floor(updateCount / 5) + 1,
          summary_metrics: {
            ...pipelineData.summary_metrics,
            weekly_profit: pipelineData.summary_metrics.weekly_profit + (Math.random() - 0.5) * 10000,
          }
        }
      };
      ws.send(JSON.stringify(update));
      updateCount++;
    } else {
      clearInterval(updateInterval);
    }
  }, 2000);

  ws.on('close', () => {
    console.log('Client disconnected');
    clearInterval(updateInterval);
  });

  ws.on('message', (message) => {
    const parsed = JSON.parse(message.toString());
    if (parsed.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong' }));
    } else if (parsed.type === 'start_pipeline') {
      ws.send(JSON.stringify({ type: 'pipeline_started', data: { timestamp: new Date().toISOString() } }));
      setTimeout(() => {
        ws.send(JSON.stringify({ type: 'pipeline_completed', data: { results: { summary_metrics: pipelineData.summary_metrics, decision_output: pipelineData.decision_output, selected_services: pipelineData.selected_services, executive_summary: pipelineData.executive_summary, test_scorecard: pipelineData.test_scorecard, llm_runtime_metrics: pipelineData.llm_runtime_metrics } } }));
      }, 3000);
    }
  });
});

wss.on('error', (error) => {
  console.error('WebSocket server error:', error);
});

function getRegionColor(region) {
  const colors = {
    asia: '#00d4ff',
    europe: '#7c3aed',
    americas: '#10b981',
    middle_east: '#f59e0b',
    africa: '#ef4444',
  };
  return colors[region?.toLowerCase()] || '#00d4ff';
}
