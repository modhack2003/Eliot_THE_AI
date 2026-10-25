# Windows convenience installer; full security-tool provisioning targets Linux.
[CmdletBinding()]
param([string]$Prefix, [switch]$NoDesktop)
$ErrorActionPreference = 'Stop'

function Find-EliotPython {
    $candidates = @()
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $located = & $pyLauncher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $candidates += $located }
        } catch { }
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') { $candidates += $pythonCommand.Source }
    $candidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    foreach ($candidate in $candidates) {
        try {
            & $candidate -I -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { }
    }
    return $null
}

try {
    $eliotPython = Find-EliotPython
    if (-not $eliotPython) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Python 3.11+ and winget were not found. Install Python from python.org (include pip), then run this installer again.'
        }
        Write-Host 'Installing Python 3.13 for your user account...'
        & winget install --id Python.Python.3.13 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Check the winget message above.' }
        $eliotPython = Find-EliotPython
        if (-not $eliotPython) { throw 'Python was installed but could not be located. Reopen the installer.' }
    }
    $eliotArguments = @('-I', (Join-Path $PSScriptRoot 'scripts\install.py'))
    if ($Prefix) { $eliotArguments += @('--prefix', $Prefix) }
    if ($NoDesktop) { $eliotArguments += '--no-desktop' }
    & $eliotPython @eliotArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host 'For the complete nmap tool setup, run install.sh inside Kali/Linux. Windows supports chat and local evidence tools.'
} catch {
    Write-Error $_
    exit 1
}
