#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s <qualification-root>\n' "$0" >&2
  exit 2
fi

root=$1
python_bin=${PYTHON_BIN:-"$root/env/bin/python"}
download_script="$root/stage/download_qwen3_snapshots.py"
cache_root="$root/hf_home/hub"
run_logs="$root/run_logs"
manifests="$root/model_manifests"

mkdir -p "$run_logs" "$manifests"

run_id="qwen3_model_download_$(date -u +%Y%m%dT%H%M%SZ)"
log_path="$run_logs/$run_id.log"
pid_path="$run_logs/$run_id.pid"
started_path="$run_logs/$run_id.started.json"
status_path="$run_logs/$run_id.status.json"
manifest_path="$manifests/$run_id.json"

for path in "$log_path" "$pid_path" "$started_path" "$status_path" "$manifest_path"; do
  if [[ -e "$path" ]]; then
    printf 'refusing to overwrite %s\n' "$path" >&2
    exit 1
  fi
done

printf '{"run_id":"%s","started_at_utc":"%s"}\n' \
  "$run_id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$started_path"

nohup env \
  HF_HOME="$root/hf_home" \
  HF_HUB_CACHE="$cache_root" \
  HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}" \
  HF_XET_HIGH_PERFORMANCE=1 \
  /bin/bash -c '
    set +e
    "$1" "$2" \
      --cache-root "$3" \
      --manifest-path "$4" \
      --max-workers 4
    rc=$?
    printf "{\"exit_code\":%d,\"completed_at_utc\":\"%s\"}\n" \
      "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$5"
    exit "$rc"
  ' _ "$python_bin" "$download_script" "$cache_root" "$manifest_path" "$status_path" \
  >"$log_path" 2>&1 </dev/null &

job_pid=$!
printf '%s\n' "$job_pid" >"$pid_path"
printf '{"run_id":"%s","pid":%d,"log":"%s","status":"%s","manifest":"%s"}\n' \
  "$run_id" "$job_pid" "$log_path" "$status_path" "$manifest_path"
