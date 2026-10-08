using System.Text.Json;
using System.Text.Json.Serialization;

namespace PiCameraControl.Manager.Core.Deployment;

public sealed record ReleaseFile(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("sha256")] string Sha256,
    [property: JsonPropertyName("size")] long Size);

public sealed record ReleaseManifest(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("packageVersion")] string PackageVersion,
    [property: JsonPropertyName("installScript")] string InstallScript,
    [property: JsonPropertyName("files")] IReadOnlyList<ReleaseFile> Files)
{
    public static async Task<ReleaseManifest> LoadAsync(
        string manifestPath,
        CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(
            manifestPath, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, FileOptions.Asynchronous);
        var manifest = await JsonSerializer.DeserializeAsync<ReleaseManifest>(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false) ?? throw new InvalidDataException("The release manifest is empty.");
        manifest.Validate();
        return manifest;
    }

    public void Validate()
    {
        if (SchemaVersion != 1)
            throw new InvalidDataException($"Unsupported release manifest schema {SchemaVersion}.");
        if (string.IsNullOrWhiteSpace(PackageVersion))
            throw new InvalidDataException("Package version is required.");
        if (!IsSafeRelativePath(InstallScript))
            throw new InvalidDataException("Install script must be a safe relative package path.");
        if (Files is null || Files.Count == 0)
            throw new InvalidDataException("The release manifest does not contain files.");
        if (Files.Select(file => file.Path).Distinct(StringComparer.OrdinalIgnoreCase).Count() != Files.Count)
            throw new InvalidDataException("The release manifest contains duplicate file paths.");

        foreach (var file in Files)
        {
            if (!IsSafeRelativePath(file.Path))
                throw new InvalidDataException($"Unsafe release path: {file.Path}");
            if (file.Size < 0)
                throw new InvalidDataException($"Negative file size: {file.Path}");
            if (file.Sha256.Length != 64 || !file.Sha256.All(Uri.IsHexDigit))
                throw new InvalidDataException($"Invalid SHA-256 value: {file.Path}");
        }

        if (!Files.Any(file => file.Path.Equals(InstallScript, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException("The install script is not listed in the release files.");
    }

    public static bool IsSafeRelativePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || Path.IsPathRooted(path) || path.Contains('\\'))
            return false;
        return path.Split('/').All(part => part.Length > 0 && part is not "." and not "..");
    }
}
