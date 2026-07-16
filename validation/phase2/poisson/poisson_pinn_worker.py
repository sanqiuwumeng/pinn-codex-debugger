"""Deterministic two-dimensional Poisson PINN worker using only PyTorch."""

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

import torch


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


class PoissonNet(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        layers: list[torch.nn.Module] = []
        widths = (2, 64, 64, 64, 1)
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
        y = points[:, 1:2]
        envelope = x * (1.0 - x) * y * (1.0 - y)
        return envelope * self.network(points)


def exact_solution(points: torch.Tensor) -> torch.Tensor:
    return torch.sin(math.pi * points[:, 0:1]) * torch.sin(
        math.pi * points[:, 1:2]
    )


def forcing(points: torch.Tensor) -> torch.Tensor:
    return 2.0 * math.pi**2 * exact_solution(points)


def pde_residual(
    model: PoissonNet, points: torch.Tensor, *, create_graph: bool
) -> torch.Tensor:
    active = points.detach().clone().requires_grad_(True)
    solution = model(active)
    first = torch.autograd.grad(
        solution,
        active,
        grad_outputs=torch.ones_like(solution),
        create_graph=True,
    )[0]
    second_x = torch.autograd.grad(
        first[:, 0:1],
        active,
        grad_outputs=torch.ones_like(first[:, 0:1]),
        create_graph=create_graph,
        retain_graph=True,
    )[0][:, 0:1]
    second_y = torch.autograd.grad(
        first[:, 1:2],
        active,
        grad_outputs=torch.ones_like(first[:, 1:2]),
        create_graph=create_graph,
    )[0][:, 1:2]
    return -second_x - second_y - forcing(active)


def sample_points(
    *,
    count: int,
    sampler: str,
    focus_x: float,
    focus_y: float,
    focus_fraction: float,
    focus_sigma: float,
) -> torch.Tensor:
    if sampler == "uniform":
        return torch.rand((count, 2))
    focus_count = int(round(count * focus_fraction))
    uniform_count = count - focus_count
    uniform = torch.rand((uniform_count, 2))
    center = torch.tensor((focus_x, focus_y)).reshape(1, 2)
    focused = center + focus_sigma * torch.randn((focus_count, 2))
    focused = focused.clamp(1.0e-6, 1.0 - 1.0e-6)
    return torch.cat((uniform, focused), dim=0)


def _configuration(mode: str) -> dict[str, Any]:
    if mode == "smoke":
        return {"epochs": 20, "collocation_points": 256, "evaluation_nodes": 33}
    if mode == "full":
        return {"epochs": 1800, "collocation_points": 2048, "evaluation_nodes": 65}
    raise ValueError(f"unsupported mode: {mode}")


def _evaluate(model: PoissonNet, nodes: int) -> dict[str, Any]:
    x = torch.linspace(0.0, 1.0, nodes)
    y = torch.linspace(0.0, 1.0, nodes)
    xx, yy = torch.meshgrid(x, y, indexing="ij")
    points = torch.stack((xx.reshape(-1), yy.reshape(-1)), dim=1)
    with torch.no_grad():
        prediction = model(points).reshape(nodes, nodes)
        reference = exact_solution(points).reshape(nodes, nodes)
    residual = pde_residual(model, points, create_graph=False).detach().reshape(
        nodes, nodes
    )
    boundary_error = prediction - reference
    error = prediction - reference
    reference_norm = torch.linalg.vector_norm(reference)
    metrics = {
        "relative_l2": float(torch.linalg.vector_norm(error) / reference_norm),
        "rmse": float(torch.sqrt(torch.mean(torch.square(error)))),
        "max_abs": float(torch.max(torch.abs(error))),
        "pde_residual_rms": float(torch.sqrt(torch.mean(torch.square(residual)))),
        "boundary_max_abs": float(
            torch.max(
                torch.abs(
                    torch.cat(
                        (
                            boundary_error[0, :],
                            boundary_error[-1, :],
                            boundary_error[1:-1, 0],
                            boundary_error[1:-1, -1],
                        )
                    )
                )
            )
        ),
    }
    return {
        "x": x.tolist(),
        "y": y.tolist(),
        "prediction": prediction.tolist(),
        "reference": reference.tolist(),
        "pde_residual": residual.tolist(),
        "boundary_error": boundary_error.tolist(),
        "metrics": metrics,
    }


def run(args: argparse.Namespace) -> None:
    output = args.output.resolve(strict=False)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite run output: {output}")
    output.mkdir(parents=True)
    config = _configuration(args.mode)
    seed = int(args.seed)
    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, int(args.threads)))

    model = PoissonNet()
    points = sample_points(
        count=config["collocation_points"],
        sampler=args.sampler,
        focus_x=args.focus_x,
        focus_y=args.focus_y,
        focus_fraction=args.focus_fraction,
        focus_sigma=args.focus_sigma,
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
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
        optimizer.step()
        scheduler.step()
        if epoch == 1 or epoch % 100 == 0 or epoch == config["epochs"]:
            item = {
                "epoch": epoch,
                "loss": float(loss.detach()),
                "learning_rate": float(scheduler.get_last_lr()[0]),
            }
            history.append(item)
            print(json.dumps(item), flush=True)

    duration = time.perf_counter() - started
    fields = _evaluate(model, config["evaluation_nodes"])
    contract = {
        "case_id": "poisson-manufactured-unit-square-v1",
        "equation": "negative_laplacian_u_equals_f",
        "domain": {"x": [0.0, 1.0], "y": [0.0, 1.0], "unit": "1"},
        "boundary": "homogeneous_dirichlet",
        "reference": "sin(pi*x)*sin(pi*y)",
        "forcing": "2*pi^2*sin(pi*x)*sin(pi*y)",
        "solution_channel": "u",
    }
    run_config = {
        "mode": args.mode,
        "seed": seed,
        "sampler": args.sampler,
        "focus": {
            "x": args.focus_x,
            "y": args.focus_y,
            "fraction": args.focus_fraction,
            "sigma": args.focus_sigma,
        },
        "training": config,
        "architecture": [2, 64, 64, 64, 1],
        "optimizer": "Adam",
        "learning_rate": 1.0e-3,
        "hard_boundary_ansatz": True,
    }
    _write_json(output / "case_contract.json", contract)
    _write_json(output / "run_config.json", run_config)
    _write_json(
        output / "runtime_environment.json",
        {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
    )
    _write_json(
        output / "training_history.json",
        {"duration_seconds": duration, "history": history},
    )
    _write_json(output / "field_metrics.json", fields["metrics"])
    _write_json(
        output / "aligned_fields.json",
        {key: value for key, value in fields.items() if key != "metrics"},
    )
    torch.save(model.state_dict(), output / "model.pt")
    generated = tuple(
        path for path in sorted(output.iterdir()) if path.name != "reproducibility_manifest.json"
    )
    _write_json(
        output / "reproducibility_manifest.json",
        {
            "seed": seed,
            "artifacts": {
                path.name: {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
                for path in generated
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--sampler", choices=("uniform", "focused"), required=True)
    parser.add_argument("--seed", type=int, default=314159)
    parser.add_argument("--focus-x", type=float, default=0.5)
    parser.add_argument("--focus-y", type=float, default=0.5)
    parser.add_argument("--focus-fraction", type=float, default=0.125)
    parser.add_argument("--focus-sigma", type=float, default=0.10)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
