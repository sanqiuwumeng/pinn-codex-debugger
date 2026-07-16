# Retrieval Model Sandbox Manifest

- Created: 2026-07-16
- Environment: `pinn_strategy_retrieval_models`
- Interpreter: `C:\Users\Mli\.conda\envs\pinn_strategy_retrieval_models\python.exe`
- Python: 3.11.11, conda-forge CPython build `h3f84c4b_2_cpython`
- Platform: Windows x86-64
- Conda: 24.11.3
- Validation: `python -m pip check` returned `No broken requirements found.`

## Current state

The environment contains Python and conda bootstrap packages only. No PyTorch,
Transformers, Sentence Transformers, Accelerate, bitsandbytes, Qwen model
runtime, model object or model weight is installed.

`pip freeze` currently contains only the conda-provided `packaging` package.
The environment is therefore an isolation boundary, not a functioning model
runtime.

## Isolation checks

- `pinn_strategy_orchestrator` was not modified.
- `pytorch2.3.1` was not modified.
- No Qwen cache directory was created by this work.
- No model download or inference process was started.

## Measured host resources

- GPU: NVIDIA GeForce RTX 5070
- Compute capability: 12.0
- Driver: 596.49
- GPU memory: 12,227 MiB
- Physical memory: 31.81 GiB
- Free disk: C: 316.61 GiB; E: 414.83 GiB

The existing `pytorch2.3.1` interpreter reports PyTorch 2.3.1 with no CUDA
runtime and `torch.cuda.is_available() == False`; it is intentionally not reused
for Qwen inference.
