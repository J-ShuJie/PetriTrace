[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._+-]*$')]
    [string]$Version = '1.0.0',

    [Parameter()]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)
    $lines = & certutil.exe -hashfile $LiteralPath SHA256
    if ($LASTEXITCODE -ne 0 -or $lines.Count -lt 2) {
        throw "certutil failed to hash $LiteralPath"
    }
    return (($lines[1] -replace '\s', '').ToLowerInvariant())
}

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $Root 'artifacts\releases'
}

$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$ArtifactsRoot = [IO.Path]::GetFullPath((Join-Path $Root 'artifacts'))
if (-not $OutputDirectory.StartsWith($ArtifactsRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must stay inside $ArtifactsRoot"
}

$FileListPath = Join-Path $Root 'deploy\release-files.txt'
$ManifestTemplatePath = Join-Path $Root 'deploy\release-manifest.json'
$files = Get-Content -LiteralPath $FileListPath |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith('#') }

if (-not $files) {
    throw 'Release file list is empty.'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$BuildDirectory = Join-Path $OutputDirectory ".build-$Version"
if (Test-Path -LiteralPath $BuildDirectory) {
    $ResolvedBuild = [IO.Path]::GetFullPath($BuildDirectory)
    if (-not $ResolvedBuild.StartsWith($OutputDirectory, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to remove a build directory outside the output directory.'
    }
    Remove-Item -LiteralPath $ResolvedBuild -Recurse -Force
}
New-Item -ItemType Directory -Path $BuildDirectory | Out-Null

try {
    foreach ($relative in $files) {
        if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains('..')) {
            throw "Unsafe release path: $relative"
        }
        $source = Join-Path $Root ($relative -replace '/', '\')
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Release file does not exist: $relative"
        }
        $destination = Join-Path $BuildDirectory ($relative -replace '/', '\')
        $destinationParent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }

    $manifest = Get-Content -Raw -LiteralPath $ManifestTemplatePath | ConvertFrom-Json
    $manifest.packageVersion = $Version
    $manifest | Add-Member -NotePropertyName builtAtUtc -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
    $entries = foreach ($relative in $files) {
        $path = Join-Path $BuildDirectory ($relative -replace '/', '\')
        $item = Get-Item -LiteralPath $path
        [ordered]@{
            path = ($relative -replace '\\', '/')
            sha256 = Get-Sha256Hex -LiteralPath $path
            size = [int64]$item.Length
        }
    }
    $manifest.files = @($entries)
    $embeddedManifestPath = Join-Path $BuildDirectory 'release-manifest.json'
    [IO.File]::WriteAllText(
        $embeddedManifestPath,
        (($manifest | ConvertTo-Json -Depth 20) + [Environment]::NewLine),
        [Text.UTF8Encoding]::new($false)
    )

    $archiveName = "pi-camera-control-pi-$Version.tar.gz"
    $archivePath = Join-Path $OutputDirectory $archiveName
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    & tar -czf $archivePath -C $BuildDirectory .
    if ($LASTEXITCODE -ne 0) {
        throw "tar failed with exit code $LASTEXITCODE"
    }

    $archiveItem = Get-Item -LiteralPath $archivePath
    $archiveHash = Get-Sha256Hex -LiteralPath $archivePath
    $manifest | Add-Member -NotePropertyName package -NotePropertyValue ([ordered]@{
        fileName = $archiveName
        sha256 = $archiveHash
        size = [int64]$archiveItem.Length
        format = 'tar.gz'
    }) -Force
    $companionManifestPath = Join-Path $OutputDirectory "pi-camera-control-pi-$Version.manifest.json"
    [IO.File]::WriteAllText(
        $companionManifestPath,
        (($manifest | ConvertTo-Json -Depth 20) + [Environment]::NewLine),
        [Text.UTF8Encoding]::new($false)
    )

    [pscustomobject]@{
        Version = $Version
        Archive = $archiveItem.FullName
        Manifest = $companionManifestPath
        Sha256 = $archiveHash
        Size = $archiveItem.Length
        FileCount = $entries.Count
    }
}
finally {
    if (Test-Path -LiteralPath $BuildDirectory) {
        Remove-Item -LiteralPath $BuildDirectory -Recurse -Force
    }
}
