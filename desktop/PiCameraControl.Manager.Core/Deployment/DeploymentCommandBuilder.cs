using PiCameraControl.Manager.Core.Configuration;

namespace PiCameraControl.Manager.Core.Deployment;

public static class PosixShell
{
    public static string Quote(string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        return "'" + value.Replace("'", "'\"'\"'", StringComparison.Ordinal) + "'";
    }
}

public static class DeploymentCommandBuilder
{
    public enum SudoAuthenticationMode
    {
        NonInteractive,
        StandardInput,
    }

    public static string BuildInstallerCommand(
        DeviceProfile profile,
        string uploadedPackageRoot,
        string installScript,
        bool configureTouchDisplay,
        bool configureTailscale,
        SudoAuthenticationMode sudoAuthentication = SudoAuthenticationMode.NonInteractive,
        string uiLanguage = "en")
    {
        ArgumentNullException.ThrowIfNull(profile);
        if (!uploadedPackageRoot.StartsWith("/", StringComparison.Ordinal) ||
            uploadedPackageRoot.IndexOfAny(['\r', '\n']) >= 0)
            throw new ArgumentException("The remote package root must be an absolute POSIX path.", nameof(uploadedPackageRoot));
        if (!ReleaseManifest.IsSafeRelativePath(installScript))
            throw new ArgumentException("The install script must be a safe package-relative path.", nameof(installScript));

        var uploadedInstallerPath = uploadedPackageRoot.TrimEnd('/') + "/" + installScript;

        var arguments = new List<string>
        {
            "bash",
            PosixShell.Quote(uploadedInstallerPath),
            "--source", PosixShell.Quote(uploadedPackageRoot),
            "--ui-language", PosixShell.Quote(PiCameraControl.Manager.Core.Localization.LocalizationService.NormalizeLanguage(uiLanguage).Split('-')[0]),
            "--port", profile.WebPort.ToString(System.Globalization.CultureInfo.InvariantCulture),
            configureTouchDisplay ? "--enable-kiosk" : "--disable-kiosk",
            "--tailscale", configureTailscale ? "install" : "skip",
            "--sudo-auth", sudoAuthentication switch
            {
                SudoAuthenticationMode.NonInteractive => "noninteractive",
                SudoAuthenticationMode.StandardInput => "stdin",
                _ => throw new ArgumentOutOfRangeException(nameof(sudoAuthentication)),
            },
        };
        return string.Join(' ', arguments);
    }
}
