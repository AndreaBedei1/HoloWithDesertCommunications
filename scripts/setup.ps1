param([string]$HoloOceanClient = "", [string]$Python = "py", [string]$PythonVersion = "3.10")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (!(Test-Path -LiteralPath .venv\Scripts\python.exe)) {
    if ($Python -eq "py") { & py "-$PythonVersion" -m venv .venv } else { & $Python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw "Creating Python environment failed" }
}
& .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw "Installing dependencies failed" }
& .venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw "Installing project failed" }
if ($HoloOceanClient) {
    & .venv\Scripts\python.exe scripts/install_holoocean.py --client $HoloOceanClient
    if ($LASTEXITCODE -ne 0) { throw "Installing HoloOcean client failed" }
}
Write-Output "Ready. Run .venv\Scripts\holo-desert.exe doctor"
