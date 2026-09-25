#!/usr/bin/env bash
# Report the hardware relevant to running local LLMs with Ollama on macOS:
# OS, CPU, RAM, and GPU/chip info. No external dependencies beyond common
# CLI tools. Degrades gracefully when a given tool is not available.
#
# Note on Apple Silicon: it uses unified memory, so there is no separate
# VRAM pool. Total system RAM is reported as the usable memory pool for
# on-GPU model execution.

set -u

echo "== OS =="
sw_vers 2>/dev/null || echo "not detected"
echo

echo "== CPU =="
if command -v sysctl >/dev/null 2>&1; then
  brand=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
  [ -n "${brand:-}" ] && echo "Model: $brand"
  cores=$(sysctl -n hw.ncpu 2>/dev/null)
  [ -n "${cores:-}" ] && echo "Logical cores: $cores"
else
  echo "not detected (no sysctl)"
fi
echo

echo "== RAM =="
if command -v sysctl >/dev/null 2>&1; then
  mem_bytes=$(sysctl -n hw.memsize 2>/dev/null)
  if [ -n "${mem_bytes:-}" ]; then
    awk -v b="$mem_bytes" 'BEGIN { printf "Total RAM: %.1f GB\n", b/1024/1024/1024 }'
  else
    echo "Total RAM: not detected"
  fi
else
  vm_stat 2>/dev/null || echo "Total RAM: not detected"
fi
echo

echo "== GPU / chip =="
if command -v system_profiler >/dev/null 2>&1; then
  system_profiler SPDisplaysDataType 2>/dev/null | grep -E "Chipset Model|Chip:" \
    || echo "not detected (system_profiler returned no display/chip info)"
else
  echo "not detected (no system_profiler)"
fi
echo "Apple Silicon uses unified memory: there is no discrete VRAM pool."
echo "The total system RAM reported above is the usable pool for on-GPU"
echo "model execution, shared with everything else running on the machine."
echo

echo "== Rule of thumb =="
echo "A Q4-quantized model needs roughly (parameters in billions x 0.6) GB of"
echo "VRAM/unified memory to run fully on-GPU. If you have less, Ollama will"
echo "offload part of the model to CPU and generation speed will drop sharply."
