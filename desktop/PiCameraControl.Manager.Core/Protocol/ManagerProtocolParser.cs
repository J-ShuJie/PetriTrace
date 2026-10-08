namespace PiCameraControl.Manager.Core.Protocol;

public enum ManagerProtocolAction
{
    Open,
    Diagnose,
    Update,
    Repair,
}

public sealed record ManagerProtocolRequest(ManagerProtocolAction Action, string? DeviceId)
{
    public bool RequiresConfirmation => Action is ManagerProtocolAction.Update or ManagerProtocolAction.Repair;
}

public static class ManagerProtocolParser
{
    public const string Scheme = "picameracontrol";

    public static bool TryParse(string? value, out ManagerProtocolRequest? request)
    {
        request = null;
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
            !uri.Scheme.Equals(Scheme, StringComparison.OrdinalIgnoreCase) ||
            !uri.Host.Equals("manage", StringComparison.OrdinalIgnoreCase) ||
            !string.IsNullOrEmpty(uri.UserInfo) ||
            uri.Port != -1 ||
            (uri.AbsolutePath != "/" && uri.AbsolutePath.Length != 0) ||
            !string.IsNullOrEmpty(uri.Fragment))
            return false;

        var values = ParseQuery(uri.Query);
        if (values.Keys.Any(key =>
                !key.Equals("action", StringComparison.OrdinalIgnoreCase) &&
                !key.Equals("device", StringComparison.OrdinalIgnoreCase)))
            return false;

        var actionText = values.GetValueOrDefault("action", "open");
        if (!Enum.TryParse<ManagerProtocolAction>(actionText, ignoreCase: true, out var action))
            return false;

        var deviceId = values.GetValueOrDefault("device");
        if (!string.IsNullOrEmpty(deviceId) && !IsSafeDeviceId(deviceId))
            return false;

        request = new ManagerProtocolRequest(action, deviceId);
        return true;
    }

    private static Dictionary<string, string> ParseQuery(string query)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var parts = item.Split('=', 2);
            var key = Uri.UnescapeDataString(parts[0]);
            var value = parts.Length == 2 ? Uri.UnescapeDataString(parts[1]) : string.Empty;
            if (!result.TryAdd(key, value))
                return new Dictionary<string, string> { ["__duplicate"] = string.Empty };
        }

        return result;
    }

    private static bool IsSafeDeviceId(string value) =>
        value.Length <= 64 && value.All(character =>
            char.IsAsciiLetterOrDigit(character) || character is '-' or '_');
}
