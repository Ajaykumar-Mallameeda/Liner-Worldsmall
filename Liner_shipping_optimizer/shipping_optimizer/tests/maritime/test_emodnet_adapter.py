"""Tests for the EMODnet ingestion adapter (LOCAL + REMOTE behavior)."""

import json
from pathlib import Path
from unittest import mock

import pytest

from maritime.ingestion.base import IngestionError
from maritime.ingestion.emodnet import EmodnetConfig, EmodnetProvider


FIXTURE = Path("data/maritime/synthetic/emodnet_vessel_density_sample.json")


def test_local_mode_loads_fixture():
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    cfg = EmodnetConfig(mode="local", local_path=str(FIXTURE))
    p = EmodnetProvider(cfg)
    result = p.fetch()
    assert result.source == "EMODNET"
    assert result.dataset == "vessel_density_all_ships"
    assert result.license == "CC BY 4.0"
    assert len(result.records) == 10
    assert result.notes == "local-fixture"


def test_local_mode_missing_path_raises():
    cfg = EmodnetConfig(mode="local", local_path="nope.json")
    p = EmodnetProvider(cfg)
    with pytest.raises(IngestionError):
        p.fetch()


def test_local_mode_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    cfg = EmodnetConfig(mode="local", local_path=str(bad))
    p = EmodnetProvider(cfg)
    with pytest.raises(IngestionError):
        p.fetch()


def test_local_mode_empty_records(tmp_path):
    p_json = tmp_path / "empty.json"
    p_json.write_text(json.dumps({
        "source": "EMODNET",
        "dataset": "x",
        "dataset_version": "0",
        "license": "CC BY 4.0",
        "attribution": "EMODnet",
        "records": [],
    }), encoding="utf-8")
    cfg = EmodnetConfig(mode="local", local_path=str(p_json))
    p = EmodnetProvider(cfg)
    result = p.fetch()
    assert result.records == []
    assert result.is_empty()


def test_remote_mode_no_network_in_optimizer_path(monkeypatch):
    """The remote path may use stdlib urllib, but a remote fetch must never
    be initiated by the optimizer import graph. We test that the *default*
    config is LOCAL, so calling fetch() in the optimizer path does not
    touch the network.
    """
    cfg = EmodnetConfig()  # default mode=local
    assert cfg.mode == "local"
    assert cfg.is_remote() is False


def test_remote_mode_uses_stdlib_urllib(monkeypatch):
    """Confirm the remote path uses urllib.request (no third-party HTTP)."""
    import maritime.ingestion.emodnet as emodnet_mod
    # Read the source; assert 'urllib.request' is imported.
    src = Path(emodnet_mod.__file__).read_text(encoding="utf-8")
    assert "urllib.request" in src
    # And no third-party http clients.
    for forbidden in ("requests", "httpx", "aiohttp"):
        assert forbidden not in src, f"emodnet module imports {forbidden}"


def test_remote_mode_urlerror_raises(monkeypatch):
    import urllib.error
    cfg = EmodnetConfig(mode="remote", source_url="https://example.invalid/x")
    p = EmodnetProvider(cfg)
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
        with pytest.raises(IngestionError):
            p.fetch()


def test_remote_mode_succeeds(monkeypatch):
    body = json.dumps({
        "source": "EMODNET", "dataset": "d", "dataset_version": "1",
        "license": "CC BY 4.0", "attribution": "EMODnet",
        "records": [],
    }).encode("utf-8")
    cfg = EmodnetConfig(mode="remote", source_url="https://example/x")
    p = EmodnetProvider(cfg)
    fake_resp = mock.MagicMock()
    fake_resp.status = 200
    fake_resp.read = lambda: body
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None
    with mock.patch("urllib.request.urlopen", return_value=fake_resp):
        result = p.fetch()
    assert result.records == []
    assert result.notes == "remote-fetch"


def test_remote_mode_http_error_raises(monkeypatch):
    fake_resp = mock.MagicMock()
    fake_resp.status = 503
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: None
    cfg = EmodnetConfig(mode="remote", source_url="https://example/x")
    p = EmodnetProvider(cfg)
    with mock.patch("urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(IngestionError):
            p.fetch()
