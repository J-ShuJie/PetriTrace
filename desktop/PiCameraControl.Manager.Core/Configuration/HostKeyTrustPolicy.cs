namespace PiCameraControl.Manager.Core.Configuration;

public enum HostKeyTrustStatus
{
    FirstSeen,
    Trusted,
    Mismatch,
}

public readonly record struct HostKeyTrustEvaluation(HostKeyTrustStatus Status)
{
    public bool CanTrust => Status == HostKeyTrustStatus.Trusted;
    public bool RequiresConfirmation => Status == HostKeyTrustStatus.FirstSeen;
}

public static class HostKeyTrustPolicy
{
    public static HostKeyTrustEvaluation Evaluate(
        DeviceProfile profile,
        string presentedAlgorithm,
        string presentedSha256)
    {
        ArgumentNullException.ThrowIfNull(profile);
        return Evaluate(
            profile.TrustedSshHostKeyAlgorithm,
            profile.TrustedSshHostKeySha256,
            presentedAlgorithm,
            presentedSha256);
    }

    public static HostKeyTrustEvaluation Evaluate(
        string? trustedAlgorithm,
        string? trustedSha256,
        string presentedAlgorithm,
        string presentedSha256)
    {
        if (!IsSafeAlgorithm(presentedAlgorithm) ||
            !TryNormalizeSha256(presentedSha256, out var normalizedPresented))
            return new HostKeyTrustEvaluation(HostKeyTrustStatus.Mismatch);

        var hasAlgorithm = !string.IsNullOrWhiteSpace(trustedAlgorithm);
        var hasFingerprint = !string.IsNullOrWhiteSpace(trustedSha256);
        if (!hasAlgorithm && !hasFingerprint)
            return new HostKeyTrustEvaluation(HostKeyTrustStatus.FirstSeen);
        if (!hasAlgorithm || !hasFingerprint || !IsSafeAlgorithm(trustedAlgorithm!) ||
            !TryNormalizeSha256(trustedSha256, out var normalizedTrusted))
            return new HostKeyTrustEvaluation(HostKeyTrustStatus.Mismatch);

        return new HostKeyTrustEvaluation(
            string.Equals(trustedAlgorithm, presentedAlgorithm, StringComparison.Ordinal) &&
            string.Equals(normalizedTrusted, normalizedPresented, StringComparison.Ordinal)
                ? HostKeyTrustStatus.Trusted
                : HostKeyTrustStatus.Mismatch);
    }

    public static bool IsSafeAlgorithm(string? value) =>
        !string.IsNullOrWhiteSpace(value) && value.Length <= 128 &&
        value.All(character =>
            char.IsAsciiLetterOrDigit(character) || character is '-' or '_' or '.' or '@');

    public static bool TryNormalizeSha256(string? value, out string normalized)
    {
        normalized = string.Empty;
        if (string.IsNullOrWhiteSpace(value) || value.StartsWith("SHA256:", StringComparison.Ordinal) ||
            value.Any(char.IsWhiteSpace) || value.Length is not (43 or 44) ||
            (value.Length == 44 && (value[^1] != '=' || value[^2] == '=')))
            return false;

        var padded = value.Length == 43 ? value + "=" : value;
        byte[] decoded;
        try
        {
            decoded = Convert.FromBase64String(padded);
        }
        catch (FormatException)
        {
            return false;
        }

        if (decoded.Length != 32)
            return false;
        var canonicalPadded = Convert.ToBase64String(decoded);
        if (!string.Equals(padded, canonicalPadded, StringComparison.Ordinal))
            return false;
        normalized = canonicalPadded.TrimEnd('=');
        return true;
    }
}
