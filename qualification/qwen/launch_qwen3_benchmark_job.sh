#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s <qualification-root>\n' "$0" >&2
  exit 2
fi

root=$1
python_bin=${PYTHON_BIN:-"$root/env/bin/python"}
benchmark_script="$root/stage/run_qwen3_retrieval_benchmark.py"
cases_path="$root/stage/qwen3_retrieval_benchmark_cases_v1.json"
cache_root="$root/hf_home/hub"
embedding_revision=1d8ad4ca9b3dd8059ad90a75d4983776a23d44af
reranker_revision=22e683669bc0f0bd69640a1354a6d0aebcfeede5
embedding_snapshot="$cache_root/models--Qwen--Qwen3-Embedding-8B/snapshots/$embedding_revision"
reranker_snapshot="$cache_root/models--Qwen--Qwen3-Reranker-4B/snapshots/$reranker_revision"
run_logs="$root/run_logs"
results_root="$root/results"

for path in "$python_bin" "$benchmark_script" "$cases_path"; do
  if [[ ! -f "$path" ]]; then
    printf 'required file is missing: %s\n' "$path" >&2
    exit 1
  fi
done
for path in "$embedding_snapshot" "$reranker_snapshot"; do
  if [[ ! -d "$path" ]]; then
    printf 'required model snapshot is missing: %s\n' "$path" >&2
    exit 1
  fi
done

mkdir -p "$run_logs" "$results_root"

run_id="qwen3_retrieval_benchmark_$(date -u +%Y%m%dT%H%M%SZ)"
result_dir="$results_root/$run_id"
log_path="$run_logs/$run_id.log"
pid_path="$run_logs/$run_id.pid"
started_path="$run_logs/$run_id.started.json"
status_path="$run_logs/$run_id.status.json"

for path in "$result_dir" "$log_path" "$pid_path" "$started_path" "$status_path"; do
  if [[ -e "$path" ]]; then
    printf 'refusing to overwrite %s\n' "$path" >&2
    exit 1
  fi
done

printf '{"run_id":"%s","started_at_utc":"%s"}\n' \
  "$run_id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$started_path"

nohup env \
  CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
  CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  HF_HOME="$root/hf_home" \
  HF_HUB_CACHE="$cache_root" \
  HF_HUB_OFFLINE=1 \
  TRANSFORMERS_OFFLINE=1 \
  TOKENIZERS_PARALLELISM=false \
  PYTHONHASHSEED=0 \
  /bin/bash -c '
    set +e
    "$1" "$2" \
      --cases "$3" \
      --result-dir "$4" \
      --embedding-snapshot "$5" \
      --embedding-revision "$6" \
      --reranker-snapshot "$7" \
      --reranker-revision "$8" \
      --max-length 2048 \
      --embedding-batch-size 4 \
      --reranker-batch-size 4 \
      --rerank-candidates 6 \
      --all-evidence-rerank-candidates 10
    rc=$?
    printf "{\"exit_code\":%d,\"completed_at_utc\":\"%s\"}\n" \
      "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$9"
    exit "$rc"
  ' _ \
  "$python_bin" "$benchmark_script" "$cases_path" "$result_dir" \
  "$embedding_snapshot" "$embedding_revision" \
  "$reranker_snapshot" "$reranker_revision" "$status_path" \
  >"$log_path" 2>&1 </dev/null &

job_pid=$!
printf '%s\n' "$job_pid" >"$pid_path"
printf '{"run_id":"%s","pid":%d,"log":"%s","status":"%s","result_dir":"%s"}\n' \
  "$run_id" "$job_pid" "$log_path" "$status_path" "$result_dir"
