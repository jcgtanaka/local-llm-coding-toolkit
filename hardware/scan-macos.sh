#!/usr/bin/env bash
# Report the hardware relevant to running local LLMs with Ollama on macOS:
# OS, CPU, RAM, and GPU/chip info. Read-only, no external dependencies beyond
# common CLI tools. Degrades gracefully when a given tool is not available.
#
# Apple Silicon (arm64) uses unified memory: there is no separate VRAM pool.
# Intel Macs have separate GPU memory (if a discrete GPU exists) and do not
# use unified memory.

set -u

echo "== OS =="
sw_vers 2>/dev/null || echo "not detected"
echo

arch=$(uname -m 2>/dev/null || echo unknown)
echo "Architecture: $arch"
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
  system_profiler SPDisplaysDataType 2>/dev/null | grep -E "Chipset Model|Chip:|VRAM|Metal" \
    || echo "not detected (system_profiler returned no display/chip info)"
else
  echo "not detected (no system_profiler)"
fi
if [ "$arch" = "arm64" ]; then
  echo "Apple Silicon uses unified memory: the CPU and GPU share one pool of RAM."
  echo "macOS limits how much of that pool the GPU can address to a fraction of"
  echo "total RAM, so the usable amount for a model is less than the total above."
else
  echo "This is not an Apple Silicon Mac: unified memory does not apply."
  echo "GPU memory (VRAM) is listed above if a discrete or integrated GPU reports it."
fi
echo

echo "== Memory note =="
echo "Model size, quantization AND context length (KV cache) all consume"
echo "memory. If they do not fit where the GPU can reach, Ollama offloads part"
echo "of the work to CPU and generation speed can drop sharply. Run the"
echo "benchmark (benchmark/benchmark_model.py) to find the real ceiling for"
echo "your machine."
