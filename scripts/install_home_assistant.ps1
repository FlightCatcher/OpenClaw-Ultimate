[CmdletBinding()]
param(
    [string]$VmName = "Home Assistant",
    [string]$VmRoot = "E:\HomeAssistant\vm",
    [string]$VhdxPath = "E:\HomeAssistant\vm\haos_ova-18.2.vhdx",
    [string]$SwitchName = "HomeAssistant-External",
    [int]$MemoryMb = 2048,
    [int]$CpuCount = 2
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[Home Assistant] $Message" -ForegroundColor Cyan
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Write-Step "Requesting administrator access..."
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $arguments
    exit 0
}

$computer = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
if (-not $processor.VirtualizationFirmwareEnabled) {
    Write-Host ""
    Write-Host "CPU virtualization is disabled in BIOS/UEFI." -ForegroundColor Yellow
    Write-Host "Enable SVM Mode / AMD-V in BIOS, save, and boot Windows again."
    Write-Host "Then run this installer again. No Home Assistant data will be lost."
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 2
}

if (-not (Test-Path -LiteralPath $VhdxPath)) {
    throw "Home Assistant disk not found: $VhdxPath"
}

$resolvedRoot = (Resolve-Path -LiteralPath $VmRoot).Path
$resolvedDisk = (Resolve-Path -LiteralPath $VhdxPath).Path
if (-not $resolvedRoot.StartsWith("E:\HomeAssistant", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use an unexpected VM root: $resolvedRoot"
}
if (-not $resolvedDisk.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Virtual disk must remain under $resolvedRoot"
}

$hyperV = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
if ($hyperV.State -ne "Enabled") {
    Write-Step "Enabling the Windows Hyper-V feature..."
    $featureResult = Enable-WindowsOptionalFeature `
        -Online `
        -FeatureName Microsoft-Hyper-V-All `
        -All `
        -NoRestart
    if ($featureResult.RestartNeeded) {
        Write-Host ""
        Write-Host "Hyper-V is enabled, but Windows must restart once." -ForegroundColor Yellow
        Write-Host "Restart Windows, then run this installer again."
        Write-Host ""
        Read-Host "Press Enter to close"
        exit 3
    }
}

Import-Module Hyper-V

$vm = Get-VM -Name $VmName -ErrorAction SilentlyContinue
if (-not $vm) {
    $switch = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue
    if (-not $switch) {
        $adapter = Get-NetAdapter -Physical |
            Where-Object Status -eq "Up" |
            Sort-Object LinkSpeed -Descending |
            Select-Object -First 1
        if (-not $adapter) {
            throw "No active physical network adapter is available for Home Assistant."
        }

        Write-Step "Creating a bridged virtual switch on $($adapter.Name)."
        Write-Host "The network may disconnect briefly while Windows creates the bridge."
        $switch = New-VMSwitch `
            -Name $SwitchName `
            -NetAdapterName $adapter.Name `
            -AllowManagementOS $true
    }

    Write-Step "Creating the Home Assistant OS virtual machine on E:."
    $vm = New-VM `
        -Name $VmName `
        -Generation 2 `
        -MemoryStartupBytes ($MemoryMb * 1MB) `
        -VHDPath $resolvedDisk `
        -SwitchName $switch.Name `
        -Path $resolvedRoot
}

Set-VMProcessor -VMName $VmName -Count $CpuCount
Set-VMMemory `
    -VMName $VmName `
    -DynamicMemoryEnabled $true `
    -MinimumBytes 1GB `
    -StartupBytes ($MemoryMb * 1MB) `
    -MaximumBytes 3GB
Set-VMFirmware -VMName $VmName -EnableSecureBoot Off
Set-VM `
    -Name $VmName `
    -AutomaticStartAction Start `
    -AutomaticStartDelay 30 `
    -AutomaticStopAction Save

if ((Get-VM -Name $VmName).State -ne "Running") {
    Write-Step "Starting Home Assistant OS..."
    Start-VM -Name $VmName | Out-Null
}

$state = [ordered]@{
    vm_name = $VmName
    vm_root = $resolvedRoot
    disk = $resolvedDisk
    memory_mb = $MemoryMb
    cpu_count = $CpuCount
    installed_at = (Get-Date).ToString("o")
    onboarding_url = "http://homeassistant.local:8123"
}
$state | ConvertTo-Json | Set-Content `
    -LiteralPath "E:\HomeAssistant\install-state.json" `
    -Encoding utf8

Write-Host ""
Write-Host "Home Assistant OS is running." -ForegroundColor Green
Write-Host "Allow 5-20 minutes for the first boot, then open:"
Write-Host "http://homeassistant.local:8123" -ForegroundColor Cyan
Write-Host ""
Write-Host "After onboarding and creating a Long-Lived Access Token, run:"
Write-Host "E:\HomeAssistant\Connect-Vela.ps1" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
