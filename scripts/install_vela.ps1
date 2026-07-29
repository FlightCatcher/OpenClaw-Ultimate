param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$launcher = Join-Path $resolvedRoot "scripts\start_vela.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "VELA AI.lnk"
$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powershell
$shortcut.Arguments = (
    "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden " +
    "-File `"$launcher`" -ProjectRoot `"$resolvedRoot`" -Port $Port"
)
$shortcut.WorkingDirectory = $resolvedRoot
$shortcut.Description = "VELA local AI agent command deck"
$shortcut.IconLocation = "$powershell,0"
$shortcut.Save()

Write-Host "[OK] Desktop shortcut created: $shortcutPath"
Write-Host "[OK] VELA remains local: http://127.0.0.1:$Port/"
