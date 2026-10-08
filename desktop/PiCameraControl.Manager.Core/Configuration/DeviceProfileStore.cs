using System.Text.Json;

namespace PiCameraControl.Manager.Core.Configuration;

public interface IDeviceProfileStore
{
    Task<IReadOnlyList<DeviceProfile>> LoadAsync(CancellationToken cancellationToken = default);
    Task SaveAsync(IEnumerable<DeviceProfile> profiles, CancellationToken cancellationToken = default);
}

public sealed class JsonDeviceProfileStore : IDeviceProfileStore
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
    };

    private readonly string _path;

    public JsonDeviceProfileStore(string? path = null)
    {
        _path = path ?? GetDefaultPath();
    }

    public string Path => _path;

    public static string GetDefaultPath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return System.IO.Path.Combine(localAppData, "PiCameraControl", "devices.json");
    }

    public async Task<IReadOnlyList<DeviceProfile>> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_path))
            return Array.Empty<DeviceProfile>();

        await using var stream = new FileStream(
            _path, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, FileOptions.Asynchronous);
        var profiles = await JsonSerializer.DeserializeAsync<List<DeviceProfile>>(
            stream, JsonOptions, cancellationToken).ConfigureAwait(false);
        return profiles is null ? Array.Empty<DeviceProfile>() : profiles;
    }

    public async Task SaveAsync(IEnumerable<DeviceProfile> profiles, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(profiles);
        var snapshot = profiles.ToArray();
        var errors = snapshot.SelectMany(profile => profile.Validate()).ToArray();
        if (errors.Length > 0)
            throw new InvalidDataException(string.Join(Environment.NewLine, errors));
        if (snapshot.Select(profile => profile.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != snapshot.Length)
            throw new InvalidDataException("Device ids must be unique.");

        var directory = System.IO.Path.GetDirectoryName(_path);
        if (!string.IsNullOrEmpty(directory))
            Directory.CreateDirectory(directory);

        var temporaryPath = _path + ".tmp";
        try
        {
            await using (var stream = new FileStream(
                temporaryPath, FileMode.Create, FileAccess.Write, FileShare.None, 4096,
                FileOptions.Asynchronous | FileOptions.WriteThrough))
            {
                await JsonSerializer.SerializeAsync(stream, snapshot, JsonOptions, cancellationToken)
                    .ConfigureAwait(false);
                await stream.FlushAsync(cancellationToken).ConfigureAwait(false);
            }

            File.Move(temporaryPath, _path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
                File.Delete(temporaryPath);
        }
    }
}
