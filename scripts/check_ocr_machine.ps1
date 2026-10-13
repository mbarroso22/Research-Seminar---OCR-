[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [string]$OutputDir = "",
    [string]$CompareWith = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$baselinePython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $baselinePython -PathType Leaf)) { throw "Existing baseline Python missing: $baselinePython" }
if (-not $OutputDir) {
    $stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
    $OutputDir = Join-Path $DataRoot "audits\machine-check-$stamp-$suffix"
}
if (Test-Path -LiteralPath $OutputDir) { throw "Choose a new inventory output directory." }
$null = New-Item -ItemType Directory -Path $OutputDir
$utf8 = New-Object System.Text.UTF8Encoding($false)
$pythonJson = & $baselinePython -c 'import json,sys,platform,struct; print(json.dumps(dict(executable=sys.executable,version=sys.version,machine=platform.machine(),bits=struct.calcsize(chr(80))*8)))'
if ($LASTEXITCODE -ne 0) { throw "Baseline Python probe failed." }
$baselineFreeze = @(& $baselinePython -m pip freeze --all)
if ($LASTEXITCODE -ne 0) { throw "Baseline package inventory failed." }
$freezePath = Join-Path $OutputDir "baseline-packages.txt"
[IO.File]::WriteAllText($freezePath, ($baselineFreeze -join "`n") + "`n", $utf8)
$freezeSha = (Get-FileHash -LiteralPath $freezePath -Algorithm SHA256).Hash.ToLowerInvariant()
$operatingSystem = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors)
$video = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM)
$disks = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    [ordered]@{ drive = $_.DeviceID; size_bytes = [long]$_.Size; free_bytes = [long]$_.FreeSpace }
})
$nvidiaCommand = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
$nvidia = [ordered]@{ available = $false; query_exit_code = $null; gpu_csv = @(); full_output = @(); error = $null }
if ($nvidiaCommand) {
    $nvidia.available = $true
    try {
        $nvidia.gpu_csv = @(& $nvidiaCommand.Source --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader 2>&1 | ForEach-Object { "$_" })
        $nvidia.query_exit_code = $LASTEXITCODE
        $nvidia.full_output = @(& $nvidiaCommand.Source 2>&1 | ForEach-Object { "$_" })
    } catch { $nvidia.error = "$_"; $nvidia.query_exit_code = $LASTEXITCODE }
}
$launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
$pythonInstallations = @()
if ($launcher) {
    try { $pythonInstallations = @(& $launcher.Source -0p 2>&1 | ForEach-Object { "$_" }) }
    catch { $pythonInstallations = @("Python launcher inventory failed: $_") }
}
$inventory = [ordered]@{
    schema_version = 1; stage = "setup_inventory"; timestamp_utc = [DateTime]::UtcNow.ToString("o")
    os = $operatingSystem.Caption; os_version = $operatingSystem.Version; cpu = $cpu
    ram_total_bytes = [long]$computer.TotalPhysicalMemory
    ram_available_bytes = [long]$operatingSystem.FreePhysicalMemory * 1024
    disks = $disks; data_root = $DataRoot; video_controllers = $video; nvidia_smi = $nvidia
    vram_note = "Use successful nvidia-smi dedicated memory values; Win32 AdapterRAM can truncate large capacities. Missing NVIDIA tools does not prove absence of a GPU."
    baseline_python = ($pythonJson | ConvertFrom-Json); python_installations = $pythonInstallations
    baseline_packages_sha256 = $freezeSha
    interpretation = "Current setup observations only; no OCR inference, retrieval, throughput or energy result"
}
if ($CompareWith) {
    $previous = Get-Content -LiteralPath $CompareWith -Raw | ConvertFrom-Json
    $inventory.baseline_environment_unchanged = ($previous.baseline_packages_sha256 -eq $freezeSha -and
        $previous.baseline_python.executable -eq $inventory.baseline_python.executable -and
        $previous.baseline_python.version -eq $inventory.baseline_python.version)
}
$path = Join-Path $OutputDir "machine_inventory.json"
[IO.File]::WriteAllText($path, ($inventory | ConvertTo-Json -Depth 10) + "`n", $utf8)
$inventory | ConvertTo-Json -Depth 10
Write-Host "Inventory: $path"
if ($CompareWith -and -not $inventory.baseline_environment_unchanged) { throw "Baseline environment changed; inspect inventories before continuing." }
