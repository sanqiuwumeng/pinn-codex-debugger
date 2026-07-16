"""Prepare and finalize an independent OpenFOAM lid-cavity reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import RegularGridInterpolator

REYNOLDS_NUMBER = 100.0
VISCOSITY = 1.0 / REYNOLDS_NUMBER
GRID_LEVELS = (32, 64, 128)
EVALUATION_NODES = 65
END_TIME = 30.0
WRITE_INTERVAL_TIME = 5.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite reference input: {path}")
    path.write_text(content.strip() + "\n", encoding="utf-8", newline="\n")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
    )


def _foam_header(class_name: str, object_name: str, location: str | None = None) -> str:
    location_line = f'    location    "{location}";\n' if location else ""
    return f"""
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {class_name};
{location_line}    object      {object_name};
}}
"""


def _case_files(grid: int) -> dict[str, str]:
    delta_t = 0.25 / grid
    write_interval = int(round(WRITE_INTERVAL_TIME / delta_t))
    block_mesh = _foam_header("dictionary", "blockMeshDict") + f"""
convertToMeters 1;
vertices
(
    (0 0 0) (1 0 0) (1 1 0) (0 1 0)
    (0 0 0.01) (1 0 0.01) (1 1 0.01) (0 1 0.01)
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({grid} {grid} 1) simpleGrading (1 1 1)
);
edges ();
boundary
(
    movingWall
    {{
        type wall;
        faces ((3 7 6 2));
    }}
    fixedWalls
    {{
        type wall;
        faces ((0 4 7 3) (2 6 5 1) (1 5 4 0));
    }}
    frontAndBack
    {{
        type empty;
        faces ((0 3 2 1) (4 5 6 7));
    }}
);
mergePatchPairs ();
"""
    velocity = _foam_header("volVectorField", "U", "0") + """
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    movingWall
    {
        type fixedValue;
        value uniform (1 0 0);
    }
    fixedWalls
    {
        type noSlip;
    }
    frontAndBack
    {
        type empty;
    }
}
"""
    pressure = _foam_header("volScalarField", "p", "0") + """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    movingWall
    {
        type zeroGradient;
    }
    fixedWalls
    {
        type zeroGradient;
    }
    frontAndBack
    {
        type empty;
    }
}
"""
    transport = _foam_header(
        "dictionary", "transportProperties", "constant"
    ) + f"""
nu [0 2 -1 0 0 0 0] {VISCOSITY:.17g};
"""
    control = _foam_header("dictionary", "controlDict", "system") + f"""
application icoFoam;
startFrom startTime;
startTime 0;
stopAt endTime;
endTime {END_TIME:g};
deltaT {delta_t:.17g};
writeControl timeStep;
writeInterval {write_interval};
purgeWrite 0;
writeFormat ascii;
writePrecision 12;
writeCompression off;
timeFormat general;
timePrecision 10;
runTimeModifiable false;
"""
    schemes = _foam_header("dictionary", "fvSchemes", "system") + """
ddtSchemes
{
    default Euler;
}
gradSchemes
{
    default Gauss linear;
    grad(p) Gauss linear;
}
divSchemes
{
    default none;
    div(phi,U) Gauss linear;
}
laplacianSchemes
{
    default Gauss linear orthogonal;
}
interpolationSchemes
{
    default linear;
}
snGradSchemes
{
    default orthogonal;
}
"""
    solution = _foam_header("dictionary", "fvSolution", "system") + """
solvers
{
    p
    {
        solver PCG;
        preconditioner DIC;
        tolerance 1e-9;
        relTol 0;
    }
    pFinal
    {
        $p;
        relTol 0;
    }
    U
    {
        solver smoothSolver;
        smoother symGaussSeidel;
        tolerance 1e-10;
        relTol 0;
    }
}
PISO
{
    nCorrectors 3;
    nNonOrthogonalCorrectors 0;
    pRefCell 0;
    pRefValue 0;
}
"""
    return {
        "0/U": velocity,
        "0/p": pressure,
        "constant/transportProperties": transport,
        "system/blockMeshDict": block_mesh,
        "system/controlDict": control,
        "system/fvSchemes": schemes,
        "system/fvSolution": solution,
    }


def prepare(root: Path) -> None:
    root = root.resolve(strict=False)
    if root.exists():
        raise FileExistsError(f"refusing to overwrite reference root: {root}")
    root.mkdir(parents=True)
    for grid in GRID_LEVELS:
        case = root / f"grid-{grid}"
        for relative, content in _case_files(grid).items():
            _write_text(case / relative, content)
        _write_json(
            case / "case-metadata.json",
            {
                "solver": "OpenFOAM-6 icoFoam",
                "grid_cells": [grid, grid, 1],
                "reynolds_number": REYNOLDS_NUMBER,
                "viscosity": VISCOSITY,
                "delta_t": 0.25 / grid,
                "end_time": END_TIME,
                "write_interval_time": WRITE_INTERVAL_TIME,
            },
        )
    _write_json(
        root / "prepared-reference.json",
        {
            "case_id": "lid-driven-cavity-re100-v1",
            "grid_levels": list(GRID_LEVELS),
            "evaluation_nodes": EVALUATION_NODES,
            "reference_method": "independent OpenFOAM-6 icoFoam finite volume solve",
        },
    )
    print(json.dumps({"status": "PREPARED", "root": str(root)}))


def _latest_times(case: Path) -> list[tuple[float, Path]]:
    times: list[tuple[float, Path]] = []
    for path in case.iterdir():
        if not path.is_dir():
            continue
        try:
            value = float(path.name)
        except ValueError:
            continue
        if value > 0 and (path / "U").is_file() and (path / "p").is_file():
            times.append((value, path))
    return sorted(times)


def _internal_block(path: Path) -> tuple[str, int, str]:
    text = path.read_text(encoding="utf-8", errors="strict")
    match = re.search(
        r"internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"nonuniform internal field not found: {path}")
    return match.group(1), int(match.group(2)), match.group(3)


def _parse_field(path: Path) -> np.ndarray:
    kind, count, body = _internal_block(path)
    if kind == "vector":
        rows = re.findall(r"\(([^()]+)\)", body)
        values = np.asarray(
            [[float(item) for item in row.split()] for row in rows], dtype=float
        )
    else:
        values = np.fromstring(body, sep=" ", dtype=float)
    if len(values) != count:
        raise ValueError(f"field length mismatch in {path}: {len(values)} != {count}")
    return values


def _read_snapshot(time_path: Path, grid: int) -> dict[str, np.ndarray]:
    velocity = _parse_field(time_path / "U")
    pressure = _parse_field(time_path / "p")
    if len(velocity) != grid * grid or len(pressure) != grid * grid:
        raise ValueError(f"unexpected cell count in {time_path}")
    u = velocity[:, 0].reshape((grid, grid))
    v = velocity[:, 1].reshape((grid, grid))
    p = pressure.reshape((grid, grid))
    centers = (np.arange(grid, dtype=float) + 0.5) / grid
    return {"x": centers, "y": centers, "u": u, "v": v, "p": p}


def _interpolate(snapshot: dict[str, np.ndarray], evaluation: np.ndarray) -> dict[str, np.ndarray]:
    yy, xx = np.meshgrid(evaluation, evaluation, indexing="ij")
    query = np.column_stack((yy.ravel(), xx.ravel()))
    result: dict[str, np.ndarray] = {"x": evaluation, "y": evaluation}
    for name in ("u", "v", "p"):
        interpolator = RegularGridInterpolator(
            (snapshot["y"], snapshot["x"]),
            snapshot[name],
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        result[name] = interpolator(query).reshape((len(evaluation), len(evaluation)))
    result["u"][0, :] = 0.0
    result["u"][-1, :] = 1.0
    result["u"][:, [0, -1]] = 0.0
    result["v"][[0, -1], :] = 0.0
    result["v"][:, [0, -1]] = 0.0
    result["p"] -= float(np.mean(result["p"]))
    return result


def _velocity_relative_l2(left: dict[str, np.ndarray], right: dict[str, np.ndarray]) -> float:
    numerator = np.sqrt(np.sum(np.square(left["u"] - right["u"]) + np.square(left["v"] - right["v"])))
    denominator = np.sqrt(np.sum(np.square(right["u"]) + np.square(right["v"])))
    return float(numerator / denominator)


def _ghia_metrics(field: dict[str, np.ndarray], ghia: dict[str, Any]) -> dict[str, float]:
    evaluation = field["x"]
    center = int(np.argmin(np.abs(evaluation - 0.5)))
    u_data = ghia["u_on_vertical_centerline"]
    v_data = ghia["v_on_horizontal_centerline"]
    predicted_u = np.interp(
        np.asarray(u_data["y"], dtype=float), evaluation, field["u"][:, center]
    )
    predicted_v = np.interp(
        np.asarray(v_data["x"], dtype=float), evaluation, field["v"][center, :]
    )
    u_error = predicted_u - np.asarray(u_data["u"], dtype=float)
    v_error = predicted_v - np.asarray(v_data["v"], dtype=float)
    return {
        "u_centerline_rmse": float(np.sqrt(np.mean(np.square(u_error)))),
        "v_centerline_rmse": float(np.sqrt(np.mean(np.square(v_error)))),
        "combined_centerline_rmse": float(
            np.sqrt(np.mean(np.concatenate((np.square(u_error), np.square(v_error)))))
        ),
        "u_centerline_max_abs": float(np.max(np.abs(u_error))),
        "v_centerline_max_abs": float(np.max(np.abs(v_error))),
    }


def finalize(root: Path, ghia_path: Path) -> None:
    root = root.resolve(strict=True)
    ghia_path = ghia_path.resolve(strict=True)
    ghia = json.loads(ghia_path.read_text(encoding="utf-8"))
    evaluation = np.linspace(0.0, 1.0, EVALUATION_NODES)
    fields: list[dict[str, np.ndarray]] = []
    levels = []
    for grid in GRID_LEVELS:
        case = root / f"grid-{grid}"
        times = _latest_times(case)
        if len(times) < 2 or abs(times[-1][0] - END_TIME) > 1.0e-9:
            raise RuntimeError(f"grid {grid} is incomplete: {times[-2:]}")
        previous = _interpolate(_read_snapshot(times[-2][1], grid), evaluation)
        final = _interpolate(_read_snapshot(times[-1][1], grid), evaluation)
        temporal = _velocity_relative_l2(previous, final)
        ghia_metrics = _ghia_metrics(final, ghia)
        fields.append(final)
        levels.append(
            {
                "grid": grid,
                "final_time": times[-1][0],
                "previous_time": times[-2][0],
                "final_interval_velocity_relative_l2": temporal,
                "ghia": ghia_metrics,
                "finite": bool(
                    np.isfinite(final["u"]).all()
                    and np.isfinite(final["v"]).all()
                    and np.isfinite(final["p"]).all()
                ),
                "log_sha256": _sha256(case / "icoFoam.log"),
            }
        )
    coarse_to_medium = _velocity_relative_l2(fields[0], fields[1])
    medium_to_fine = _velocity_relative_l2(fields[1], fields[2])
    convergence = {
        "case_id": "lid-driven-cavity-re100-v1",
        "solver": "OpenFOAM-6 icoFoam",
        "reynolds_number": REYNOLDS_NUMBER,
        "viscosity": VISCOSITY,
        "grid_levels": levels,
        "coarse_to_medium_velocity_relative_l2": coarse_to_medium,
        "medium_to_fine_velocity_relative_l2": medium_to_fine,
        "observed_reduction_ratio": medium_to_fine / coarse_to_medium,
        "ghia_source_sha256": _sha256(ghia_path),
        "checks": {
            "all_levels_finite": all(level["finite"] for level in levels),
            "all_levels_temporally_steady": all(
                level["final_interval_velocity_relative_l2"] <= 0.005
                for level in levels
            ),
            "successive_grid_difference_reduces": medium_to_fine < coarse_to_medium,
            "fine_pair_velocity_relative_l2_at_most_0_03": medium_to_fine <= 0.03,
            "fine_ghia_centerline_rmse_at_most_0_03": (
                levels[-1]["ghia"]["combined_centerline_rmse"] <= 0.03
            ),
        },
    }
    convergence["status"] = (
        "PASS" if all(convergence["checks"].values()) else "FAIL"
    )
    fields_path = root / "reference_fields.npz"
    if fields_path.exists():
        raise FileExistsError(f"refusing to overwrite reference: {fields_path}")
    fine = fields[-1]
    dy = float(evaluation[1] - evaluation[0])
    dx = dy
    p_y, p_x = np.gradient(fine["p"], dy, dx, edge_order=2)
    np.savez_compressed(
        fields_path,
        x=evaluation,
        y=evaluation,
        u=fine["u"],
        v=fine["v"],
        p=fine["p"],
        p_x=p_x,
        p_y=p_y,
        u_medium=fields[1]["u"],
        v_medium=fields[1]["v"],
        u_coarse=fields[0]["u"],
        v_coarse=fields[0]["v"],
    )
    convergence_path = root / "reference_convergence.json"
    _write_json(convergence_path, convergence)
    _write_json(
        root / "reference_manifest.json",
        {
            "artifacts": {
                path.name: {
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in (fields_path, convergence_path, ghia_path)
            }
        },
    )
    if convergence["status"] != "PASS":
        raise RuntimeError("lid-cavity reference failed a frozen gate")
    print(json.dumps({"status": "PASS", "root": str(root)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--root", type=Path, required=True)
    finalize_parser.add_argument("--ghia", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.root)
    else:
        finalize(args.root, args.ghia)


if __name__ == "__main__":
    main()
