namespace PiCameraControl.Manager.Core.Connectivity;

public static class ManagerUrlBuilder
{
    public const string EntryParameter = "entry";
    public const string EntryValue = "windows-manager";

    public static Uri Build(Uri baseUri)
    {
        ArgumentNullException.ThrowIfNull(baseUri);
        if (!baseUri.IsAbsoluteUri ||
            (baseUri.Scheme != Uri.UriSchemeHttp && baseUri.Scheme != Uri.UriSchemeHttps))
            throw new ArgumentException("The control-panel URL must use HTTP or HTTPS.", nameof(baseUri));

        var builder = new UriBuilder(baseUri);
        var pairs = ParseQuery(builder.Query)
            .Where(pair => !pair.Key.Equals(EntryParameter, StringComparison.OrdinalIgnoreCase))
            .Append(new KeyValuePair<string, string>(EntryParameter, EntryValue));
        builder.Query = string.Join("&", pairs.Select(pair =>
            $"{Uri.EscapeDataString(pair.Key)}={Uri.EscapeDataString(pair.Value)}"));
        builder.Fragment = string.Empty;
        return builder.Uri;
    }

    private static IEnumerable<KeyValuePair<string, string>> ParseQuery(string query)
    {
        foreach (var item in query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var parts = item.Split('=', 2);
            yield return new KeyValuePair<string, string>(
                Uri.UnescapeDataString(parts[0]),
                parts.Length == 2 ? Uri.UnescapeDataString(parts[1]) : string.Empty);
        }
    }
}
