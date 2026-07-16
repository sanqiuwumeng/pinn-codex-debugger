#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: setup_remote_training_env.sh <env-root> <status-file> <success-marker>" >&2
    exit 2
fi

env_root="$1"
status_file="$2"
success_marker="$3"

mkdir -p "$(dirname "$status_file")"
trap 'rc=$?; printf "%s\n" "$rc" > "$status_file"; exit "$rc"' EXIT

if [[ -e "$env_root" ]]; then
    echo "environment target already exists: $env_root" >&2
    exit 3
fi

source /root/miniconda3/etc/profile.d/conda.sh
conda create --prefix "$env_root" --yes python=3.11.11 pip
"$env_root/bin/python" -m pip install \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.3.1
"$env_root/bin/python" -m pip install numpy==2.2.5
"$env_root/bin/python" - <<'PY'
import json
import sys

import numpy
import torch

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is unavailable in the isolated training environment")
x = torch.linspace(0.0, 1.0, 128, device="cuda", requires_grad=True)
loss = torch.sin(x).square().sum()
first = torch.autograd.grad(loss, x, create_graph=True)[0]
second = torch.autograd.grad(first.sum(), x)[0]
torch.cuda.synchronize()
if not bool(torch.isfinite(second).all()):
    raise RuntimeError("CUDA second-order autograd probe produced non-finite values")

print(
    json.dumps(
        {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "numpy": numpy.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device_capability": (
                torch.cuda.get_device_capability() if torch.cuda.is_available() else None
            ),
            "cuda_second_order_autograd": True,
        },
        sort_keys=True,
    )
)
PY
touch "$success_marker"
