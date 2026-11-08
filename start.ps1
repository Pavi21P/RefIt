param([string]$PythonPath = '', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not $PythonPath) {
        $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
        if (Test-Path -LiteralPath $localPython) { $PythonPath = $localPython }
        else { $PythonPath = 'python' }
    }
    & $PythonPath -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment. Pass -PythonPath with your Python executable.' }
    & $venvPython -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $venvPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
Write-Host "RefIt: http://127.0.0.1:$Port"
& $venvPython manage.py runserver "127.0.0.1:$Port"
