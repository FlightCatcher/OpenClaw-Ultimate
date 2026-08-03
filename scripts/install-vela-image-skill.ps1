[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$skillSource = Join-Path $projectRoot "integrations\openclaw-skills\image-studio-4k"
$userProfilePath = [Environment]::GetFolderPath("UserProfile")
$skillTarget = Join-Path $userProfilePath ".openclaw\workspace\skills\image-studio-4k"

if (-not (Test-Path -LiteralPath (Join-Path $skillSource "SKILL.md"))) {
    throw "VELA image skill source is missing: $skillSource"
}

if (Test-Path -LiteralPath $skillTarget) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupTarget = "$skillTarget.backup-$stamp"
    Copy-Item -LiteralPath $skillTarget -Destination $backupTarget -Recurse
    Write-Host "Backed up the current skill to $backupTarget"
}

New-Item -ItemType Directory -Force -Path $skillTarget | Out-Null
Copy-Item -Path (Join-Path $skillSource "*") -Destination $skillTarget -Recurse -Force
Write-Host "Installed VELA image skill at $skillTarget"
