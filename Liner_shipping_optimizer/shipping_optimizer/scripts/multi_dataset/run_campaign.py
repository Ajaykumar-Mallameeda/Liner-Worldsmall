#!/usr/bin/env python3
"""Run the accepted C3 pipeline on selected datasets and seeds, strictly one run after the other.

    python scripts/multi_dataset/run_campaign.py --datasets baltic WAF --seeds 0 1 2
    python scripts/multi_dataset/run_campaign.py --datasets World-500 --seeds 0 --wall-cap-sec 14400

Each run is ``tests/test_orchestrator.py --dataset D --seed S --output-dir <out-root>/<D>/seed<S>`` in its own
process with the C3 flags the test applies itself, ``PYTHONHASHSEED=0`` (the frozen reference's setting) and
nothing else changed: no solver option, no time limit, no cost parameter is touched here.

Per run the driver records (``driver_record.json``): command, UTC start/end, wall seconds, exit code, whether the
wall cap killed it (the cap is a safety net around the whole pipeline - it is NOT the 120 s solver budget, which
stays inside the pipeline untouched), the peak working set (Windows API) of the pipeline's python processes and of CBC, sampled every
~2 s (a lower bound of the true peak), and the machine description.
Failed, timed-out and killed runs are kept and reported like any other.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "reports" / "multi_dataset_20261016" / "runs"
sys.path.insert(0, str(ROOT))


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def _peak_ws_mb_of_pid(pid: int) -> float | None:
    """Exact peak working set (so far) of a process, by pid (Windows API)."""
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x0400 | 0x0010, False, int(pid))      # QUERY_INFORMATION | VM_READ
        if not h:
            return None
        try:
            pmc = _PMC()
            pmc.cb = ctypes.sizeof(pmc)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 2 ** 20 if ok else None
        finally:
            k32.CloseHandle(h)
    except Exception:                                    # noqa: BLE001
        return None


def _pids(image: str) -> list:
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, timeout=10).stdout
        pids = []
        for ln in out.splitlines():
            parts = [p.strip('"') for p in ln.split('","')]
            if len(parts) >= 2 and parts[1].strip('"').isdigit():
                pids.append(int(parts[1].strip('"')))
        return pids
    except Exception:                                    # noqa: BLE001
        return []


def sample_peaks(peaks: dict) -> None:
    """Running maxima of the peak working set. The pipeline's real interpreter is ``python3.11.exe`` (the venv
    ``python.exe`` is only a launcher stub); keys: ``python`` = largest single interpreter process, ``python_sum`` =
    largest sum of the per-process peaks over the interpreters alive at one sampling instant, ``cbc`` = largest CBC
    process. Sampled every ~2 s, so these are lower bounds of the true peaks."""
    me = os.getpid()
    py = [v for v in (_peak_ws_mb_of_pid(pid) for pid in _pids("python3*") if pid != me) if v is not None]
    if py:
        peaks["python"] = max(peaks.get("python", 0.0), max(py))
        peaks["python_sum"] = max(peaks.get("python_sum", 0.0), sum(py))
    cb = [v for v in (_peak_ws_mb_of_pid(pid) for pid in _pids("cbc.exe")) if v is not None]
    if cb:
        peaks["cbc"] = max(peaks.get("cbc", 0.0), max(cb))


def machine() -> dict:
    info = {"platform": platform.platform(), "python": sys.version.split()[0], "cpu_count": os.cpu_count()}
    try:
        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ctypes.sizeof(ms)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        info["ram_total_gb"] = round(ms.ullTotalPhys / 2 ** 30, 1)
        info["ram_available_gb_at_start"] = round(ms.ullAvailPhys / 2 ** 30, 1)
    except Exception:                                    # noqa: BLE001
        pass
    try:
        import pulp
        info["pulp"] = pulp.__version__
        info["cbc"] = "2.10.3 (bundled with PuLP)"
    except Exception:                                    # noqa: BLE001
        pass
    return info


def run_one(dataset: str, seed: int, out_root: Path, wall_cap: float | None, extra_env: dict,
            out_dir: Path | None = None) -> dict:
    """``out_dir`` (optional) replaces the default ``<out_root>/<dataset>/seed<S>`` run directory."""
    out = out_dir if out_dir is not None else out_root / dataset / f"seed{seed}"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "tests" / "test_orchestrator.py"), "--dataset", dataset, "--non-interactive",
           "--seed", str(seed), "--output-dir", str(out)]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env.update(extra_env)
    rec = {"dataset": dataset, "seed": seed, "command": cmd, "output_dir": str(out), "wall_cap_sec": wall_cap,
           "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "machine": machine()}
    t0 = time.perf_counter()
    peaks: dict = {}
    with open(out / "run.log", "wb") as log:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        timed_out = False
        while True:
            try:
                proc.wait(timeout=2)
                break
            except subprocess.TimeoutExpired:
                sample_peaks(peaks)
                if wall_cap and time.perf_counter() - t0 > wall_cap:
                    timed_out = True
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
                    proc.wait()
                    break
    rec.update({"wall_sec": round(time.perf_counter() - t0, 1), "exit_code": proc.returncode, "killed_by_wall_cap": timed_out,
                "peak_working_set_mb_python_sampled": round(peaks.get("python", 0.0), 1),
                "peak_working_set_mb_python_sum_sampled": round(peaks.get("python_sum", 0.0), 1),
                "peak_working_set_mb_cbc_sampled": round(peaks.get("cbc", 0.0), 1),
                "ended_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "has_pipeline_output": (out / "pipeline_output.json").is_file()})
    (out / "driver_record.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--wall-cap-sec", type=float, default=None, help="kill a run that exceeds this wall time (recorded)")
    ap.add_argument("--skip-existing", action="store_true", help="skip runs whose driver_record.json exists")
    a = ap.parse_args(argv)
    from src.data.dataset_registry import resolve_dataset
    keys = [resolve_dataset(d).key for d in a.datasets]
    rc = 0
    for key in keys:
        for seed in a.seeds:
            if a.skip_existing and (a.out_root / key / f"seed{seed}" / "driver_record.json").is_file():
                print(f"[{key} seed {seed}] skipped (record exists)")
                continue
            print(f"[{key} seed {seed}] running ...", flush=True)
            r = run_one(key, seed, a.out_root, a.wall_cap_sec, {})
            print(f"[{key} seed {seed}] exit={r['exit_code']} wall={r['wall_sec']} s killed={r['killed_by_wall_cap']} "
                  f"output={'yes' if r['has_pipeline_output'] else 'NO'} peakWS python={r['peak_working_set_mb_python_sampled']} MB cbc={r['peak_working_set_mb_cbc_sampled']} MB", flush=True)
            rc |= 1 if r["exit_code"] else 0
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
