param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$sourceRoot = Join-Path $resolvedRoot "integrations\vela-desktop"
$appRoot = Join-Path $env:USERPROFILE ".openclaw\apps\openclaw-desktop"
$distRoot = Join-Path $appRoot "dist"
$executable = Join-Path $distRoot "VELA-Desktop.exe"
$iconPath = Join-Path $appRoot "build\vela-icon.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "VELA.lnk"

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "package.json") -PathType Leaf)) {
    throw "VELA desktop source is missing: $sourceRoot"
}

New-Item -ItemType Directory -Force -Path $appRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceRoot "package.json") -Destination $appRoot -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot "package-lock.json") -Destination $appRoot -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot "src") -Destination $appRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot "renderer") -Destination $appRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot "build") -Destination $appRoot -Recurse -Force

if (-not $SkipBuild) {
    Push-Location $appRoot
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) {
            throw "VELA desktop dependencies could not be installed."
        }

        & npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "VELA desktop build failed."
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "VELA desktop executable is missing: $executable"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $executable
$shortcut.WorkingDirectory = $distRoot
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "VELA local AI desktop"
$shortcut.Save()

$installedShortcut = $shell.CreateShortcut($shortcutPath)
if ($installedShortcut.TargetPath -ne $executable) {
    throw "VELA desktop shortcut verification failed."
}

Write-Host "[OK] Native VELA desktop installed: $executable"
Write-Host "[OK] Desktop shortcut created: $shortcutPath"
