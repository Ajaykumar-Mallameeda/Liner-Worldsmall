// Tier-0 consumer check, frontend half: execute the REAL frontend consumers of the margin and
// the verdict (runtime adapter + React components, server-side rendered) on every scenario.
//
// usage: node tier0_frontend.mjs <frontend_dir_with_node_modules> <src_dir_under_test> <scenarios_dir> <out.json> <bundle_out.cjs>
//
// The scenarios are pipeline-output-shaped files (tier0_scenarios.py): a REAL orchestrator output
// and outputs derived from it for edge margins.  What is recorded is what a user would SEE.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [, , FRONT, SRC, SCEN, OUT, BUNDLE] = process.argv;
const req = createRequire(path.join(FRONT, 'package.json'));
const esbuild = req('esbuild');

const entryTemplate = fs.readFileSync(new URL('./tier0_frontend_entry.jsx', import.meta.url), 'utf8');
const entryPath = path.join(path.dirname(BUNDLE), 'tier0_frontend_entry.generated.jsx');
fs.writeFileSync(entryPath, entryTemplate.replaceAll('__SRC__', SRC.replaceAll('\\', '/')));
await esbuild.build({
  entryPoints: [entryPath], bundle: true, platform: 'node', format: 'cjs', outfile: BUNDLE,
  jsx: 'automatic', loader: { '.js': 'jsx', '.jsx': 'jsx' }, logLevel: 'error',
  nodePaths: [path.join(FRONT, 'node_modules')], define: { 'import.meta.env': '{}' },
});
const M = req(BUNDLE);

const strip = (html) => html.replace(/<[^>]+>/g, '|').replace(/\|+/g, '|').replace(/&amp;/g, '&').replace(/&#x27;/g, "'");
function render(Component, props) {
  try {
    return { ok: true, text: strip(M.renderToStaticMarkup(M.createElement(Component, props))) };
  } catch (e) {
    return { ok: false, error: `${e.name}: ${e.message}` };
  }
}
const pick = (text, re) => { const m = text.match(re); return m ? m[0] : null; };

const result = { scenarios: {} };
for (const f of fs.readdirSync(SCEN).filter((x) => x.endsWith('.json') && !x.startsWith('_')).sort()) {
  const name = f.replace('.json', '');
  const out = JSON.parse(fs.readFileSync(path.join(SCEN, f), 'utf8'));
  const rec = { components: {}, normalized: {} };
  let rt;
  try {
    rt = M.normalizeRuntime(out);
  } catch (e) {
    rec.normalized.error = `${e.name}: ${e.message}`;
    result.scenarios[name] = rec;
    continue;
  }
  const state = { global: rt.global, regions: rt.regions };
  rec.normalized = {
    global_margin: rt.global.margin, global_weeklyProfit: rt.global.weeklyProfit,
    global_revenue: rt.global.revenue,
    region_margins: Object.fromEntries(Object.entries(rt.regions).map(([k, v]) => [k, v.margin])),
  };
  const sv = render(M.SummaryView, { optimizationState: state });
  rec.components.SummaryView = sv.ok
    ? { ok: true, verdict: pick(sv.text, /Verdict: (Good|Needs Improvement)/),
        margin_sentence: pick(sv.text, /with an \|[^|]*\|[^|]*profit margin|[-0-9.]*undefined% profit margin|[^|]*% profit margin/),
        says_strong_financial_performance: sv.text.includes('strong financial performance'),
        executive_summary_verdict_in_data: (out.executive_summary || '').split('\n')[0] }
    : sv;
  rec.components.RegionCard = {};
  for (const [id, r] of Object.entries(rt.regions)) {
    const rc = render(M.RegionCard, { r, onClick: () => {}, selected: false });
    rec.components.RegionCard[id] = rc.ok ? { ok: true, margin_cell: pick(rc.text, /Margin\|[^|]*\|?[^|]*/) } : rc;
  }
  const ri = render(M.RegionalIntelligence, { optimizationState: state });
  rec.components.RegionalIntelligence = ri.ok
    ? { ok: true, margin_cell: pick(ri.text, /[-0-9.]+%\|Margin|—\|Margin/) } : ri;
  const oi = render(M.OptimizationInsights, { optimizationState: state });
  rec.components.OptimizationInsights = oi.ok
    ? { ok: true, best_margin: pick(oi.text, /Best Margin\|[^|]*\|[^|]*/) } : oi;
  const ex = render(M.ExportPanel, { optimizationState: state });
  rec.components.ExportPanel = ex.ok ? { ok: true, margin_row: pick(ex.text, /Margin\|[^|]*/) } : ex;
  // the console's own verdict card (CommandCenter): "Verdict: <evaluation.status>"; the whole view is
  // rendered, so any browser-only dependency shows up as an explicit blocker
  {
    const full = { ...state, iterations: rt.iterations, iteration_results: rt.iteration_results,
                   iteration_selection: rt.iteration_selection, scorecards: rt.scorecards,
                   iteration_regions_map: rt.iteration_regions_map, corridors: rt.corridors,
                   llm_runtime_aggregate: rt.llm_runtime_aggregate, llm_runtime_metrics: rt.llm_runtime_metrics,
                   raw: rt.raw, freshness: { status: 'live' } };
    const cc = render(M.CommandCenter, { optimizationState: full });
    rec.components.CommandCenter = cc.ok
      ? { ok: true, verdict_card: pick(cc.text, /EXPLANATION\|Verdict: [A-Za-z ]+\|Profit margin [^|]*/) }
      : cc;
  }
  rec.components.BenchmarkBadge_margin_target = {
    target: M.BENCHMARKS.margin.target,
    badge: (() => { const b = render(M.BenchmarkBadge, { value: rt.global.margin, benchmark: M.BENCHMARKS.margin, compact: false });
                    return b.ok ? b.text : b.error; })(),
  };
  result.scenarios[name] = rec;
}
fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
console.log('scenarios:', Object.keys(result.scenarios).join(', '));
