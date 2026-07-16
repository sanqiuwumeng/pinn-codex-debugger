"""Deterministic multi-output PINN worker for the Re=100 lid cavity."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

REYNOLDS_NUMBER = 100.0
VISCOSITY = 1.0 / REYNOLDS_NUMBER


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


class CavityNet(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        widths = (2, 96, 96, 96, 96, 3)
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
        y = points[:, 1:2]
        raw = self.network(points)
        side_distance = x * (1.0 - x)
        top_distance_squared = torch.square(1.0 - y)
        denominator = side_distance + top_distance_squared
        base_u = torch.where(
            denominator > 1.0e-12,
            y * side_distance / denominator.clamp_min(1.0e-12),
            torch.zeros_like(denominator),
        )
        envelope = side_distance * y * (1.0 - y)
        u = base_u + envelope * raw[:, 0:1]
        v = envelope * raw[:, 1:2]
        p = raw[:, 2:3]
        return torch.cat((u, v, p), dim=1)


def _gradient(
    values: torch.Tensor,
    points: torch.Tensor,
    *,
    create_graph: bool,
) -> torch.Tensor:
    return torch.autograd.grad(
        values,
        points,
        grad_outputs=torch.ones_like(values),
        create_graph=create_graph,
        retain_graph=True,
    )[0]


def pde_residual(
    model: CavityNet,
    points: torch.Tensor,
    *,
    create_graph: bool,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    active = points.detach().clone().requires_grad_(True)
    fields = model(active)
    u = fields[:, 0:1]
    v = fields[:, 1:2]
    p = fields[:, 2:3]
    grad_u = _gradient(u, active, create_graph=True)
    grad_v = _gradient(v, active, create_graph=True)
    grad_p = _gradient(p, active, create_graph=create_graph)
    u_x, u_y = grad_u[:, 0:1], grad_u[:, 1:2]
    v_x, v_y = grad_v[:, 0:1], grad_v[:, 1:2]
    u_xx = _gradient(u_x, active, create_graph=create_graph)[:, 0:1]
    u_yy = _gradient(u_y, active, create_graph=create_graph)[:, 1:2]
    v_xx = _gradient(v_x, active, create_graph=create_graph)[:, 0:1]
    v_yy = _gradient(v_y, active, create_graph=create_graph)[:, 1:2]
    continuity = u_x + v_y
    momentum_x = (
        u * u_x
        + v * u_y
        + grad_p[:, 0:1]
        - VISCOSITY * (u_xx + u_yy)
    )
    momentum_y = (
        u * v_x
        + v * v_y
        + grad_p[:, 1:2]
        - VISCOSITY * (v_xx + v_yy)
    )
    return continuity, momentum_x, momentum_y, fields


def sample_points(
    *,
    count: int,
    sampler: str,
    focus_x: float,
    focus_y: float,
    focus_fraction: float,
    sigma: float,
    device: torch.device,
) -> torch.Tensor:
    epsilon = 1.0e-4
    if sampler == "uniform":
        return epsilon + (1.0 - 2.0 * epsilon) * torch.rand(
            (count, 2), device=device
        )
    focus_count = int(round(count * focus_fraction))
    uniform_count = count - focus_count
    uniform = epsilon + (1.0 - 2.0 * epsilon) * torch.rand(
        (uniform_count, 2), device=device
    )
    focused = torch.cat(
        (
            focus_x + sigma * torch.randn((focus_count, 1), device=device),
            focus_y + sigma * torch.randn((focus_count, 1), device=device),
        ),
        dim=1,
    ).clamp(epsilon, 1.0 - epsilon)
    return torch.cat((uniform, focused), dim=0)


def _configuration(mode: str) -> dict[str, int]:
    if mode == "smoke":
        return {"epochs": 20, "collocation_points": 512}
    if mode == "full":
        return {"epochs": 6000, "collocation_points": 8192}
    raise ValueError(f"unsupported mode: {mode}")


def _residual_grid(
    model: CavityNet,
    x: torch.Tensor,
    y: torch.Tensor,
    *,
    chunk_size: int = 1024,
) -> tuple[torch.Tensor, torch.Tensor]:
    inner_y, inner_x = torch.meshgrid(y[1:-1], x[1:-1], indexing="ij")
    inner_points = torch.stack((inner_x.reshape(-1), inner_y.reshape(-1)), dim=1)
    continuity_values = []
    momentum_values = []
    for start in range(0, len(inner_points), chunk_size):
        continuity, momentum_x, momentum_y, _ = pde_residual(
            model,
            inner_points[start : start + chunk_size],
            create_graph=False,
        )
        continuity_values.append(continuity.detach())
        momentum_values.append(torch.cat((momentum_x, momentum_y), dim=1).detach())
    inner_shape = (len(y) - 2, len(x) - 2)
    continuity_grid = torch.zeros((len(y), len(x)), device=x.device)
    momentum_grid = torch.zeros((len(y), len(x), 2), device=x.device)
    continuity_grid[1:-1, 1:-1] = torch.cat(continuity_values).reshape(inner_shape)
    momentum_grid[1:-1, 1:-1, :] = torch.cat(momentum_values).reshape(
        (*inner_shape, 2)
    )
    return continuity_grid, momentum_grid


def _evaluate(
    model: CavityNet,
    reference_path: Path,
    device: torch.device,
) -> dict[str, Any]:
    with np.load(reference_path, allow_pickle=False) as payload:
        x_numpy = np.asarray(payload["x"], dtype=np.float32)
        y_numpy = np.asarray(payload["y"], dtype=np.float32)
        reference_u = np.asarray(payload["u"], dtype=np.float32)
        reference_v = np.asarray(payload["v"], dtype=np.float32)
        reference_p = np.asarray(payload["p"], dtype=np.float32)
        reference_p_x = np.asarray(payload["p_x"], dtype=np.float32)
        reference_p_y = np.asarray(payload["p_y"], dtype=np.float32)
    x = torch.tensor(x_numpy, device=device)
    y = torch.tensor(y_numpy, device=device)
    yy, xx = torch.meshgrid(y, x, indexing="ij")
    points = torch.stack((xx.reshape(-1), yy.reshape(-1)), dim=1)
    with torch.no_grad():
        fields = model(points).reshape(len(y), len(x), 3)
    prediction_velocity = fields[:, :, :2]
    prediction_p = fields[:, :, 2]
    prediction_p = prediction_p - torch.mean(prediction_p)
    continuity, momentum = _residual_grid(model, x, y)
    reference_velocity = torch.tensor(
        np.stack((reference_u, reference_v), axis=2), device=device
    )
    velocity_error = prediction_velocity - reference_velocity
    vector_error = torch.sqrt(torch.sum(torch.square(velocity_error), dim=2))
    max_flat = int(torch.argmax(vector_error))
    max_index = np.unravel_index(max_flat, tuple(vector_error.shape))
    center_x = int(torch.argmin(torch.abs(x - 0.5)))
    center_y = int(torch.argmin(torch.abs(y - 0.5)))
    centerline_error = torch.cat(
        (velocity_error[:, center_x, 0], velocity_error[center_y, :, 1])
    )
    boundary_error = torch.cat(
        (
            vector_error[0, 1:-1],
            vector_error[-1, 1:-1],
            vector_error[1:-1, 0],
            vector_error[1:-1, -1],
        )
    )
    prediction_p_numpy = prediction_p.detach().cpu().numpy()
    p_y, p_x = np.gradient(
        prediction_p_numpy,
        y_numpy.astype(float),
        x_numpy.astype(float),
        edge_order=2,
    )
    reference_gradient = np.stack((reference_p_x, reference_p_y), axis=2)
    prediction_gradient = np.stack((p_x, p_y), axis=2)
    metrics = {
        "velocity_relative_l2": float(
            torch.linalg.vector_norm(velocity_error)
            / torch.linalg.vector_norm(reference_velocity)
        ),
        "velocity_vector_max_abs": float(torch.max(vector_error)),
        "velocity_vector_max_abs_x": float(x[max_index[1]]),
        "velocity_vector_max_abs_y": float(y[max_index[0]]),
        "centerline_velocity_rmse": float(
            torch.sqrt(torch.mean(torch.square(centerline_error)))
        ),
        "wall_velocity_max_abs": float(torch.max(boundary_error)),
        "continuity_rms": float(
            torch.sqrt(torch.mean(torch.square(continuity[1:-1, 1:-1])))
        ),
        "momentum_rms": float(
            torch.sqrt(
                torch.mean(
                    torch.sum(torch.square(momentum[1:-1, 1:-1, :]), dim=2)
                )
            )
        ),
        "pressure_mean_abs": float(torch.abs(torch.mean(prediction_p))),
        "pressure_gradient_relative_l2": float(
            np.linalg.norm(prediction_gradient - reference_gradient)
            / np.linalg.norm(reference_gradient)
        ),
    }
    return {
        "x": x_numpy,
        "y": y_numpy,
        "prediction_velocity": prediction_velocity.detach().cpu().numpy(),
        "reference_velocity": reference_velocity.detach().cpu().numpy(),
        "prediction_p": prediction_p_numpy,
        "reference_p": reference_p,
        "continuity": continuity.detach().cpu().numpy(),
        "momentum": momentum.detach().cpu().numpy(),
        "prediction_pressure_gradient": prediction_gradient,
        "reference_pressure_gradient": reference_gradient,
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
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(max(1, int(args.threads)))
    device = torch.device(
        "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    )
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    model = CavityNet().to(device)
    points = sample_points(
        count=config["collocation_points"],
        sampler=args.sampler,
        focus_x=args.focus_x,
        focus_y=args.focus_y,
        focus_fraction=args.focus_fraction,
        sigma=args.sigma,
        device=device,
    )
    optimizer = torch.optim.Adam(
        model.parameters(), lr=8.0e-4, weight_decay=1.0e-7
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config["epochs"], eta_min=1.0e-5
    )
    history = []
    started = time.perf_counter()
    for epoch in range(1, config["epochs"] + 1):
        optimizer.zero_grad(set_to_none=True)
        continuity, momentum_x, momentum_y, fields = pde_residual(
            model, points, create_graph=True
        )
        continuity_loss = torch.mean(torch.square(continuity))
        momentum_loss = torch.mean(
            torch.square(momentum_x) + torch.square(momentum_y)
        )
        gauge_loss = torch.square(torch.mean(fields[:, 2]))
        loss = continuity_loss + momentum_loss + 0.01 * gauge_loss
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
                "continuity_loss": float(continuity_loss.detach()),
                "momentum_loss": float(momentum_loss.detach()),
                "gauge_loss": float(gauge_loss.detach()),
                "gradient_norm": float(gradient_norm),
                "learning_rate": float(scheduler.get_last_lr()[0]),
            }
            history.append(item)
            print(json.dumps(item), flush=True)

    duration = time.perf_counter() - started
    evaluation = _evaluate(model, reference, device)
    _write_json(
        output / "case_contract.json",
        {
            "case_id": "lid-driven-cavity-re100-v1",
            "equations": (
                "div(u)=0; u*du/dx+v*du/dy+dp/dx-(1/Re)laplacian(u)=0; "
                "u*dv/dx+v*dv/dy+dp/dy-(1/Re)laplacian(v)=0"
            ),
            "reynolds_number": REYNOLDS_NUMBER,
            "domain": {"x": [0.0, 1.0], "y": [0.0, 1.0], "unit": "1"},
            "boundary_condition": (
                "top u=1,v=0; bottom and side walls u=v=0; corners use side-wall convention"
            ),
            "pressure_gauge": "zero mean",
            "output_channels": ["u", "v", "p"],
        },
    )
    _write_json(
        output / "run_config.json",
        {
            "mode": args.mode,
            "seed": seed,
            "sampler": args.sampler,
            "focus": {
                "x": args.focus_x,
                "y": args.focus_y,
                "fraction": args.focus_fraction,
                "sigma": args.sigma,
            },
            "training": config,
            "architecture": [2, 96, 96, 96, 96, 3],
            "optimizer": "Adam",
            "learning_rate": 8.0e-4,
            "hard_velocity_boundary_transform": True,
            "reference_sha256": _sha256(reference),
        },
    )
    _write_json(
        output / "runtime_environment.json",
        {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": str(device),
            "cuda_available": torch.cuda.is_available(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "gpu": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda"
                else None
            ),
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
        y=evaluation["y"],
        prediction_velocity=evaluation["prediction_velocity"],
        reference_velocity=evaluation["reference_velocity"],
        prediction_p=evaluation["prediction_p"],
        reference_p=evaluation["reference_p"],
        continuity=evaluation["continuity"],
        momentum=evaluation["momentum"],
        prediction_pressure_gradient=evaluation["prediction_pressure_gradient"],
        reference_pressure_gradient=evaluation["reference_pressure_gradient"],
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
    parser.add_argument("--focus-x", type=float, default=0.5)
    parser.add_argument("--focus-y", type=float, default=0.5)
    parser.add_argument("--focus-fraction", type=float, default=0.125)
    parser.add_argument("--sigma", type=float, default=0.10)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
