using Microsoft.Win32;

namespace PiCameraControl.Manager.Services;

internal static class ManagerProtocolRegistration
{
    public static void EnsureRegistered()
    {
        if (!OperatingSystem.IsWindows())
            return;
        var executable = Environment.ProcessPath;
        if (string.IsNullOrWhiteSpace(executable))
            return;

        using var root = Registry.CurrentUser.CreateSubKey(@"Software\Classes\picameracontrol");
        root.SetValue(null, "URL:PetriTrace Manager");
        root.SetValue("URL Protocol", string.Empty);
        using var icon = root.CreateSubKey("DefaultIcon");
        icon.SetValue(null, $"\"{executable}\",0");
        using var command = root.CreateSubKey(@"shell\open\command");
        command.SetValue(null, $"\"{executable}\" \"%1\"");
    }
}
