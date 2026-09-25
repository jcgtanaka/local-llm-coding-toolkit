#!/usr/bin/env bash
# Report the hardware relevant to running local LLMs with Ollama on Linux:
# OS, CPU, RAM, and GPU (NVIDIA via nvidia-smi, AMD via rocm-smi if present).
# No external dependencies beyond common CLI tools. Degrades gracefully when
# a given vendor's tool is not installed.

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
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null \
    || echo "  not detected (nvidia-smi present but query failed)"
  found_gpu=true
fi
if command -v rocm-smi >/dev/null 2>&1; then
  echo "AMD:"
  rocm-smi --showproductname --showmeminfo vram 2>/dev/null \
    || echo "  not detected (rocm-smi present but query failed)"
  found_gpu=true
fi
if [ "$found_gpu" = false ]; then
  echo "No NVIDIA (nvidia-smi) or AMD (rocm-smi) tooling detected on PATH."
  echo "If you have a GPU, install the matching vendor tools to get VRAM info."
fi
echo

echo "== Rule of thumb =="
echo "A Q4-quantized model needs roughly (parameters in billions x 0.6) GB of"
echo "VRAM/unified memory to run fully on-GPU. If you have less, Ollama will"
echo "offload part of the model to CPU and generation speed will drop sharply."
