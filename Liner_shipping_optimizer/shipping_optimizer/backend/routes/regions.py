"""
API routes for regional agent data
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/regions", tags=["regions"])

# In-memory storage for regional data
regional_data = {
    "regions": [
        {
            "id": "asia",
            "name": "Asia",
            "status": "completed",
            "weekly_profit": 106904049,
            "coverage_percent": 76.9,
            "services_selected": 99,
            "profit_margin_pct": 79.7,
            "hub_ports": [146, 176, 282],
            "services_generated": 802,
            "services_filtered": 400,
            "uncovered_teu": 24978,
            "optimization_type": "hybrid",
            "execution_time": 12.5
        },
        {
            "id": "europe",
            "name": "Europe",
            "status": "completed",
            "weekly_profit": 234567890,
            "coverage_percent": 82.3,
            "services_selected": 87,
            "profit_margin_pct": 81.2,
            "hub_ports": [98, 143, 201],
            "services_generated": 650,
            "services_filtered": 325,
            "uncovered_teu": 18765,
            "optimization_type": "milp",
            "execution_time": 8.3
        },
        {
            "id": "americas",
            "name": "Americas",
            "status": "completed",
            "weekly_profit": 187654321,
            "coverage_percent": 68.5,
            "services_selected": 95,
            "profit_margin_pct": 76.8,
            "hub_ports": [45, 89, 234],
            "services_generated": 750,
            "services_filtered": 375,
            "uncovered_teu": 35421,
            "optimization_type": "genetic",
            "execution_time": 15.7
        },
        {
            "id": "africa",
            "name": "Africa",
            "status": "completed",
            "weekly_profit": 98765432,
            "coverage_percent": 45.2,
            "services_selected": 45,
            "profit_margin_pct": 68.3,
            "hub_ports": [67, 123, 189],
            "services_generated": 400,
            "services_filtered": 200,
            "uncovered_teu": 52134,
            "optimization_type": "hybrid",
            "execution_time": 6.2
        },
        {
            "id": "oceania",
            "name": "Oceania",
            "status": "completed",
            "weekly_profit": 145789321,
            "coverage_percent": 58.9,
            "services_selected": 67,
            "profit_margin_pct": 72.4,
            "hub_ports": [234, 345, 456],
            "services_generated": 550,
            "services_filtered": 275,
            "uncovered_teu": 28976,
            "optimization_type": "milp",
            "execution_time": 7.8
        }
    ]
}

@router.get("/")
async def get_all_regions():
    """Get all regional agent results"""
    return {
        "regions": regional_data["regions"],
        "total_regions": len(regional_data["regions"]),
        "last_updated": datetime.utcnow().isoformat()
    }

@router.get("/{region_id}")
async def get_region(region_id: str):
    """Get specific region data"""
    region = next((r for r in regional_data["regions"] if r["id"] == region_id), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region

@router.get("/{region_id}/services")
async def get_region_services(region_id: str):
    """Get services for a specific region"""
    region = next((r for r in regional_data["regions"] if r["id"] == region_id), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Mock service data
    services = [
        {
            "service_id": f"{region_id}_svc_{i}",
            "origin": region["hub_ports"][0],
            "destination": region["hub_ports"][1] if len(region["hub_ports"]) > 1 else region["hub_ports"][0],
            "weekly_teu": 5000 + (i * 1000),
            "vessel_type": "Panamax" if i % 2 == 0 else "Post-Panamax",
            "frequency": "weekly",
            "profit": 1000000 + (i * 100000)
        }
        for i in range(region["services_selected"])
    ]

    return {
        "region_id": region_id,
        "services": services,
        "total_services": len(services)
    }

@router.get("/{region_id}/hubs")
async def get_region_hubs(region_id: str):
    """Get hub ports for a specific region"""
    region = next((r for r in regional_data["regions"] if r["id"] == region_id), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Mock hub port data
    hubs = [
        {
            "port_id": port_id,
            "name": f"Hub Port {port_id}",
            "country": "Country",
            "latitude": 0.0,
            "longitude": 0.0,
            "teu_throughput": 100000 + (port_id * 1000),
            "vessels_assigned": 15 + (port_id % 10)
        }
        for port_id in region["hub_ports"]
    ]

    return hubs

@router.post("/{region_id}/optimize")
async def optimize_region(region_id: str, config: Dict[str, Any]):
    """Trigger optimization for a specific region"""
    region = next((r for r in regional_data["regions"] if r["id"] == region_id), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Update region status
    region["status"] = "running"

    return {
        "message": f"Optimization started for {region_id}",
        "config": config,
        "timestamp": datetime.utcnow().isoformat()
    }