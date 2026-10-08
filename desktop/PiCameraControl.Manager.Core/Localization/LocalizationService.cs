using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;

namespace PiCameraControl.Manager.Core.Localization;

public sealed record LanguageOption(string Code, string NativeName);

public sealed class LocalizationService : INotifyPropertyChanged
{
    public const string Chinese = "zh-CN";
    public const string English = "en-US";
    public const string German = "de-DE";

    private static readonly IReadOnlyList<LanguageOption> LanguageOptions =
    [
        new(Chinese, "简体中文"),
        new(English, "English"),
        new(German, "Deutsch"),
    ];

    public static LocalizationService Instance { get; } = new();

    private readonly ILanguagePreferenceStore _store;
    private string _currentLanguage;

    public LocalizationService(
        ILanguagePreferenceStore? store = null,
        CultureInfo? systemCulture = null)
    {
        _store = store ?? new JsonLanguagePreferenceStore();
        _currentLanguage = NormalizeLanguage(_store.Load() ?? (systemCulture ?? CultureInfo.CurrentUICulture).Name);
        ApplyCulture(_currentLanguage);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public IReadOnlyList<LanguageOption> SupportedLanguages => LanguageOptions;

    public string CurrentLanguage => _currentLanguage;

    public string this[string key] => LocalizationCatalog.Get(_currentLanguage, key);

    public string Format(string key, params object?[] arguments) =>
        string.Format(CultureInfo.GetCultureInfo(_currentLanguage), this[key], arguments);

    public void SetLanguage(string languageCode, bool persist = true)
    {
        var normalized = NormalizeLanguage(languageCode);
        if (normalized == _currentLanguage)
        {
            if (persist)
                _store.Save(normalized);
            return;
        }

        _currentLanguage = normalized;
        ApplyCulture(normalized);
        OnPropertyChanged(nameof(CurrentLanguage));
        OnPropertyChanged("Item[]");
        if (persist)
            _store.Save(normalized);
    }

    public static string NormalizeLanguage(string? languageCode)
    {
        if (string.IsNullOrWhiteSpace(languageCode))
            return English;
        if (languageCode.StartsWith("zh", StringComparison.OrdinalIgnoreCase))
            return Chinese;
        if (languageCode.StartsWith("de", StringComparison.OrdinalIgnoreCase))
            return German;
        if (languageCode.StartsWith("en", StringComparison.OrdinalIgnoreCase))
            return English;
        return English;
    }

    public static IReadOnlyCollection<string> TranslationKeys => LocalizationCatalog.Keys;

    private static void ApplyCulture(string languageCode)
    {
        var culture = CultureInfo.GetCultureInfo(languageCode);
        CultureInfo.CurrentUICulture = culture;
        CultureInfo.DefaultThreadCurrentUICulture = culture;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
}
