param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
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
    "-File `"$launcher`" -ProjectRoot `"$resolvedRoot`""
)
$shortcut.WorkingDirectory = $resolvedRoot
$shortcut.Description = "VELA local AI agent powered by OpenClaw"
$openClawIcon = Join-Path ((& npm root -g).Trim()) "openclaw\dist\control-ui\favicon.ico"

if (Test-Path -LiteralPath $openClawIcon -PathType Leaf) {
    $shortcut.IconLocation = "$openClawIcon,0"
}

$shortcut.Save()

Write-Host "[OK] Desktop shortcut created: $shortcutPath"
Write-Host "[OK] VELA uses the original OpenClaw Dashboard and icon."
