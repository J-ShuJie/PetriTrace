namespace PiCameraControl.Manager.Core.Configuration;

public enum PreferredConnection
{
    Automatic,
    LocalNetwork,
    Tailscale,
}

public enum SshAuthenticationMode
{
    PrivateKey,
    Password,
}

public sealed record DeviceProfile
{
    public const int CurrentSchemaVersion = 1;

    public int SchemaVersion { get; init; } = CurrentSchemaVersion;
    public required string Id { get; init; }
    public required string DisplayName { get; init; }
    public required string HostName { get; init; }
    public required string SshUserName { get; init; }
    public int SshPort { get; init; } = 22;
    public SshAuthenticationMode AuthenticationMode { get; init; } = SshAuthenticationMode.PrivateKey;
    public string? PrivateKeyPath { get; init; }
    public int WebPort { get; init; } = 5000;
    public bool UseHttps { get; init; }
    public string? LocalAddress { get; init; }
    public string? TailscaleAddress { get; init; }
    public PreferredConnection PreferredConnection { get; init; } = PreferredConnection.Automatic;
    public bool TouchDisplayEnabled { get; init; } = true;
    public string? TrustedSshHostKeyAlgorithm { get; init; }
    public string? TrustedSshHostKeySha256 { get; init; }
    public DateTimeOffset? LastConnectedAt { get; init; }
    public string? LastSuccessfulBaseUrl { get; init; }

    public IEnumerable<string> Validate()
    {
        if (SchemaVersion != CurrentSchemaVersion)
            yield return $"Unsupported device profile schema {SchemaVersion}.";
        if (string.IsNullOrWhiteSpace(Id))
            yield return "Device id is required.";
        else if (Id.Length > 64 || Id.Any(character =>
                     !char.IsAsciiLetterOrDigit(character) && character is not '-' and not '_'))
            yield return "Device id contains unsupported characters.";
        if (string.IsNullOrWhiteSpace(DisplayName))
            yield return "Display name is required.";
        if (!HostAddress.IsSafeHost(HostName))
            yield return "Host name contains unsupported characters.";
        if (!HostAddress.IsSafeSshUser(SshUserName))
            yield return "SSH user name contains unsupported characters.";
        if (SshPort is < 1 or > 65535)
            yield return "SSH port must be between 1 and 65535.";
        if (WebPort is < 1 or > 65535)
            yield return "Web port must be between 1 and 65535.";
        if (AuthenticationMode == SshAuthenticationMode.PrivateKey &&
            string.IsNullOrWhiteSpace(PrivateKeyPath))
            yield return "A private key path is required for private-key authentication.";
        if (!string.IsNullOrWhiteSpace(LocalAddress) && !HostAddress.IsSafeHost(LocalAddress))
            yield return "Local address contains unsupported characters.";
        if (!string.IsNullOrWhiteSpace(TailscaleAddress) && !HostAddress.IsSafeHost(TailscaleAddress))
            yield return "Tailscale address contains unsupported characters.";
        if (string.IsNullOrWhiteSpace(TrustedSshHostKeyAlgorithm) !=
            string.IsNullOrWhiteSpace(TrustedSshHostKeySha256))
            yield return "SSH host-key algorithm and SHA-256 fingerprint must be stored together.";
        else if (!string.IsNullOrWhiteSpace(TrustedSshHostKeyAlgorithm) &&
                 !HostKeyTrustPolicy.IsSafeAlgorithm(TrustedSshHostKeyAlgorithm))
            yield return "SSH host-key algorithm contains unsupported characters.";
        else if (!string.IsNullOrWhiteSpace(TrustedSshHostKeySha256) &&
                 !HostKeyTrustPolicy.TryNormalizeSha256(TrustedSshHostKeySha256, out _))
            yield return "SSH host-key SHA-256 fingerprint is invalid.";
    }
}

internal static class HostAddress
{
    public static bool IsSafeHost(string? value)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > 253)
            return false;

        if (Uri.CheckHostName(value) != UriHostNameType.Unknown)
            return true;

        return Uri.TryCreate($"http://[{value}]", UriKind.Absolute, out var uri) &&
               uri.HostNameType == UriHostNameType.IPv6;
    }

    public static bool IsSafeSshUser(string? value)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > 64)
            return false;

        return value.All(character =>
            char.IsAsciiLetterOrDigit(character) || character is '_' or '-' or '.');
    }
}
