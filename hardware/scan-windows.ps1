# Report the hardware relevant to running local LLMs with Ollama on Windows:
# OS, CPU, RAM, and GPU (name via Win32_VideoController, VRAM via nvidia-smi.exe
# when available since AdapterRAM is often unreliable on modern cards).
# Degrades gracefully when a given source is not available.

Write-Host "== OS =="
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    Write-Host "$($os.Caption) ($($os.Version))"
} catch {
    Write-Host "not detected"
}
Write-Host ""

Write-Host "== CPU =="
try {
    $cpu = Get-CimInstance Win32_Processor -ErrorAction Stop
    Write-Host "Model: $($cpu.Name)"
    Write-Host "Logical cores: $($cpu.NumberOfLogicalProcessors)"
} catch {
    Write-Host "not detected"
}
Write-Host ""

Write-Host "== RAM =="
try {
    $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $totalGb = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    Write-Host "Total RAM: $totalGb GB"
} catch {
    Write-Host "not detected"
}
Write-Host ""

Write-Host "== GPU =="
try {
    $gpus = Get-CimInstance Win32_VideoController -ErrorAction Stop
    foreach ($gpu in $gpus) {
        Write-Host "Name: $($gpu.Name)"
    }
} catch {
    Write-Host "not detected (Win32_VideoController query failed)"
}

$nvidiaSmi = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    Write-Host "NVIDIA VRAM (via nvidia-smi.exe, more reliable than AdapterRAM):"
    try {
        & nvidia-smi.exe --query-gpu=name,memory.total --format=csv,noheader
    } catch {
        Write-Host "  not detected (nvidia-smi.exe present but query failed)"
    }
} else {
    Write-Host "nvidia-smi.exe not found on PATH: VRAM size not detected."
    Write-Host "(Win32_VideoController's AdapterRAM field is often wrong on modern GPUs,"
    Write-Host " so it is not used here as a VRAM source.)"
}
Write-Host ""

Write-Host "== Rule of thumb =="
Write-Host "A Q4-quantized model needs roughly (parameters in billions x 0.6) GB of"
Write-Host "VRAM/unified memory to run fully on-GPU. If you have less, Ollama will"
Write-Host "offload part of the model to CPU and generation speed will drop sharply."
