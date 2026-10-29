"""Sea-lane endpoint for the map (backend/searoutes.py): geometry, lengths vs LINERLIB, passages, avoid sets."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("searoute")

from backend import searoutes  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    searoutes._mem.clear()
    mp = pytest.MonkeyPatch()
    mp.setenv("SEAROUTE_CACHE_DIR", str(tmp_path_factory.mktemp("searoute_cache")))
    app = FastAPI()
    app.include_router(searoutes.router)
    yield TestClient(app)
    mp.undo()
    searoutes._mem.clear()


def test_route_has_unwrapped_geometry_length_and_passages(client):
    body = client.get("/api/searoutes/worldsmall", params={"pairs": "NLRTM-CNSHA,PABLB-USEWR"}).json()
    assert body["missing"] == []
    assert body["always_avoided"] == ["northwest", "bering"]
    r = body["routes"]["NLRTM|CNSHA"]
    assert {"suez", "malacca"} <= set(r["passages"])
    # Sea-lane length within 5 % of the optimizer's LINERLIB distance.
    assert r["model_nm"] and abs(r["nm"] - r["model_nm"]) / r["model_nm"] < 0.05
    assert r["model_canal"] == {"suez": 1, "panama": 0}
    lons = [c[0] for c in r["coords"]]
    assert all(abs(b - a) < 180 for a, b in zip(lons, lons[1:]))
    # Balboa (Pacific side) to Newark goes through the Panama Canal.
    assert "panama" in body["routes"]["PABLB|USEWR"]["passages"]


def test_avoid_reroutes_and_never_uses_arctic(client):
    base = client.get("/api/searoutes/worldsmall", params={"pairs": "NLRTM-CNSHA"}).json()["routes"]["NLRTM|CNSHA"]
    alt = client.get("/api/searoutes/worldsmall", params={"pairs": "NLRTM-CNSHA", "avoid": "suez,panama"}).json()["routes"]["NLRTM|CNSHA"]
    assert "suez" not in alt["passages"] and "panama" not in alt["passages"]
    assert "northwest" not in alt["passages"] and "bering" not in alt["passages"]
    assert "south_africa" in alt["passages"]
    assert alt["nm"] > base["nm"] * 1.2


def test_errors(client):
    assert client.get("/api/searoutes/worldsmall", params={"pairs": "NLRTM-CNSHA", "avoid": "atlantis"}).status_code == 422
    assert client.get("/api/searoutes/no_such_dataset", params={"pairs": "A-B"}).status_code == 404
    too_many = ",".join(f"A{i}-B{i}" for i in range(searoutes.MAX_PAIRS + 1))
    assert client.get("/api/searoutes/worldsmall", params={"pairs": too_many}).status_code == 413
    body = client.get("/api/searoutes/worldsmall", params={"pairs": "NLRTM-XXXXX"}).json()
    assert body["missing"] == ["NLRTM|XXXXX"]
