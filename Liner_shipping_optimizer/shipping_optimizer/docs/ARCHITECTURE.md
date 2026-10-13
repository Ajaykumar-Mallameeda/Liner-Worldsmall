# System Architecture

## Overview

The AI Vessel Routing System is a **hybrid AI + Operations Research** platform that optimizes global liner shipping networks. It combines **hierarchical genetic algorithms**, **mixed-integer linear programming**, and **multi-agent LLM coordination** to produce optimized weekly service plans.

## Architecture Layers

### 1. Data Layer
- **Input**: Port network, origin-destination demand matrix (9,622 lanes), fleet database (6 vessel classes), distance matrix, cost model
- **Source**: Structured CSV files with port geography, demand volumes, vessel specifications, and operating costs
- **Processing**: ETL pipeline with Pydantic validation, FFE→TEU conversion (×2), K-means geographic port clustering

### 2. Optimization Layer (OR)

#### Hierarchical Genetic Algorithm (GA)
- **Service GA**: Selects optimal service routes from candidates using profit-maximizing fitness function
- **Frequency GA**: Optimizes sailing frequencies per selected service
- **L1+L2**: Two-layer architecture: service selection (L1) → frequency optimization (L2)

#### Hub MILP
- Mixed-integer linear programming for hub-and-spoke flow optimization
- Fleet vessel assignment with capacity constraints
- Transshipment cost modeling

### 3. AI Agent Layer

#### Orchestrator Agent
- Runs the main iteration loop (up to 3 iterations)
- Coordinates all agents in sequence
- Detects convergence and triggers re-runs

#### Coordinator Agent (LLM-powered)
- Analyzes the full optimization problem (port counts, lane density, demand distribution)
- Generates adaptive weight adjustments (profit/coverage/cost) each iteration
- Detects regional conflicts in service assignments
- Evaluates convergence quality
- 100% AI-generated decisions across all iterations

#### Regional Agents (×5)
- Parallel execution across Asia, Europe, Americas, Middle East, Africa
- Each runs its own GA + MILP pipeline
- Produces regional strategy, hub selection, and service plan

#### Service Generator Agent
- Computes network statistics per region
- Generates candidate service routes (800-2,000 per region)
- LLM attempts to select archetype parameters; algorithmic fallback active

### 4. Consensus Layer

#### Consensus Engine
- Weighted voting across regions and coordinator
- Weight adjustment reconciliation
- Conflict detection and resolution
- Confidence scoring
- Archetype parameter agreement

#### Validators
- **Weight Validator**: Ensures weights ∈ [0,1], sum to 1.0
- **Archetype Validator**: Validates service mix ratios
- **Regional Policy Validator**: Schema policy validation

### 5. Runtime Layer

#### pipeline_output.json
- Single source of truth for all frontend data
- Contains: summary metrics, regional results, decision output, iteration audit, selected services, health status, consensus results, test scorecard, LLM metrics
- 309/313 assertions verify integrity

### 6. Frontend Layer

#### Architecture
- React SPA with 33 modular components
- Single `useOptimizationState()` hook as state source
- `runtimeAdapter.js` normalizes backend snake_case → frontend camelCase
- WebSocket manager for live updates
- Runtime truth loaded from `pipeline_output.json` on mount

#### Navigation (14 tabs)
Landing → Overview → Fleet Explorer → Route Explorer → Port Intelligence → Pipeline → Regional Agents → Funnel Analytics → Feedback Loop → Conflict Resolution → Maritime Map → Scenarios → Export Center → Executive Summary

## Data Flow

```
pipeline_output.json
    │
    ▼
runtimeAdapter.js (normalizes field names)
    │
    ▼
apiClient.js (loads file + HTTP endpoints)
websocketManager.js (live WebSocket updates)
    │
    ▼
useOptimizationState.js (React hook — single state source)
    │
    ▼
33 Components across 6 directories
    │
    ▼
14-tab Dashboard
```

## Key Design Decisions

1. **Runtime Truth Single Source**: All frontend data originates from `pipeline_output.json`. No mock data, no hardcoded values.
2. **Backend Frozen**: Algorithms, AI agents, prompts, and validators are certified and frozen for V1.
3. **Frontend Adapts to Backend**: The runtime adapter handles all field name normalization.
4. **Component Isolation**: Each of 33 components has a single responsibility and receives data via props.
5. **WebSocket for Live Updates**: Real-time pipeline progress without polling.
