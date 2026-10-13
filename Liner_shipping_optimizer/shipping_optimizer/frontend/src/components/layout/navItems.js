// Phase 11 - reorganized navigation. Grouped by console section.
const navItems = [
  // --- COMMAND ---------------------------------------------------
  { id: "command_center",        label: "Command Center",         icon: "❖", section: "COMMAND" },

  // --- INTELLIGENCE ----------------------------------------------
  { id: "network_intel",         label: "Network Intelligence",   icon: "⊕", section: "INTELLIGENCE" },
  { id: "fleet_intel",           label: "Fleet Intelligence",     icon: "⎈", section: "INTELLIGENCE" },
  { id: "demand_intel",          label: "Demand Intelligence",    icon: "◍", section: "INTELLIGENCE" },
  { id: "port_intel",            label: "Port Intelligence",      icon: "◈", section: "INTELLIGENCE" },
  { id: "maritime_situation",    label: "Maritime Situation",     icon: "◐", section: "INTELLIGENCE" },

  // --- AI OPERATIONS ---------------------------------------------
  { id: "pipeline_ops",          label: "Pipeline",               icon: "◈", section: "AI OPERATIONS" },
  { id: "regional_agents",       label: "Regional Agents",        icon: "◎", section: "AI OPERATIONS" },
  { id: "ga_milp",               label: "GA · MILP",              icon: "◆", section: "AI OPERATIONS" },
  { id: "feedback_loop",         label: "Feedback Loop",          icon: "↺", section: "AI OPERATIONS" },
  { id: "decision_center",       label: "Decision Center",        icon: "▣", section: "AI OPERATIONS" },
  { id: "scenario_analysis",     label: "Scenario Analysis",      icon: "⌁", section: "AI OPERATIONS" },

  // --- SYSTEM ---------------------------------------------------
  { id: "telemetry",             label: "Telemetry",              icon: "▤", section: "SYSTEM" },
  { id: "data_sources",          label: "Data Sources",           icon: "◉", section: "SYSTEM" },
  { id: "system_health",         label: "System Health",          icon: "▣", section: "SYSTEM" },
];

export default navItems;
