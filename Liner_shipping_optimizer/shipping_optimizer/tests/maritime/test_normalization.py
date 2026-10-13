"""Tests for the normalization layer (coordinates + timestamps + records)."""

import pytest

from maritime.normalization.coordinates import normalize_coordinate, quantize_cell
from maritime.normalization.timestamps import (
    normalize_observation_window,
    parse_period,
)


def test_normalize_coordinate_valid():
    assert normalize_coordinate(10.0, 20.0) == (10.0, 20.0)


def test_normalize_coordinate_out_of_range_lat():
    with pytest.raises(ValueError):
        normalize_coordinate(91.0, 0.0)


def test_normalize_coordinate_out_of_range_lon():
    with pytest.raises(ValueError):
        normalize_coordinate(0.0, 181.0)


def test_normalize_coordinate_nan():
    with pytest.raises(ValueError):
        normalize_coordinate(float("nan"), 0.0)


def test_quantize_cell_deterministic():
    a = quantize_cell(1.2901, 103.8501, precision=3)
    b = quantize_cell(1.2904, 103.8504, precision=3)
    c = quantize_cell(1.2909, 103.8509, precision=3)
    assert a == b == c
    assert a.startswith("cell:")


def test_quantize_cell_truncates_not_rounds():
    # Truncation: 1.2999 truncates to 1.299 (not rounds to 1.300).
    a = quantize_cell(1.2999, 103.8500, precision=3)
    assert a == "cell:1.299,103.850"


def test_quantize_cell_precision_changes_bucket():
    a = quantize_cell(1.2901, 103.8501, precision=3)
    b = quantize_cell(1.2901, 103.8501, precision=4)
    assert a != b


def test_normalize_observation_window_reversed():
    with pytest.raises(ValueError):
        normalize_observation_window("2024-02-01T00:00:00Z", "2024-01-01T00:00:00Z")


def test_normalize_observation_window_too_large():
    with pytest.raises(ValueError):
        normalize_observation_window(
            "2020-01-01T00:00:00Z", "2030-01-01T00:00:00Z"
        )


def test_parse_period_start_end():
    s, e = parse_period({"start": "2024-01-01T00:00:00Z", "end": "2024-01-02T00:00:00Z"})
    assert s.startswith("2024-01-01")
    assert e.startswith("2024-01-02")


def test_parse_period_observation_keys():
    s, e = parse_period({"observation_start": "2024-01-01T00:00:00Z",
                         "observation_end": "2024-01-02T00:00:00Z"})
    assert s.startswith("2024-01-01")
    assert e.startswith("2024-01-02")


def test_parse_period_single_timestamp():
    s, e = parse_period({"timestamp": "2024-01-01T00:00:00Z"})
    assert s == e
