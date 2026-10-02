#!/usr/bin/env bash
# Report the hardware relevant to running local LLMs with Ollama on Linux:
# OS, CPU, RAM, and GPU (NVIDIA via nvidia-smi, AMD via rocm-smi, and any
# other VGA/3D controller via lspci). Read-only, no external dependencies
# beyond common CLI tools. Degrades gracefully when a tool is not installed.

set -u

echo "== OS =="
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "${PRETTY_NAME:-unknown Linux distribution}"
else
  uname -a
fi
echo

echo "== CPU =="
if command -v lscpu >/dev/null 2>&1; then
  model=$(lscpu | awk -F: '/Model name/ {print $2; exit}' | sed 's/^ *//')
  [ -n "${model:-}" ] && echo "Model: $model"
fi
if command -v nproc >/dev/null 2>&1; then
  echo "Logical cores: $(nproc)"
else
  echo "Logical cores: not detected"
fi
echo

echo "== RAM =="
if command -v free >/dev/null 2>&1; then
  free -h | awk '/^Mem:/ {print "Total RAM: " $2}'
else
  echo "Total RAM: not detected (no 'free' command)"
fi
echo

echo "== GPU =="
found_gpu=false
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "NVIDIA:"
  if nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; then
    found_gpu=true
  else
    echo "  not detected (nvidia-smi present but query failed)"
  fi
fi
if command -v rocm-smi >/dev/null 2>&1; then
  echo "AMD (rocm-smi):"
  if rocm-smi --showproductname --showmeminfo vram 2>/dev/null; then
    found_gpu=true
  else
    echo "  not detected (rocm-smi present but query failed)"
  fi
fi
if command -v lspci >/dev/null 2>&1; then
  pci=$(lspci 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' || true)
  if [ -n "$pci" ]; then
    echo "Display adapters (lspci; VRAM size not reported here):"
    echo "  ${pci//$'\n'/$'\n'  }"
    # Any adapter that is not a pure NVIDIA/AMD result still counts as detected.
    found_gpu=true
  fi
fi
if [ "$found_gpu" = false ]; then
  echo "No discrete GPU detected: expect CPU inference (slower, uses system RAM)."
  echo "If you do have a GPU, install the vendor tools (nvidia-smi or rocm-smi) for VRAM info."
fi
echo

echo "== Memory note =="
echo "Model size, quantization AND context length (KV cache) all consume"
echo "VRAM/RAM. If they do not fit on the GPU, Ollama offloads part of the"
echo "work to CPU and generation speed can drop sharply. Run the benchmark"
echo "(benchmark/benchmark_model.py) to find the real ceiling for your machine."
