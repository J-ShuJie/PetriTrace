[CmdletBinding()]
param([ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._+-]*$')][string]$Version='1.0.0')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'publish_windows_manager.ps1') -Version $Version -Runtime win-x64
$PublishDir=Join-Path $Root "artifacts/windows-manager/PetriTrace-$Version-win-x64"
$Candidates=@("${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe", "$env:ProgramFiles/Inno Setup 6/ISCC.exe", "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe")
$Compiler=$Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Compiler) { throw 'Install Inno Setup 6 before building Setup.' }
& $Compiler "/DPublishDir=$PublishDir" "/DReleaseVersion=$Version" (Join-Path $Root 'deploy/windows-setup.iss')
if ($LASTEXITCODE -ne 0) { throw 'Setup compilation failed.' }
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Root "artifacts/setup/PetriTrace-$Version-Setup.exe")
