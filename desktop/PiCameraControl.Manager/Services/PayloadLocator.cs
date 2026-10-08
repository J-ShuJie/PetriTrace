using System.IO;

namespace PiCameraControl.Manager.Services;

internal static class PayloadLocator
{
    public static string FindPayload()
    {
        var packaged = Path.Combine(AppContext.BaseDirectory, "payload");
        if (HasBuiltManifest(packaged))
            return packaged;

        throw new DirectoryNotFoundException(
            "找不到已构建的树莓派发布包。请使用 scripts/publish_windows_manager.ps1 生成完整发行目录。");
    }

    public static string FindSourceRoot()
    {
        var packaged = Path.Combine(AppContext.BaseDirectory, "payload");
        if (Directory.Exists(packaged))
            return packaged;

        foreach (var start in new[] { Environment.CurrentDirectory, AppContext.BaseDirectory })
        {
            var directory = new DirectoryInfo(start);
            for (var depth = 0; directory is not null && depth < 8; depth++, directory = directory.Parent)
            {
                if (File.Exists(Path.Combine(directory.FullName, "deploy", "release-manifest.json")) &&
                    File.Exists(Path.Combine(directory.FullName, "app.py")))
                    return directory.FullName;
            }
        }

        throw new DirectoryNotFoundException(
            "找不到树莓派发布包。请使用 scripts/publish_windows_manager.ps1 生成完整发行目录。");
    }

    private static bool HasBuiltManifest(string root)
    {
        var path = Path.Combine(root, "release-manifest.json");
        if (!File.Exists(path))
            return false;
        return new FileInfo(path).Length > 128;
    }
}
