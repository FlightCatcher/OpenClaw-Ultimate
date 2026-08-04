[CmdletBinding()]
param(
    [string]$BaseUrl = "http://homeassistant.local:8123",
    [string]$VelaRoot = "E:\Projects\OpenClaw-Ultimate"
)

$ErrorActionPreference = "Stop"

function Set-EnvValue {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Value
    )

    $lines = if (Test-Path -LiteralPath $Path) {
        [Collections.Generic.List[string]](Get-Content -LiteralPath $Path)
    } else {
        [Collections.Generic.List[string]]::new()
    }

    $prefix = "$Name="
    $index = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($prefix, [StringComparison]::Ordinal)) {
            $index = $i
            break
        }
    }

    $entry = "$Name=$Value"
    if ($index -ge 0) {
        $lines[$index] = $entry
    } else {
        $lines.Add($entry)
    }
    Set-Content -LiteralPath $Path -Value $lines -Encoding utf8
}

$resolvedVelaRoot = (Resolve-Path -LiteralPath $VelaRoot).Path
if ($resolvedVelaRoot -ne "E:\Projects\OpenClaw-Ultimate") {
    throw "Unexpected VELA project path: $resolvedVelaRoot"
}

$secureToken = Read-Host "Paste the Home Assistant Long-Lived Access Token" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
}
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "The Home Assistant token cannot be empty."
}

$normalizedUrl = $BaseUrl.TrimEnd("/")
$headers = @{ Authorization = "Bearer $token" }
try {
    $response = Invoke-RestMethod `
        -Uri "$normalizedUrl/api/" `
        -Headers $headers `
        -TimeoutSec 15
} catch {
    throw "Home Assistant rejected the connection or token: $($_.Exception.Message)"
}
if ($response.message -ne "API running.") {
    throw "Unexpected Home Assistant API response."
}

$envPath = Join-Path $resolvedVelaRoot ".env"
Set-EnvValue -Path $envPath -Name "OCU_HOME_ASSISTANT_ENABLED" -Value "true"
Set-EnvValue -Path $envPath -Name "OCU_HOME_ASSISTANT_BASE_URL" -Value $normalizedUrl
Set-EnvValue -Path $envPath -Name "OCU_HOME_ASSISTANT_TOKEN" -Value $token
Set-EnvValue -Path $envPath -Name "OCU_HOME_ASSISTANT_TIMEOUT" -Value "10"
Set-EnvValue -Path $envPath -Name "OCU_HOME_ASSISTANT_READ_ONLY" -Value "true"
Set-EnvValue `
    -Path $envPath `
    -Name "OCU_HOME_ASSISTANT_ALLOWED_DOMAINS" `
    -Value '["light","switch","fan","climate","cover","vacuum","media_player","scene","script"]'

Write-Host ""
Write-Host "Home Assistant is connected to VELA in read-only mode." -ForegroundColor Green
Write-Host "Restart VELA, then ask it to run home_status or list smart-home devices."
Write-Host "Device control stays disabled until the discovered entity list is reviewed."
Write-Host ""
