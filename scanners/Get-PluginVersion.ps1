<#
.SYNOPSIS
  Read-only DCC plugin version scanner.

.DESCRIPTION
  Looks for plugin version files under an install tree:

    <InstallRoot>/<AppName>/<AppVersion>/plugins/<PluginName>/version.txt

  The default install root is the "apps" folder next to this script. Pass
  -TestRoot to point at a fixture tree instead. The script only reads
  version.txt files; it never copies, deletes, or writes plugins.

  Each version.txt file should contain a single version string on the first
  line, for example: 3.9.0
#>
[CmdletBinding()]
param(
    [string]$InstallRoot,
    [string]$TestRoot,
    [string]$PluginName = 'LightTrace'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = if ($TestRoot) { $TestRoot } elseif ($InstallRoot) { $InstallRoot } else { Join-Path $PSScriptRoot 'apps' }

if (-not (Test-Path -LiteralPath $root)) {
    [pscustomobject]@{
        AppName = ''; AppVersion = ''; PluginName = $PluginName
        PluginVersion = ''; PluginPath = $root; Status = "Install root not found: $root"
    }
    return
}

$found = $false
Get-ChildItem -LiteralPath $root -Directory -ErrorAction Stop | ForEach-Object {
    $appName = $_.Name
    Get-ChildItem -LiteralPath $_.FullName -Directory | ForEach-Object {
        $appVersion = $_.Name
        $versionFile = Join-Path $_.FullName "plugins/$PluginName/version.txt"
        if (Test-Path -LiteralPath $versionFile) {
            $found = $true
            $version = (Get-Content -LiteralPath $versionFile -TotalCount 1).Trim()
            [pscustomobject]@{
                AppName        = $appName
                AppVersion     = $appVersion
                PluginName     = $PluginName
                PluginVersion  = $version
                PluginPath     = $versionFile
                Status         = 'OK'
            }
        }
    }
}

if (-not $found) {
    [pscustomobject]@{
        AppName = ''; AppVersion = ''; PluginName = $PluginName
        PluginVersion = ''; PluginPath = $root
        Status = "No $PluginName version.txt files under $root"
    }
}
