#!/usr/bin/env bash
# monitor_screen.sh — logs CPU/GPU/RAM while a screening curl runs.
set -u

LOG=/tmp/screen_monitor.log
INTERVAL=1
BACKEND=/home/sinjan/Documents/project/backend

rm -f "$LOG"
echo "ts,ram_used_gb,ram_total_gb,cpu_idle_pct,gpu_util_pct,gpu_mem_mb,gpu_mem_total_mb,gpu_temp_c,top_cpu,top_gpu" > "$LOG"

sample() {
  while true; do
    TS=$(date +%H:%M:%S)

    read -r ram_used ram_total < <(free -g | awk '/^Mem:/{print $3, $2}')

    cpu_idle=$(top -bn1 | awk '/^%Cpu/{print $8}' | tr -d ' ')
    [ -z "$cpu_idle" ] && cpu_idle="?"

    if command -v nvidia-smi >/dev/null 2>&1; then
      IFS=',' read -r gpu_util gpu_mem gpu_mem_tot gpu_temp < <(
        nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu \
          --format=csv,noheader,nounits | tr -d ' '
      )
    else
      gpu_util="?"; gpu_mem="?"; gpu_mem_tot="?"; gpu_temp="?"
    fi

    top_cpu=$(ps -eo pcpu,comm --sort=-pcpu | awk 'NR==2{printf "%s(%s%%)",$2,$1}')

    top_gpu=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory \
      --format=csv,noheader 2>/dev/null | head -1 | tr ',' ' ' | tr -s ' ')

    echo "$TS,${ram_used},${ram_total},${cpu_idle},${gpu_util},${gpu_mem},${gpu_mem_tot},${gpu_temp},${top_cpu},${top_gpu}" >> "$LOG"
    sleep "$INTERVAL"
  done
}

sample &
SAMPLER_PID=$!
trap "kill $SAMPLER_PID 2>/dev/null" EXIT

echo "[monitor] logging → $LOG"
echo "[monitor] hitting backend ..."

curl -sS -X POST http://localhost:8000/api/v2/screen \
  -F "document=@${BACKEND}/test_data/document.jpg" \
  -F "live_photo=@${BACKEND}/test_data/face.jpg" \
  -w "\n[monitor] curl total: %{time_total}s\n" \
  -o /tmp/screen_result.json

kill $SAMPLER_PID 2>/dev/null
wait $SAMPLER_PID 2>/dev/null

echo
echo "===== last 40 samples ====="
tail -40 "$LOG"
