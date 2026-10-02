# Report the hardware relevant to running local LLMs with Ollama on Windows:
# OS, CPU, RAM, and GPU (NVIDIA via nvidia-smi.exe when available, other
# adapters via Win32_VideoController). Read-only, no external dependencies.
# Run with: powershell -ExecutionPolicy Bypass -File hardware/scan-windows.ps1

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
    # Multi-socket machines return an array: join names, sum logical cores.
    $cpus = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
    $names = ($cpus | ForEach-Object { $_.Name.Trim() }) -join " + "
    $logical = ($cpus | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
    Write-Host "Model: $names"
    Write-Host "Logical cores: $logical"
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
$nvidiaSmi = $null
$cmd = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
if ($cmd) {
    $nvidiaSmi = $cmd.Source
} else {
    $candidate = Join-Path $env:ProgramFiles "NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if (Test-Path $candidate) { $nvidiaSmi = $candidate }
}
if ($nvidiaSmi) {
    Write-Host "NVIDIA (via nvidia-smi, accurate VRAM):"
    try {
        $out = & $nvidiaSmi --query-gpu=name,memory.total --format=csv,noheader 2>&1
        if ($LASTEXITCODE -eq 0) {
            $out | ForEach-Object { Write-Host "  $_" }
        } else {
            Write-Host "  not detected (nvidia-smi exited with code $LASTEXITCODE)"
        }
    } catch {
        Write-Host "  not detected (nvidia-smi present but query failed)"
    }
} else {
    Write-Host "nvidia-smi not found on PATH or in Program Files: NVIDIA VRAM size not detected."
}

Write-Host "All display adapters (Win32_VideoController):"
try {
    $adapters = @(Get-CimInstance Win32_VideoController -ErrorAction Stop)
    if ($adapters.Count -eq 0) {
        Write-Host "  none reported: expect CPU inference."
    }
    foreach ($a in $adapters) {
        if ($a.AdapterRAM) {
            $gb = [math]::Round($a.AdapterRAM / 1GB, 1)
            Write-Host "  $($a.Name) (AdapterRAM: $gb GB)"
        } else {
            Write-Host "  $($a.Name) (AdapterRAM: not reported)"
        }
    }
    Write-Host "  Caveat: AdapterRAM is a 32-bit field and can under-report VRAM above 4 GB."
} catch {
    Write-Host "  not detected (Win32_VideoController query failed)"
}
Write-Host ""

Write-Host "== Memory note =="
Write-Host "Model size, quantization AND context length (KV cache) all consume"
Write-Host "VRAM/RAM. If they do not fit on the GPU, Ollama offloads part of the"
Write-Host "work to CPU and generation speed can drop sharply. Run the benchmark"
Write-Host "(benchmark/benchmark_model.py) to find the real ceiling for your machine."
