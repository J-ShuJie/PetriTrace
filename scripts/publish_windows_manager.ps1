[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._+-]*$')]
    [string]$Version = '1.0.0',

    [Parameter()]
    [ValidateSet('win-x64', 'win-arm64')]
    [string]$Runtime = 'win-x64'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$ArtifactsRoot = Join-Path $Root 'artifacts'
$ReleaseRoot = Join-Path $ArtifactsRoot 'releases'
$WindowsRoot = Join-Path $ArtifactsRoot 'windows-manager'
$PublishDirectory = Join-Path $WindowsRoot "PetriTrace-$Version-$Runtime"
$Project = Join-Path $Root 'desktop\PiCameraControl.Manager\PiCameraControl.Manager.csproj'

New-Item -ItemType Directory -Force -Path $ReleaseRoot, $WindowsRoot | Out-Null

$package = & (Join-Path $PSScriptRoot 'build_release.ps1') -Version $Version -OutputDirectory $ReleaseRoot
if (-not $package -or -not (Test-Path -LiteralPath $package.Archive)) {
    throw 'The Raspberry Pi payload was not produced.'
}

if (Test-Path -LiteralPath $PublishDirectory) {
    $resolved = [IO.Path]::GetFullPath($PublishDirectory)
    $allowed = [IO.Path]::GetFullPath($WindowsRoot)
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to replace a publish directory outside artifacts/windows-manager.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

$dotnetHome = Join-Path $Root '.dotnet-home'
$nugetPackages = Join-Path $Root '.nuget-packages'
$buildTemp = Join-Path $Root '.build-temp'
New-Item -ItemType Directory -Force -Path $dotnetHome, $nugetPackages, $buildTemp | Out-Null
$env:DOTNET_CLI_HOME = $dotnetHome
$env:NUGET_PACKAGES = $nugetPackages
$env:TEMP = $buildTemp
$env:TMP = $buildTemp
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'

& dotnet publish $Project -c Release -r $Runtime --self-contained true `
    -p:PublishSingleFile=true `
    "-p:Version=$Version" `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:DebugType=None `
    -p:DebugSymbols=false `
    -o $PublishDirectory
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE"
}

$PayloadDirectory = Join-Path $PublishDirectory 'payload'
New-Item -ItemType Directory -Path $PayloadDirectory | Out-Null
& tar -xzf $package.Archive -C $PayloadDirectory
if ($LASTEXITCODE -ne 0) {
    throw "payload extraction failed with exit code $LASTEXITCODE"
}

Copy-Item -LiteralPath (Join-Path $Root 'LICENSE') -Destination $PublishDirectory
Copy-Item -LiteralPath (Join-Path $Root 'THIRD_PARTY_NOTICES.md') -Destination $PublishDirectory
Copy-Item -LiteralPath (Join-Path $Root 'licenses') -Destination $PublishDirectory -Recurse
$noticePath = Join-Path $PublishDirectory 'THIRD_PARTY_NOTICES.md'
$noticeText = [IO.File]::ReadAllText($noticePath).Replace('(tools/', '(payload/tools/').Replace('(static/', '(payload/static/')
[IO.File]::WriteAllText($noticePath, $noticeText, [Text.UTF8Encoding]::new($false))

$releaseInfo = [ordered]@{
    product = 'PetriTrace'
    version = $Version
    runtime = $Runtime
    builtAtUtc = [DateTime]::UtcNow.ToString('o')
    payloadArchiveSha256 = $package.Sha256
    entryExecutable = 'PetriTrace.exe'
    payloadDirectory = 'payload'
}
[IO.File]::WriteAllText(
    (Join-Path $PublishDirectory 'release-info.json'),
    (($releaseInfo | ConvertTo-Json) + [Environment]::NewLine),
    [Text.UTF8Encoding]::new($false)
)

$zipPath = Join-Path $WindowsRoot "PetriTrace-$Version-$Runtime.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $PublishDirectory '*') -DestinationPath $zipPath -CompressionLevel Optimal

[pscustomobject]@{
    Version = $Version
    Runtime = $Runtime
    Directory = $PublishDirectory
    Executable = Join-Path $PublishDirectory 'PetriTrace.exe'
    Archive = $zipPath
    Payload = $PayloadDirectory
}
