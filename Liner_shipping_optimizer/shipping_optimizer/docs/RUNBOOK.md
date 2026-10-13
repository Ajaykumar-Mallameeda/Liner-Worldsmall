# Runbook - AI Vessel Routing System

## Overview

This runbook provides step-by-step procedures for operating the AI Vessel Routing System in production. It covers daily operations, troubleshooting common issues, and managing different scenarios.

## Quick Reference Commands

```bash
# Environment setup
source venv/bin/activate  # Windows: venv\Scripts\activate

# Run optimization
python -c "
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader
loader = NetworkLoader()
problem = loader.load_world_large()
result = OrchestratorAgent().process({'problem': problem})
print(f'Profit: ${result[\"summary_metrics\"][\"annual_profit\"]:,.0f}')
"

# Run with custom configuration
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct python run_optimization.py

# Validate data
python validate_data.py --data-dir data/ --instance WorldLarge

# Run performance benchmark
python benchmark_performance.py --instance WorldLarge --iterations 3
```

## Daily Operations

### Morning Checklist

```bash
# 1. Verify API connectivity
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models

# 2. Check data freshness
ls -la data/*.csv | head -5

# 3. Review logs from last run
tail -n 50 logs/optimization_$(date +%Y%m%d).log

# 4. Verify system resources
df -h  # Disk space
free -h  # Memory
```

### Running Daily Optimization

```python
#!/usr/bin/env python3
"""
daily_optimization.py
Standard daily optimization routine
"""

import logging
from datetime import datetime
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader
from src.utils.logger import setup_logging

def main():
    # Setup logging
    log_file = f"logs/optimization_{datetime.now().strftime('%Y%m%d')}.log"
    setup_logging(level=logging.INFO, file=log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("=== Starting Daily Optimization ===")
    
    try:
        # Load data
        logger.info("Loading WorldLarge instance...")
        loader = NetworkLoader()
        problem = loader.load_world_large()
        logger.info(f"Loaded: {len(problem.ports)} ports, {len(problem.demands)} demands")
        
        # Run optimization
        logger.info("Starting optimization...")
        orchestrator = OrchestratorAgent()
        result = orchestrator.process({"problem": problem})
        
        # Extract key metrics
        metrics = result["summary_metrics"]
        logger.info("=== OPTIMIZATION RESULTS ===")
        logger.info(f"Weekly Profit: ${metrics['weekly_profit']:,.0f}")
        logger.info(f"Annual Profit: ${metrics['annual_profit']:,.0f}")
        logger.info(f"Coverage: {metrics['coverage']:.1f}%")
        logger.info(f"Services: {metrics['total_services']}")
        logger.info(f"Iterations: {result['iterations_run']}")
        
        # Save results
        import json
        output_file = f"results/optimization_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to {output_file}")
        
        # Check quality thresholds
        if metrics['coverage'] < 70:
            logger.warning(f"Low coverage: {metrics['coverage']:.1f}% < 70%")
        if metrics['weekly_profit'] < 0:
            logger.error(f"Negative profit: ${metrics['weekly_profit']:,.0f}")
            
    except Exception as e:
        logger.error(f"Optimization failed: {str(e)}", exc_info=True)
        raise
    
    logger.info("=== Daily Optimization Complete ===")

if __name__ == "__main__":
    main()
```

### Daily Health Checks

```python
#!/usr/bin/env python3
"""
health_check.py
Verify system health and data integrity
"""

def check_api_key():
    """Verify OpenRouter API key is valid"""
    import os
    from src.utils.config import Config
    
    if not Config.OPENROUTER_API_KEY:
        return False, "No API key configured"
    if not Config.OPENROUTER_API_KEY.startswith("sk-or-"):
        return False, "Invalid API key format"
    return True, "API key valid"

def check_data_files():
    """Verify all required data files exist"""
    from pathlib import Path
    
    required = [
        "data/ports.csv",
        "data/services.csv", 
        "data/demands.csv",
        "data/dist_dense.csv"
    ]
    
    missing = []
    for file in required:
        if not Path(file).exists():
            missing.append(file)
    
    return len(missing) == 0, f"Missing files: {missing}" if missing else "All files present"

def check_memory():
    """Verify sufficient memory for optimization"""
    import psutil
    
    available_gb = psutil.virtual_memory().available / (1024**3)
    required_gb = 8
    
    return available_gb > required_gb, f"{available_gb:.1f}GB available, {required_gb}GB required"

def main():
    checks = [
        ("API Key", check_api_key),
        ("Data Files", check_data_files),
        ("Memory", check_memory)
    ]
    
    print("=== System Health Check ===")
    all_good = True
    
    for name, check_func in checks:
        status, message = check_func()
        icon = "✓" if status else "✗"
        print(f"{icon} {name}: {message}")
        all_good = all_good and status
    
    print(f"\nOverall Status: {'HEALTHY' if all_good else 'NEEDS ATTENTION'}")
    return all_good

if __name__ == "__main__":
    main()
```

## Scenario Management

### Scenario 1: Standard Production Run

**When**: Daily scheduled optimization

**Steps**:
1. Verify data freshness (must be < 24 hours old)
2. Check system resources (≥8GB RAM available)
3. Run with default parameters
4. Validate results meet thresholds (≥70% coverage)
5. Archive results and update dashboards

**Expected Runtime**: 5-10 minutes for WorldLarge instance

```bash
# Standard production run
python daily_optimization.py
```

### Scenario 2: High-Demand Period

**When**: Peak season (e.g., Q4 holiday rush)

**Modifications**:
1. Increase GA population: `GA_POPULATION_SIZE=120`
2. More generations: `GA_GENERATIONS=180`
3. Tighter convergence: `COVERAGE_TARGET=75`

```bash
# High-demand configuration
export GA_POPULATION_SIZE=120
export GA_GENERATIONS=180
export COVERAGE_TARGET=75
python daily_optimization.py
```

### Scenario 3: Fleet Constraint Tightening

**When**: Vessel availability reduced (e.g., drydock maintenance)

**Modifications**:
1. Reduce fleet cap in code (temporary change)
2. Increase coverage weight in GA
3. Lower unserved demand penalty

```python
# Custom fleet constraint run
from src.optimization.hub_milp import HubMILP

# Temporarily modify fleet size
HubMILP.fleet_size = 250  # Down from 300

# Adjust weights for better coverage
result = orchestrator.process({
    "problem": problem,
    "weights": {
        "profit_weight": 0.4,
        "coverage_weight": 0.5,
        "cost_weight": 0.1
    }
})
```

### Scenario 4: Emergency Rerouting

**When**: Port closure or canal blockage

**Steps**:
1. Remove affected ports from ports.csv
2. Update distances for alternate routes
3. Increase exploration factor for diversity
4. Run with extended iterations

```python
# Emergency scenario
problem.exploration_factor = 2.0  # More exploration
result = orchestrator.process({"problem": problem})

# Check if affected region needs special handling
for region_result in result["regional_results"]:
    if "CLOSURE" in region_result["region"].upper():
        print(f"Emergency adjustment for {region_result['region']}")
```

## Troubleshooting Guide

### Issue: Optimization Fails to Start

**Symptoms**:
- Immediate error on script start
- "API key not found" messages

**Diagnostics**:
```bash
# Check environment
echo $OPENROUTER_API_KEY | head -c 20
echo $ORCHESTRATOR_MODEL

# Verify file permissions
ls -la .env
ls -la data/
```

**Solutions**:
1. Set API key in `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
   ```
2. Verify data directory exists:
   ```bash
   mkdir -p data logs results
   ```
3. Check Python path:
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)
   ```

### Issue: Low Coverage (< 60%)

**Symptoms**:
- Coverage consistently below 60%
- High unserved demand

**Diagnostics**:
```python
# Check service pool size
print(f"Candidate services: {len(problem.services)}")

# Check demand distribution
demands = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)
top_10_percent = int(len(demands) * 0.1)
print(f"Top 10% demand: {sum(d.weekly_teu for d in demands[:top_10_percent]):.0f} TEU")
print(f"Bottom 90% demand: {sum(d.weekly_teu for d in demands[top_10_percent:]):.0f} TEU")
```

**Solutions**:
1. Generate more candidate services:
   ```python
   # In ServiceGeneratorAgent.generate_services()
   top_n_direct = min(800, len(top_demands))  # Increase from 500
   ```
2. Lower service filtering threshold:
   ```python
   # In RegionalAgent._filter_services()
   margin = (svc.capacity * 0.3 * 150) > svc.weekly_cost  # Lower from 0.5
   ```
3. Increase coverage weight:
   ```python
   problem.coverage_weight = 0.6  # Up from 0.4
   problem.profit_weight = 0.3    # Down from 0.5
   ```

### Issue: MILP Solver Timeout

**Symptoms**:
- "MILP timeout" warnings
- Incomplete solutions

**Diagnostics**:
```python
# Check MILP statistics
for cluster_result in cluster_results:
    print(f"Status: {cluster_result['status']}")
    print(f"Variables: {cluster_result['num_direct_vars'] + cluster_result['num_transfer_vars']}")
```

**Solutions**:
1. Reduce time limit per cluster:
   ```python
   milp = HubMILP(sub, chromosome, time_limit=60)  # Down from 120
   ```
2. Limit transfer pairs:
   ```python
   # In transfer_pairs()
   MAX_TRANSFER_PAIRS = 1000  # Down from 2000
   ```
3. Simplify problem:
   ```python
   # Skip MILP for very low coverage
   if chromosome["coverage_estimate"] < 20:
       chromosome["skip_milp"] = True
   ```

### Issue: Memory Overflow

**Symptoms**:
- "Killed" process
- OutOfMemoryError

**Diagnostics**:
```bash
# Monitor memory usage
watch -n 1 'ps aux | grep python | head -5'

# Check system limits
ulimit -a
```

**Solutions**:
1. Use sparse matrices:
   ```python
   from scipy.sparse import csr_matrix
   distance_matrix = csr_matrix((data, (rows, cols)), shape=(n_ports, n_ports))
   ```
2. Process regions sequentially:
   ```python
   # Disable parallel processing
   for agent in regional_agents:
       result = agent.process({"problem": regional_problem})
   ```
3. Reduce problem size:
   ```python
   # Filter small demands
   problem.demands = [d for d in problem.demands if d.weekly_teu > 10]
   ```

### Issue: Too Many Service Conflicts

**Symptoms**:
- High conflict count in coordinator
- Services duplicated across regions

**Diagnostics**:
```python
# Check overlap
conflicts = coordinator._identify_conflicts(regional_results)
print(f"Conflicts: {len(conflicts)}")
for c in conflicts[:5]:
    print(f"Service {c['service_id']} in: {', '.join(c['regions'])}")
```

**Solutions**:
1. Improve port clustering:
   ```python
   # In PortClustering.cluster_ports()
   self.n_clusters = 4  # More regions for better separation
   ```
2. Add region tags to services:
   ```python
   # Mark services with primary region
   service.primary_region = determine_region(service.ports)
   ```
3. Strengthen coordinator resolution:
   ```python
   # Keep service only if profit margin > threshold
   if keep_profit - drop_profit < min_profit_diff:
       # Remove from both regions
   ```

## Performance Optimization

### Runtime Benchmarking

```python
#!/usr/bin/env python3
"""
benchmark.py
Comprehensive performance benchmarking
"""

import time
import psutil
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader

def benchmark_instance(instance_name, loader_func):
    """Benchmark a specific problem instance"""
    print(f"\n=== Benchmarking {instance_name} ===")
    
    # Start monitoring
    process = psutil.Process()
    start_time = time.perf_counter()
    start_mem = process.memory_info().rss / 1024**2  # MB
    
    # Load problem
    load_start = time.perf_counter()
    problem = loader_func()
    load_time = time.perf_counter() - load_start
    
    # Run optimization
    opt_start = time.perf_counter()
    result = OrchestratorAgent().process({"problem": problem})
    opt_time = time.perf_counter() - opt_start
    
    # Calculate metrics
    total_time = time.perf_counter() - start_time
    peak_mem = process.memory_info().rss / 1024**2  # MB
    mem_delta = peak_mem - start_mem
    
    # Report
    print(f"Problem Size: {len(problem.ports)} ports, {len(problem.demands)} demands")
    print(f"Load Time: {load_time:.2f}s")
    print(f"Optimization Time: {opt_time:.2f}s")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Memory Used: {mem_delta:.1f}MB (peak: {peak_mem:.1f}MB)")
    print(f"Coverage: {result['summary_metrics']['coverage']:.1f}%")
    print(f"Iterations: {result['iterations_run']}")
    
    return {
        "instance": instance_name,
        "load_time": load_time,
        "opt_time": opt_time,
        "total_time": total_time,
        "memory_mb": mem_delta,
        "coverage": result['summary_metrics']['coverage']
    }

def main():
    loader = NetworkLoader()
    
    results = []
    results.append(benchmark_instance("Small", loader.load_small))
    results.append(benchmark_instance("Medium", loader.load_medium))
    results.append(benchmark_instance("WorldLarge", loader.load_world_large))
    
    # Summary
    print("\n=== BENCHMARK SUMMARY ===")
    print("{:<12} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
        "Instance", "Load", "Opt", "Total", "Mem", "Coverage"))
    for r in results:
        print("{:<12} {:>10.2f} {:>10.2f} {:>10.2f} {:>10.1f} {:>10.1f}%".format(
            r["instance"], r["load_time"], r["opt_time"], 
            r["total_time"], r["memory_mb"], r["coverage"]
        ))

if __name__ == "__main__":
    main()
```

### Optimization Tuning

Based on benchmark results, apply these tuning strategies:

1. **For Speed Critical**:
   ```python
   config = {
       "GA_POPULATION_SIZE": 60,     # Down from 80
       "GA_GENERATIONS": 80,        # Down from 120
       "MILP_TIME_LIMIT": 60,       # Down from 120
       "MAX_TRANSFER_PAIRS": 1000   # Down from 2000
   }
   ```

2. **For Quality Critical**:
   ```python
   config = {
       "GA_POPULATION_SIZE": 100,    # Up from 80
       "GA_GENERATIONS": 180,       # Up from 120
       "COVERAGE_TARGET": 75,       # Up from 70
       "MAX_ITERATIONS": 4          # Up from 3
   }
   ```

3. **For Memory Constrained**:
   ```python
   config = {
       "MAX_SERVICES_PER_DEMAND": 5,   # Down from 10
       "MAX_TRANSFER_PAIRS": 500,      # Down from 2000
       "GA_POPULATION_SIZE": 40        # Down from 80
   }
   ```

## Monitoring and Alerting

### Key Performance Indicators

| Metric | Target | Alert Threshold | Measurement |
|--------|--------|-----------------|-------------|
| Coverage | ≥70% | <60% | Daily run |
| Profit Margin | ≥30% | <20% | Daily run |
| Runtime | <10min | >15min | Daily run |
| Success Rate | 100% | <95% | Weekly |
| Memory Use | <2GB | >4GB | Daily run |

### Alert Script

```python
#!/usr/bin/env python3
"""
alert_checker.py
Check optimization results and send alerts
"""

import smtplib
from email.mime.text import MimeText

def check_results(results):
    """Check results against thresholds"""
    alerts = []
    
    coverage = results["summary_metrics"]["coverage"]
    if coverage < 60:
        alerts.append(f"CRITICAL: Low coverage {coverage:.1f}% < 60%")
    elif coverage < 70:
        alerts.append(f"WARNING: Coverage {coverage:.1f}% below target 70%")
    
    profit = results["summary_metrics"]["weekly_profit"]
    cost = results["summary_metrics"]["total_cost"]
    margin = profit / (profit + cost) * 100 if (profit + cost) > 0 else 0
    
    if margin < 20:
        alerts.append(f"CRITICAL: Low margin {margin:.1f}% < 20%")
    elif margin < 30:
        alerts.append(f"WARNING: Margin {margin:.1f}% below target 30%")
    
    iterations = results["iterations_run"]
    if iterations >= 3:
        alerts.append(f"INFO: Max iterations reached ({iterations})")
    
    return alerts

def send_alert(alerts):
    """Send email alert"""
    if not alerts:
        return
    
    subject = "Shipping Optimizer Alert"
    body = "\n".join(alerts)
    
    msg = MimeText(body)
    msg["Subject"] = subject
    msg["From"] = "optimizer@company.com"
    msg["To"] = "ops-team@company.com"
    
    # Configure SMTP server
    with smtplib.SMTP("smtp.company.com") as server:
        server.send_message(msg)

def main():
    # Load latest results
    import json
    from pathlib import Path
    import glob
    
    result_files = glob.glob("results/optimization_*.json")
    if not result_files:
        print("No results found")
        return
    
    latest = max(result_files)
    with open(latest) as f:
        results = json.load(f)
    
    alerts = check_results(results)
    if alerts:
        print("Alerts detected:")
        for alert in alerts:
            print(f"  - {alert}")
        send_alert(alerts)
    else:
        print("All metrics normal")

if __name__ == "__main__":
    main()
```

## Maintenance Tasks

### Weekly Maintenance

```bash
#!/bin/bash
# weekly_maintenance.sh

echo "=== Weekly Maintenance ==="

# 1. Clean old logs (keep 30 days)
find logs/ -name "*.log" -mtime +30 -delete
echo "Cleaned old logs"

# 2. Archive old results
mkdir -p archive/$(date +%Y-%m)
mv results/optimization_$(date -d '7 days ago' +%Y%m%d)*.json archive/$(date +%Y-%m)/
echo "Archived old results"

# 3. Update dependencies
pip list --outdated > requirements_outdated.txt
echo "Checked for outdated packages"

# 4. Verify data integrity
python validate_data.py --all
echo "Validated data integrity"

# 5. Performance check
python benchmark.py --quick
echo "Performance check complete"

echo "=== Maintenance Complete ==="
```

### Monthly Maintenance

```python
#!/usr/bin/env python3
"""
monthly_maintenance.py
Deep system maintenance tasks
"""

import sqlite3
import json
from datetime import datetime, timedelta

def analyze_trends():
    """Analyze monthly performance trends"""
    # Load last 30 days of results
    results = []
    for i in range(30):
        date = datetime.now() - timedelta(days=i)
        file = f"results/optimization_{date.strftime('%Y%m%d')}.json"
        try:
            with open(file) as f:
                results.append(json.load(f))
        except FileNotFoundError:
            continue
    
    if len(results) < 7:
        print("Insufficient data for trend analysis")
        return
    
    # Calculate trends
    coverages = [r["summary_metrics"]["coverage"] for r in results]
    profits = [r["summary_metrics"]["weekly_profit"] for r in results]
    
    print("=== MONTHLY TRENDS ===")
    print(f"Average Coverage: {sum(coverages)/len(coverages):.1f}%")
    print(f"Coverage Trend: {'↑' if coverages[-1] > coverages[0] else '↓'}")
    print(f"Average Profit: ${sum(profits)/len(profits):,.0f}/week")
    print(f"Profit Trend: {'↑' if profits[-1] > profits[0] else '↓'}")

def update_models():
    """Retrain or update ML models if needed"""
    print("Checking for model updates...")
    # Placeholder for model retraining logic
    pass

def main():
    analyze_trends()
    update_models()
    print("Monthly maintenance complete")

if __name__ == "__main__":
    main()
```

## Emergency Procedures

### System Failure Recovery

```bash
#!/bin/bash
# emergency_recovery.sh

echo "=== EMERGENCY RECOVERY ==="

# 1. Check last known good state
LAST_GOOD=$(ls -t results/optimization_*.json | head -1 | grep -o '[0-9]\{8\}')
echo "Last good run: $LAST_GOOD"

# 2. Restore from checkpoint if available
if [ -f "checkpoints/checkpoint_$LAST_GOOD.json" ]; then
    cp checkpoints/checkpoint_$LAST_GOOD.json checkpoint.json
    echo "Restored checkpoint"
fi

# 3. Run with safe configuration
export GA_POPULATION_SIZE=40
export GA_GENERATIONS=60
export MILP_TIME_LIMIT=30

python daily_optimization.py

echo "=== RECOVERY COMPLETE ==="
```

### Data Corruption Recovery

```python
#!/usr/bin/env python3
"""
data_recovery.py
Recover from data corruption
"""

import pandas as pd
from pathlib import Path

def validate_and_repair():
    """Validate and repair data files"""
    
    # Check ports.csv
    ports = pd.read_csv("data/ports.csv")
    dup_ports = ports[ports.duplicated(subset=["id"], keep=False)]
    if not dup_ports.empty:
        print(f"Found {len(dup_ports)} duplicate ports")
        ports = ports.drop_duplicates(subset=["id"], keep="first")
        ports.to_csv("data/ports.csv", index=False)
        print("Fixed duplicate ports")
    
    # Check services.csv
    services = pd.read_csv("data/services.csv")
    # Parse ports list
    services["port_count"] = services["ports"].str.count(",") + 1
    bad_services = services[services["port_count"] < 2]
    if not bad_services.empty:
        print(f"Found {len(bad_services)} invalid services")
        services = services[services["port_count"] >= 2]
        services = services.drop("port_count", axis=1)
        services.to_csv("data/services.csv", index=False)
        print("Fixed invalid services")
    
    # Check demands.csv
    demands = pd.read_csv("data/demands.csv")
    zero_demands = demands[demands["weekly_teu"] <= 0]
    if not zero_demands.empty:
        print(f"Found {len(zero_demands)} zero/negative demands")
        demands = demands[demands["weekly_teu"] > 0]
        demands.to_csv("data/demands.csv", index=False)
        print("Removed invalid demands")
    
    print("Data recovery complete")

def main():
    # Backup current data
    Path("data/backup").mkdir(exist_ok=True)
    for file in ["ports.csv", "services.csv", "demands.csv", "dist_dense.csv"]:
        if Path(f"data/{file}").exists():
            Path(f"data/{file}").rename(f"data/backup/{file}.{datetime.now().strftime('%Y%m%d%H%M')}")
    
    # Recover from last known good if available
    backup_dir = Path("data/backup")
    if backup_dir.exists():
        latest_backup = max(backup_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
        print(f"Recovering from {latest_backup}")
    
    validate_and_repair()

if __name__ == "__main__":
    main()
```