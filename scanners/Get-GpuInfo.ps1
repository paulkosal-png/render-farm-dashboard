<#
.SYNOPSIS
  Read-only GPU inventory for a render node.

.DESCRIPTION
  By default this runs nvidia-smi on the local machine and writes one object
  per GPU (Model, DriverVersion, VramMB, TemperatureC).

  With -TestRoot the script does not call nvidia-smi. It reads
  <TestRoot>/gpu.json instead, which is a list of the same objects. Use this
  to develop and test the scanner without a GPU.

  The script never changes drivers, clocks, or processes.
#>
[CmdletBinding()]
param(
    [string]$TestRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-GpuRows {
    param([object[]]$Rows)
    $index = 0
    foreach ($row in $Rows) {
        [pscustomobject]@{
            GpuIndex       = $index
            Model          = [string]$row.Model
            DriverVersion  = [string]$row.DriverVersion
            VramMB         = [int]$row.VramMB
            TemperatureC   = if ($null -ne $row.TemperatureC) { [int]$row.TemperatureC } else { $null }
            Status         = if ($row.Status) { [string]$row.Status } else { 'OK' }
        }
        $index++
    }
}

if ($TestRoot) {
    $source = Join-Path $TestRoot 'gpu.json'
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Test fixture not found: $source"
    }
    $rows = Get-Content -LiteralPath $source -Raw | ConvertFrom-Json
    Write-GpuRows -Rows @($rows)
    return
}

$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $smi) {
    [pscustomobject]@{
        GpuIndex = 0; Model = ''; DriverVersion = ''; VramMB = 0
        TemperatureC = $null; Status = 'nvidia-smi was not found on PATH'
    }
    return
}

$query = & $smi.Source --query-gpu=name,driver_version,memory.total,temperature.gpu --format=csv,noheader,nounits
if ($LASTEXITCODE -ne 0) {
    throw "nvidia-smi exited with code $LASTEXITCODE"
}

$parsed = foreach ($line in $query) {
    if (-not $line.Trim()) { continue }
    $parts = $line.Split(',').ForEach({ $_.Trim() })
    [pscustomobject]@{
        Model         = $parts[0]
        DriverVersion = $parts[1]
        VramMB        = [int]$parts[2]
        TemperatureC  = if ($parts.Count -gt 3 -and $parts[3] -match '^\d+$') { [int]$parts[3] } else { $null }
        Status        = 'OK'
    }
}
Write-GpuRows -Rows @($parsed)
