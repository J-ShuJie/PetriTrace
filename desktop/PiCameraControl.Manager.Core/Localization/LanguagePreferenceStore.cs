using System.Text.Json;

namespace PiCameraControl.Manager.Core.Localization;

public interface ILanguagePreferenceStore
{
    string? Load();
    void Save(string languageCode);
}

public sealed class JsonLanguagePreferenceStore : ILanguagePreferenceStore
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
    };

    private readonly string _path;

    public JsonLanguagePreferenceStore(string? path = null)
    {
        _path = path ?? GetDefaultPath();
    }

    public string Path => _path;

    public static string GetDefaultPath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return System.IO.Path.Combine(localAppData, "PiCameraControl", "manager-settings.json");
    }

    public string? Load()
    {
        if (!File.Exists(_path))
            return null;

        try
        {
            var document = JsonSerializer.Deserialize<LanguagePreference>(File.ReadAllText(_path), JsonOptions);
            return document?.Language;
        }
        catch (JsonException)
        {
            return null;
        }
        catch (IOException)
        {
            return null;
        }
        catch (UnauthorizedAccessException)
        {
            return null;
        }
    }

    public void Save(string languageCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(languageCode);
        var directory = System.IO.Path.GetDirectoryName(_path);
        if (!string.IsNullOrEmpty(directory))
            Directory.CreateDirectory(directory);

        var temporaryPath = _path + ".tmp";
        try
        {
            File.WriteAllText(temporaryPath,
                JsonSerializer.Serialize(new LanguagePreference(languageCode), JsonOptions));
            File.Move(temporaryPath, _path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
                File.Delete(temporaryPath);
        }
    }

    private sealed record LanguagePreference(string Language);
}
