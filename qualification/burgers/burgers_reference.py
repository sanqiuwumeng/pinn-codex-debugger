"""Independent converged numerical reference for the viscous Burgers case."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

VISCOSITY = 0.01 / math.pi
GRID_LEVELS = (513, 1025, 2049)
EVALUATION_NODES_X = 257
EVALUATION_NODES_T = 101


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite reference evidence: {path}")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rhs(values: np.ndarray, dx: float) -> np.ndarray:
    result = np.zeros_like(values)
    flux = 0.5 * np.square(values)
    result[1:-1] = (
        -(flux[2:] - flux[:-2]) / (2.0 * dx)
        + VISCOSITY
        * (values[2:] - 2.0 * values[1:-1] + values[:-2])
        / (dx * dx)
    )
    return result


def _rk4_step(values: np.ndarray, dx: float, dt: float) -> np.ndarray:
    k1 = _rhs(values, dx)
    stage = values + 0.5 * dt * k1
    stage[[0, -1]] = 0.0
    k2 = _rhs(stage, dx)
    stage = values + 0.5 * dt * k2
    stage[[0, -1]] = 0.0
    k3 = _rhs(stage, dx)
    stage = values + dt * k3
    stage[[0, -1]] = 0.0
    k4 = _rhs(stage, dx)
    updated = values + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    updated[[0, -1]] = 0.0
    return updated


def solve(nodes: int, evaluation_x: np.ndarray, evaluation_t: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    x = np.linspace(-1.0, 1.0, nodes)
    dx = float(x[1] - x[0])
    values = -np.sin(math.pi * x)
    values[[0, -1]] = 0.0
    snapshots = np.empty((len(evaluation_t), len(evaluation_x)), dtype=np.float64)
    snapshots[0] = np.interp(evaluation_x, x, values)
    current_time = 0.0
    step_count = 0
    started = time.perf_counter()
    for output_index, target_time in enumerate(evaluation_t[1:], start=1):
        while current_time < target_time - 1.0e-15:
            max_speed = max(float(np.max(np.abs(values))), 1.0e-12)
            convection_limit = 0.35 * dx / max_speed
            diffusion_limit = 0.20 * dx * dx / VISCOSITY
            dt = min(convection_limit, diffusion_limit, float(target_time - current_time))
            values = _rk4_step(values, dx, dt)
            if not np.isfinite(values).all():
                raise FloatingPointError(f"reference solve became non-finite at grid {nodes}")
            current_time += dt
            step_count += 1
        snapshots[output_index] = np.interp(evaluation_x, x, values)
    elapsed = time.perf_counter() - started
    return snapshots, {
        "nodes": nodes,
        "dx": dx,
        "steps": step_count,
        "elapsed_seconds": elapsed,
        "minimum": float(np.min(snapshots)),
        "maximum": float(np.max(snapshots)),
        "finite": bool(np.isfinite(snapshots).all()),
    }


def relative_l2(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(left - right) / np.linalg.norm(right))


def run(output: Path) -> None:
    output = output.resolve(strict=False)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite reference root: {output}")
    output.mkdir(parents=True)
    evaluation_x = np.linspace(-1.0, 1.0, EVALUATION_NODES_X)
    evaluation_t = np.linspace(0.0, 1.0, EVALUATION_NODES_T)
    fields = []
    levels = []
    for nodes in GRID_LEVELS:
        field, metadata = solve(nodes, evaluation_x, evaluation_t)
        fields.append(field)
        levels.append(metadata)
        print(json.dumps(metadata), flush=True)

    coarse_to_medium = relative_l2(fields[0], fields[1])
    medium_to_fine = relative_l2(fields[1], fields[2])
    convergence = {
        "case_id": "viscous-burgers-standard-v1",
        "equation": "u_t + u*u_x - nu*u_xx = 0",
        "viscosity": VISCOSITY,
        "domain": {"x": [-1.0, 1.0], "t": [0.0, 1.0]},
        "initial_condition": "-sin(pi*x)",
        "boundary_condition": "u(t,-1)=u(t,1)=0",
        "method": "second-order conservative centered space with explicit RK4",
        "levels": levels,
        "coarse_to_medium_relative_l2": coarse_to_medium,
        "medium_to_fine_relative_l2": medium_to_fine,
        "observed_reduction_ratio": medium_to_fine / coarse_to_medium,
        "checks": {
            "all_levels_finite": all(item["finite"] for item in levels),
            "successive_difference_reduces": medium_to_fine < coarse_to_medium,
            "fine_pair_relative_l2_at_most_0_005": medium_to_fine <= 0.005,
            "initial_condition_exact": bool(
                np.max(np.abs(fields[2][0] + np.sin(math.pi * evaluation_x)))
                <= 1.0e-12
            ),
            "boundary_condition_exact": bool(
                np.max(np.abs(fields[2][:, [0, -1]])) <= 1.0e-12
            ),
        },
    }
    convergence["status"] = (
        "PASS" if all(convergence["checks"].values()) else "FAIL"
    )
    fields_path = output / "reference_fields.npz"
    np.savez_compressed(
        fields_path,
        x=evaluation_x,
        t=evaluation_t,
        u=fields[2],
        u_medium=fields[1],
        u_coarse=fields[0],
    )
    convergence_path = output / "reference_convergence.json"
    _write_json(convergence_path, convergence)
    _write_json(
        output / "reference_environment.json",
        {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    )
    artifact_paths = (
        fields_path,
        convergence_path,
        output / "reference_environment.json",
    )
    _write_json(
        output / "reference_manifest.json",
        {
            "artifacts": {
                path.name: {
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in artifact_paths
            }
        },
    )
    if convergence["status"] != "PASS":
        raise RuntimeError("Burgers numerical reference failed convergence gates")
    print(json.dumps({"status": "PASS", "output": str(output)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
