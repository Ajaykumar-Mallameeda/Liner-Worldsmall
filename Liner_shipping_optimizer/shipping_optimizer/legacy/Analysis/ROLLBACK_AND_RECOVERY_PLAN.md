# ROLLBACK AND RECOVERY PLAN

## Executive Summary

This document defines rollback and recovery procedures for each implementation phase, ensuring we can quickly recover from failures while maintaining system stability. Each phase is designed to be independently reversible.

---

## ROLLBACK PHILOSOPHY

### Core Principles
1. **Fast Recovery**: Minimize downtime with quick rollback procedures
2. **Data Integrity**: Never compromise data during rollback
3. **Incremental Revert**: Can rollback individual features, not just entire system
4. **Automated Where Possible**: Reduce human error in rollback procedures
5. **Document Everything**: Clear runbooks for every rollback scenario

### Rollback Triggers
- **Critical Bugs**: Optimization produces invalid results
- **Performance Regression**: >50% slower than baseline
- **System Instability**: Error rate >5%
- **Data Corruption**: Validation failures
- **Customer Impact**: SLA violations

---

## PHASE 1: CRITICAL CORRECTNESS FIXES - ROLLBACK

### Rollback Strategy
**Risk Level**: LOW  
**Recovery Time**: <5 minutes

### Individual Bug Rollbacks

#### A.1.1 Fleet Capacity Constraint
```bash
# Rollback command
git revert <commit-hash-for-fleet-fix>

# Or disable via feature flag
export FLEET_CONSTRAINT_ENABLED=false
```

#### A.1.2 MILP Status Check
```bash
# Rollback command
git revert <commit-hash-for-milp-status>

# Verify old behavior returns
python scripts/test_milp_behavior.py --expect-no-status-check
```

#### A.1.3 FFE/TEU Unit Conversion
```bash
# Rollback command
git revert <commit-hash-for-unit-conversion>

# Danger: This will double all capacity calculations
# Only rollback if absolutely necessary
```

### Full Phase Rollback
```bash
# Complete phase rollback
git revert --no-edit <start-commit>..<end-commit>

# Verify baseline behavior
python -m tests.test_orchestrator --baseline-mode
```

### Validation After Rollback
```bash
# Run critical tests
pytest tests/test_critical_bugs/ -v

# Verify solution quality
python scripts/validate_solution.py --expect-known-results

# Check for data corruption
python scripts/validate_data_integrity.py
```

---

## PHASE 2: RELIABILITY & ERROR HANDLING - ROLLBACK

### Rollback Strategy
**Risk Level**: MEDIUM  
**Recovery Time**: <10 minutes

### Component Rollbacks

#### Structured Logging (D.1.1)
```bash
# Feature flag approach
export STRUCTURED_LOGGING_ENABLED=false
# Falls back to standard logging

# Or code rollback
git revert <logging-commit>

# Verify simple logging works
python scripts/test_logging.py --check-basic
```

#### Circuit Breaker (D.2.1)
```bash
# Disable via config
circuit_breaker:
  enabled: false
  failure_threshold: 0  # Never opens

# Or rollback implementation
git revert <circuit-breaker-commit>

# Test LLM calls work without protection
python scripts/test_llm_integration.py --no-circuit-breaker
```

#### Solution Validator (C.1.1)
```bash
# Bypass validation
export SOLUTION_VALIDATION_ENABLED=false

# Or remove validator
git revert <validator-commit>

# Verify optimization completes
python -m tests.test_orchestrator --skip-validation
```

### Health Check Rollback
```bash
# If health checks are failing
kubectl delete deployment vessel-routing

# Deploy previous version
kubectl apply -f deployments/previous-version.yaml

# Verify health passes
curl http://localhost:8000/health
```

---

## PHASE 3: ASYNC INFRASTRUCTURE - ROLLBACK

### Rollback Strategy
**Risk Level**: HIGH  
**Recovery Time**: <15 minutes

### Async Mode Rollback
```bash
# 1. Switch to sync mode via config
async_mode:
  enabled: false
  fallback_to_sync: true

# 2. Restart services
kubectl rollout restart deployment/vessel-routing-api

# 3. Verify sync mode
curl http://localhost:8000/status | jq '.async_mode'
# Should return false
```

### Redis Queue Rollback
```bash
# If Redis is causing issues
# 1. Disable queue
queue:
  enabled: false
  fallback_to_sync: true

# 2. Clear queue (if needed)
redis-cli FLUSHALL

# 3. Restart without queue
docker-compose down
docker-compose up -d --no-queue

# 4. Verify direct processing
python scripts/test_direct_processing.py
```

### Complete Async Rollback
```bash
# Full rollback to synchronous architecture
git checkout sync-stable-branch

# Rebuild containers
docker-compose build --no-cache

# Start without async features
docker-compose up -d

# Validate
python -m tests.test_orchestrator --sync-only
```

### Database Rollback (if needed)
```bash
# If job persistence is causing issues
# 1. Stop writing to DB
export JOB_PERSISTENCE_ENABLED=false

# 2. Clear problematic data
psql -d vessel_routing -c "DELETE FROM jobs WHERE created_at < '1 hour ago';"

# 3. Verify operation
python scripts/test_without_persistence.py
```

---

## PHASE 4: PERFORMANCE OPTIMIZATIONS - ROLLBACK

### Rollback Strategy
**Risk Level**: MEDIUM  
**Recovery Time**: <10 minutes

### Parallel GA Rollback
```bash
# Disable parallel execution
parallel_ga:
  enabled: false
  force_sequential: true

# Or via environment
export PARALLEL_GA_ENABLED=false

# Restart services
kubectl rollout restart deployment/regional-optimizer

# Verify sequential execution
python scripts/test_ga_execution.py --expect-sequential
```

### Caching Rollback
```bash
# Disable Redis cache
cache:
  enabled: false
  fallback_to_compute: true

# Clear cache if corrupted
redis-cli FLUSHDB

# Verify no cache used
python scripts/test_cache_behavior.py --expect-no-cache
```

### MILP Optimizations Rollback
```bash
# Disable warm starts
milp:
  warm_start_enabled: false
  use_simple_initialization: true

# Disable cut aggregation
milp:
  cut_aggregation_enabled: false
  standard_cuts_only: true

# Verify MILP behavior
python scripts/test_milp_features.py --baseline-mode
```

### Performance Validation
```bash
# After any performance rollback
python scripts/benchmark.py --compare-baseline

# Ensure performance hasn't regressed below baseline
python scripts/performance_check.py --min-coverage 0.7 --max-time 600
```

---

## PHASE 5: MONITORING & OBSERVABILITY - ROLLBACK

### Rollback Strategy
**Risk Level**: LOW  
**Recovery Time**: <5 minutes

### Monitoring Rollback
```bash
# Monitoring issues typically don't require code rollback
# Just disable features

# Disable metrics collection
metrics:
  enabled: false

# Disable tracing
tracing:
  enabled: false

# Disable alerting
alerting:
  enabled: false

# Services continue without monitoring
```

### Alerting Rollback
```bash
# If alerts are firing incorrectly
# 1. Disable specific alert
kubectl patch alertmanager-config -p '{"spec":{"disabled_alerts":["high_error_rate"]}}'

# 2. Or disable all alerts
kubectl scale deployment alertmanager --replicas=0

# 3. Verify alerts stop
kubectl logs deployment/alertmanager
```

---

## PHASE 6: DEPLOYMENT INFRASTRUCTURE - ROLLBACK

### Rollback Strategy
**Risk Level**: HIGH  
**Recovery Time**: <30 minutes

### Kubernetes Rollback
```bash
# Quick rollback to previous deployment
kubectl rollout undo deployment/vessel-routing-api
kubectl rollout undo deployment/regional-optimizer
kubectl rollout undo deployment/llm-service

# Verify rollback status
kubectl rollout status deployment/vessel-routing-api

# Check pods are running
kubectl get pods -l app=vessel-routing
```

### Blue-Green Rollback
```bash
# If using blue-green deployment
# Switch traffic back to blue
kubectl patch service vessel-routing-api -p '{"spec":{"selector":{"version":"blue"}}}'

# Verify traffic switched
kubectl get service vessel-routing-api -o yaml

# Scale down green
kubectl scale deployment vessel-routing-api-green --replicas=0
```

### Helm Rollback
```bash
# Rollback to previous Helm release
helm rollback vessel-routing 2  # Rollback to revision 2

# Check rollback status
helm history vessel-routing

# Verify pods
kubectl get pods -l release=vessel-routing
```

### Complete Infrastructure Rollback
```bash
# If K8s deployment is completely broken
# 1. Scale down all deployments
kubectl scale deployment --all --replicas=0

# 2. Fall back to Docker Compose
cd docker/
docker-compose up -d

# 3. Verify system works
curl http://localhost:8000/health

# 4. Debug K8s issues separately
```

---

## PHASE 7: PRODUCTION FEATURES - ROLLBACK

### Rollback Strategy
**Risk Level**: MEDIUM  
**Recovery Time**: <20 minutes

### Feature Flag Rollbacks
```bash
# Most production features have feature flags
features:
  rate_limiting: false
  api_authentication: false
  advanced_optimizations: false

# Reload config
kubectl rollout restart deployment/vessel-routing-api
```

### API Rollback
```bash
# If new API endpoints are failing
# 1. Route to old API version
kubectl patch ingress vessel-routing -p '{"spec":{"rules":[{"host":"api.vessel-routing.com","http":{"paths":[{"path":"/","backend":{"serviceName":"vessel-routing-api-v1","servicePort":8000}}]}}]}}'

# 2. Deploy old API version
kubectl apply -f deployments/api-v1.yaml

# 3. Verify
curl -H "Accept: application/json" http://api.vessel-routing.com/v1/optimize
```

### Database Migration Rollback
```bash
# If database migration caused issues
# 1. Identify migration
flyway info

# 2. Rollback last migration
flyway undo

# 3. Verify data integrity
python scripts/validate_database.py

# 4. Re-run failed migration manually
```

---

## EMERGENCY PROCEDURES

### Complete System Failure
```bash
# 1. Declare emergency
kubectl annotate all emergency=true timestamp=$(date +%s)

# 2. Stop all deployments
kubectl scale deployment --all --replicas=0

# 3. Start minimal stack
docker-compose -f docker-compose.minimal.yml up -d

# 4. Verify basic functionality
python scripts/smoke_test.py --environment minimal

# 5. Investigate failure
kubectl logs -l app=vessel-routing --since=1h

# 6. Gradually restore services
kubectl scale deployment vessel-routing-api --replicas=1
# Verify, then continue
```

### Data Corruption Recovery
```bash
# 1. Stop all writes
kubectl scale deployment --all --replicas=0

# 2. Restore from backup
# Choose appropriate backup based on corruption time
pg_restore -d vessel_routing backups/latest_good.backup

# 3. Verify data integrity
python scripts/validate_all_data.py

# 4. Restart with validation enabled
export DATA_VALIDATION_STRICT=true
docker-compose up -d

# 5. Monitor closely
tail -f logs/validation.log
```

### Performance Degradation
```bash
# 1. Identify bottleneck
kubectl top pods
python scripts/performance_profiler.py

# 2. Disable recent optimizations
export ALL_PERFORMANCE_FEATURES=false

# 3. Restart with baseline config
cp config/baseline.yaml config/current.yaml
docker-compose restart

# 4. Verify performance
python scripts/benchmark.py --compare-baseline

# 5. Gradually re-enable features
```

---

## ROLLBACK AUTOMATION

### Automated Rollback Script
```python
# scripts/emergency_rollback.py
def emergency_rollback(target_phase):
    """Automated emergency rollback to specified phase"""
    
    rollback_procedures = {
        "phase1": rollback_phase1,
        "phase2": rollback_phase2,
        "phase3": rollback_phase3,
        "phase4": rollback_phase4,
        "phase5": rollback_phase5,
        "phase6": rollback_phase6,
        "phase7": rollback_phase7
    }
    
    # Execute rollback
    rollback_procedures[target_phase]()
    
    # Verify system health
    if not verify_system_health():
        # Rollback to previous phase
        emergency_rollback(get_previous_phase(target_phase))
    
    # Notify team
    notify_rollback_complete(target_phase)

def verify_system_health():
    """Check if system is healthy after rollback"""
    checks = [
        check_api_health,
        check_optimization_quality,
        check_data_integrity,
        check_performance
    ]
    
    return all(check() for check in checks)
```

### Health Check Monitoring
```python
# scripts/health_monitor.py
def continuous_health_monitoring():
    """Monitor system health and auto-rollback on critical issues"""
    
    while True:
        health_status = check_system_health()
        
        if health_status.critical:
            # Auto-rollback last change
            auto_emergency_rollback()
            
        elif health_status.degraded:
            # Alert team
            alert_degraded_performance(health_status)
            
        sleep(HEALTH_CHECK_INTERVAL)
```

---

## ROLLBACK VALIDATION

### Post-Rollback Checklists

#### Phase 1-2 Rollback Validation
- [ ] All critical bugs are back to expected behavior
- [ ] Error handling is minimal but functional
- [ ] Basic logging works
- [ ] Solution quality remains acceptable

#### Phase 3-4 Rollback Validation  
- [ ] System runs synchronously
- [ ] All optimizations produce same results
- [ ] Performance is at baseline level
- [ ] No caching or parallel features

#### Phase 5-6 Rollback Validation
- [ ] System runs without monitoring
- [ ] Containers work correctly
- [ ] Manual deployment possible
- [ ] Basic functionality preserved

#### Phase 7 Rollback Validation
- [ ] API v1 functionality works
- [ ] No authentication required
- [ ] All features disabled via flags
- [ ] Database schema compatible

### Automated Validation
```bash
# Run after any rollback
python scripts/post_rollback_validation.py --phase <phase-number>

# Comprehensive validation
python scripts/validate_system_health.py --strict-mode

# Performance validation
python scripts/benchmark.py --ensure-baseline-performance
```

---

## COMMUNICATION PROCEDURES

### Rollback Notification Template
```
Subject: EMERGENCY ROLLBACK - Phase X

System State:
- Time: <timestamp>
- Trigger: <rollback-reason>
- Current Phase: <previous-phase>
- Estimated Downtime: <duration>

Impact:
- Services Affected: <list>
- Customer Impact: <description>
- Data Impact: <none/minor/significant>

Actions Taken:
- Rollback procedure executed
- Systems restored to <phase>
- Validation completed

Next Steps:
- Investigating root cause
- Plan for re-deployment
- ETA for fix: <estimate>

Contact:
- Lead: <name>
- Slack: #incident-response
```

### Rollback Decision Tree
```
Is optimization producing invalid results?
  YES → Rollback to Phase 1 immediately
  
Is error rate > 5%?
  YES → Rollback to previous phase
  
Is performance degraded > 50%?
  YES → Disable performance features
  
Is monitoring/alerting broken?
  YES → Disable monitoring, continue operation
  
Is deployment infrastructure broken?
  YES → Fall back to Docker Compose
```

---

## SUMMARY

### Rollback Times by Phase
| Phase | Typical Rollback Time | Max Acceptable Downtime |
|-------|---------------------|------------------------|
| 1 | <5 minutes | 15 minutes |
| 2 | <10 minutes | 30 minutes |
| 3 | <15 minutes | 1 hour |
| 4 | <10 minutes | 30 minutes |
| 5 | <5 minutes | 15 minutes |
| 6 | <30 minutes | 2 hours |
| 7 | <20 minutes | 1 hour |

### Key Rollback Strategies
1. **Feature Flags**: For all non-critical features
2. **Environment Variables**: Quick configuration changes
3. **Git Revert**: For code changes
4. **Helm Rollback**: For deployment changes
5. **Blue-Green**: For API changes
6. **Fallback Services**: When all else fails

### Critical Success Factors
1. **Test Rollback Procedures**: Regular drills and testing
2. **Document Everything**: Clear runbooks for all scenarios
3. **Automate Where Possible**: Reduce human error
4. **Monitor Continuously**: Catch issues early
5. **Communicate Clearly**: Keep stakeholders informed

This comprehensive rollback plan ensures we can quickly and safely recover from any issue during the upgrade process, maintaining system stability while we work toward production readiness.