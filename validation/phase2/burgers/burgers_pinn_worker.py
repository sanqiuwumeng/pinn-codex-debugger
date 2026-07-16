"""Deterministic PyTorch worker for the classic viscous Burgers PINN case."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

VISCOSITY = 0.01 / math.pi


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite worker output: {path}")
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


class BurgersNet(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        widths = (2, 64, 64, 64, 1)
        layers: list[torch.nn.Module] = []
        for index, (left, right) in enumerate(zip(widths[:-1], widths[1:])):
            layer = torch.nn.Linear(left, right)
            torch.nn.init.xavier_uniform_(layer.weight)
            torch.nn.init.zeros_(layer.bias)
            layers.append(layer)
            if index < len(widths) - 2:
                layers.append(torch.nn.Tanh())
        self.network = torch.nn.Sequential(*layers)

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        x = points[:, 0:1]
        time = points[:, 1:2]
        initial = -torch.sin(math.pi * x)
        envelope = time * (1.0 - torch.square(x))
        return initial + envelope * self.network(points)


def pde_residual(
    model: BurgersNet, points: torch.Tensor, *, create_graph: bool
) -> torch.Tensor:
    active = points.detach().clone().requires_grad_(True)
    solution = model(active)
    first = torch.autograd.grad(
        solution,
        active,
        grad_outputs=torch.ones_like(solution),
        create_graph=True,
    )[0]
    derivative_x = first[:, 0:1]
    derivative_t = first[:, 1:2]
    derivative_xx = torch.autograd.grad(
        derivative_x,
        active,
        grad_outputs=torch.ones_like(derivative_x),
        create_graph=create_graph,
    )[0][:, 0:1]
    return derivative_t + solution * derivative_x - VISCOSITY * derivative_xx


def sample_points(
    *,
    count: int,
    sampler: str,
    focus_x: float,
    focus_t: float,
    focus_fraction: float,
    sigma_x: float,
    sigma_t: float,
) -> torch.Tensor:
    if sampler == "uniform":
        uniform = torch.rand((count, 2))
        uniform[:, 0] = -1.0 + 2.0 * uniform[:, 0]
        return uniform
    focus_count = int(round(count * focus_fraction))
    uniform_count = count - focus_count
    uniform = torch.rand((uniform_count, 2))
    uniform[:, 0] = -1.0 + 2.0 * uniform[:, 0]
    focused_x = focus_x + sigma_x * torch.randn((focus_count, 1))
    focused_t = focus_t + sigma_t * torch.randn((focus_count, 1))
    focused = torch.cat(
        (
            focused_x.clamp(-1.0 + 1.0e-6, 1.0 - 1.0e-6),
            focused_t.clamp(1.0e-6, 1.0 - 1.0e-6),
        ),
        dim=1,
    )
    return torch.cat((uniform, focused), dim=0)


def _configuration(mode: str) -> dict[str, int]:
    if mode == "smoke":
        return {"epochs": 30, "collocation_points": 512}
    if mode == "full":
        return {"epochs": 2500, "collocation_points": 4096}
    raise ValueError(f"unsupported mode: {mode}")


def _residual_grid(
    model: BurgersNet, points: torch.Tensor, chunk_size: int = 2048
) -> torch.Tensor:
    values = []
    for start in range(0, len(points), chunk_size):
        values.append(
            pde_residual(
                model,
                points[start : start + chunk_size],
                create_graph=False,
            ).detach()
        )
    return torch.cat(values, dim=0)


def _evaluate(model: BurgersNet, reference_path: Path) -> dict[str, Any]:
    with np.load(reference_path, allow_pickle=False) as payload:
        x_numpy = np.asarray(payload["x"], dtype=np.float32)
        t_numpy = np.asarray(payload["t"], dtype=np.float32)
        reference_numpy = np.asarray(payload["u"], dtype=np.float32)
    x = torch.tensor(x_numpy)
    time_values = torch.tensor(t_numpy)
    tt, xx = torch.meshgrid(time_values, x, indexing="ij")
    points = torch.stack((xx.reshape(-1), tt.reshape(-1)), dim=1)
    with torch.no_grad():
        prediction = model(points).reshape(len(time_values), len(x))
    reference = torch.tensor(reference_numpy)
    residual = _residual_grid(model, points).reshape(len(time_values), len(x))
    error = prediction - reference
    gradient = np.gradient(reference_numpy.astype(float), x_numpy.astype(float), axis=1)
    threshold = float(np.percentile(np.abs(gradient), 90.0))
    high_gradient_mask = torch.tensor(np.abs(gradient) >= threshold)
    max_flat = int(torch.argmax(torch.abs(error)))
    max_index = np.unravel_index(max_flat, tuple(error.shape))
    metrics = {
        "relative_l2": float(torch.linalg.vector_norm(error) / torch.linalg.vector_norm(reference)),
        "rmse": float(torch.sqrt(torch.mean(torch.square(error)))),
        "max_abs": float(torch.max(torch.abs(error))),
        "max_abs_t": float(time_values[max_index[0]]),
        "max_abs_x": float(x[max_index[1]]),
        "pde_residual_rms": float(torch.sqrt(torch.mean(torch.square(residual)))),
        "initial_max_abs": float(torch.max(torch.abs(error[0]))),
        "boundary_max_abs": float(
            torch.max(torch.abs(torch.cat((error[:, 0], error[:, -1]))))
        ),
        "high_gradient_rmse": float(
            torch.sqrt(torch.mean(torch.square(error[high_gradient_mask])))
        ),
        "high_gradient_threshold": threshold,
    }
    return {
        "x": x_numpy,
        "t": t_numpy,
        "prediction": prediction.detach().numpy(),
        "reference": reference_numpy,
        "pde_residual": residual.detach().numpy(),
        "metrics": metrics,
    }


def run(args: argparse.Namespace) -> None:
    output = args.output.resolve(strict=False)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite run output: {output}")
    output.mkdir(parents=True)
    reference = args.reference.resolve(strict=True)
    config = _configuration(args.mode)
    seed = int(args.seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, int(args.threads)))

    model = BurgersNet()
    points = sample_points(
        count=config["collocation_points"],
        sampler=args.sampler,
        focus_x=args.focus_x,
        focus_t=args.focus_t,
        focus_fraction=args.focus_fraction,
        sigma_x=args.sigma_x,
        sigma_t=args.sigma_t,
    )
    optimizer = torch.optim.Adam(
        model.parameters(), lr=1.0e-3, weight_decay=1.0e-6
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config["epochs"], eta_min=1.0e-5
    )
    history = []
    started = time.perf_counter()
    for epoch in range(1, config["epochs"] + 1):
        optimizer.zero_grad(set_to_none=True)
        residual = pde_residual(model, points, create_graph=True)
        loss = torch.mean(torch.square(residual))
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError(f"non-finite loss at epoch {epoch}")
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(
            model.parameters(), max_norm=10.0
        )
        optimizer.step()
        scheduler.step()
        if epoch == 1 or epoch % 100 == 0 or epoch == config["epochs"]:
            item = {
                "epoch": epoch,
                "loss": float(loss.detach()),
                "gradient_norm": float(gradient_norm),
                "learning_rate": float(scheduler.get_last_lr()[0]),
            }
            history.append(item)
            print(json.dumps(item), flush=True)

    duration = time.perf_counter() - started
    evaluation = _evaluate(model, reference)
    case_contract = {
        "case_id": "viscous-burgers-standard-v1",
        "equation": "u_t + u*u_x - nu*u_xx = 0",
        "viscosity": VISCOSITY,
        "domain": {"x": [-1.0, 1.0], "t": [0.0, 1.0], "unit": "1"},
        "initial_condition": "-sin(pi*x)",
        "boundary_condition": "u(t,-1)=u(t,1)=0",
        "solution_channel": "u",
    }
    run_config = {
        "mode": args.mode,
        "seed": seed,
        "sampler": args.sampler,
        "focus": {
            "x": args.focus_x,
            "t": args.focus_t,
            "fraction": args.focus_fraction,
            "sigma_x": args.sigma_x,
            "sigma_t": args.sigma_t,
        },
        "training": config,
        "architecture": [2, 64, 64, 64, 1],
        "optimizer": "Adam",
        "learning_rate": 1.0e-3,
        "hard_initial_and_boundary_ansatz": True,
        "reference_sha256": _sha256(reference),
    }
    _write_json(output / "case_contract.json", case_contract)
    _write_json(output / "run_config.json", run_config)
    _write_json(
        output / "runtime_environment.json",
        {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
    )
    _write_json(
        output / "training_history.json",
        {"duration_seconds": duration, "history": history},
    )
    _write_json(output / "field_metrics.json", evaluation["metrics"])
    np.savez_compressed(
        output / "aligned_fields.npz",
        x=evaluation["x"],
        t=evaluation["t"],
        prediction=evaluation["prediction"],
        reference=evaluation["reference"],
        pde_residual=evaluation["pde_residual"],
    )
    torch.save(model.state_dict(), output / "model.pt")
    generated = tuple(
        path
        for path in sorted(output.iterdir())
        if path.name != "reproducibility_manifest.json"
    )
    _write_json(
        output / "reproducibility_manifest.json",
        {
            "seed": seed,
            "artifacts": {
                path.name: {
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in generated
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--sampler", choices=("uniform", "focused"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--focus-x", type=float, default=0.0)
    parser.add_argument("--focus-t", type=float, default=0.75)
    parser.add_argument("--focus-fraction", type=float, default=0.125)
    parser.add_argument("--sigma-x", type=float, default=0.15)
    parser.add_argument("--sigma-t", type=float, default=0.10)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
