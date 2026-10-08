using System.Text.RegularExpressions;

namespace PiCameraControl.Manager.Core.Localization;

/// <summary>
/// Translates application-owned validation and deployment messages that cross
/// service boundaries as plain text. Unknown system, SSH, and remote-command
/// output is deliberately preserved so diagnostic detail is never discarded.
/// </summary>
public static partial class RuntimeMessageLocalizer
{
    private sealed record PatternFormatter(Regex Pattern, Func<string, Match, string> Format);

    private static readonly IReadOnlyDictionary<string, IReadOnlyDictionary<string, string>> Exact =
        new Dictionary<string, IReadOnlyDictionary<string, string>>(StringComparer.OrdinalIgnoreCase)
        {
            [LocalizationService.Chinese] = CreateChinese(),
            [LocalizationService.English] = CreateEnglish(),
            [LocalizationService.German] = CreateGerman(),
        };

    private static readonly PatternFormatter[] PatternFormatters =
    [
        new(Connecting(), (language, match) => language switch
        {
            LocalizationService.English => $"Connecting to {match.Groups[1].Value}…",
            LocalizationService.German => $"Verbindung mit {match.Groups[1].Value} wird hergestellt…",
            _ => match.Value,
        }),
        new(ConnectionSucceeded(), (language, match) => language switch
        {
            LocalizationService.English => $"SSH connection established; {match.Groups[1].Value} verified. The password is never written to disk or deployment logs.",
            LocalizationService.German => $"SSH-Verbindung hergestellt; {match.Groups[1].Value} geprüft. Das Passwort wird weder auf den Datenträger noch in Bereitstellungsprotokolle geschrieben.",
            _ => match.Value,
        }),
        new(UploadedFiles(), (language, match) => language switch
        {
            LocalizationService.English => $"Verified and uploaded {match.Groups[1].Value} release files. The temporary directory will be removed after installation.",
            LocalizationService.German => $"{match.Groups[1].Value} Veröffentlichungsdateien geprüft und hochgeladen. Das temporäre Verzeichnis wird nach der Installation entfernt.",
            _ => match.Value,
        }),
        new(ServiceStatus(), (language, match) => language switch
        {
            LocalizationService.English => $"Background-service status: {match.Groups[1].Value}",
            LocalizationService.German => $"Status der Hintergrunddienste: {match.Groups[1].Value}",
            _ => match.Value,
        }),
        new(ConnectionFailure(), (language, match) => language switch
        {
            LocalizationService.English => $"Could not establish the SSH connection ({match.Groups[1].Value}). Check the address, network, and authentication details.",
            LocalizationService.German => $"Die SSH-Verbindung konnte nicht hergestellt werden ({match.Groups[1].Value}). Adresse, Netzwerk und Anmeldedaten prüfen.",
            _ => match.Value,
        }),
        new(HostKeyMismatch(), (language, match) => language switch
        {
            LocalizationService.English => $"The Raspberry Pi SSH host key differs from the saved record. To prevent connection to the wrong device, the manager refused the connection.\nSaved: {match.Groups[1].Value}\nCurrent device: {match.Groups[2].Value}",
            LocalizationService.German => $"Der SSH-Hostschlüssel des Raspberry Pi weicht vom gespeicherten Eintrag ab. Um eine Verbindung mit dem falschen Gerät zu verhindern, wurde sie abgelehnt.\nGespeichert: {match.Groups[1].Value}\nAktuelles Gerät: {match.Groups[2].Value}",
            _ => match.Value,
        }),
    ];

    public static string Translate(LocalizationService localizer, string? message)
    {
        if (string.IsNullOrWhiteSpace(message))
            return string.Empty;

        var trimmed = message.Trim();
        if (Exact[localizer.CurrentLanguage].TryGetValue(trimmed, out var translated))
            return translated;

        foreach (var formatter in PatternFormatters)
        {
            var match = formatter.Pattern.Match(trimmed);
            if (match.Success)
                return formatter.Format(localizer.CurrentLanguage, match);
        }

        var pathMatch = PathMessage().Match(trimmed);
        if (pathMatch.Success)
            return FormatPathMessage(localizer.CurrentLanguage, pathMatch.Groups[1].Value, pathMatch.Groups[2].Value);

        var commandMatch = CommandFailure().Match(trimmed);
        if (commandMatch.Success)
            return FormatCommandFailure(localizer.CurrentLanguage, commandMatch.Groups[1].Value, commandMatch.Groups[2].Value);

        return trimmed;
    }

    private static IReadOnlyDictionary<string, string> CreateChinese() => new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["Device id is required."] = "设备 ID 不能为空。",
        ["Device id contains unsupported characters."] = "设备 ID 含有不支持的字符。",
        ["Display name is required."] = "设备显示名称不能为空。",
        ["Host name contains unsupported characters."] = "主机名含有不支持的字符。",
        ["SSH user name contains unsupported characters."] = "SSH 用户名含有不支持的字符。",
        ["SSH port must be between 1 and 65535."] = "SSH 端口必须介于 1 和 65535 之间。",
        ["Web port must be between 1 and 65535."] = "Web 端口必须介于 1 和 65535 之间。",
        ["A private key path is required for private-key authentication."] = "使用私钥认证时必须提供私钥路径。",
        ["Local address contains unsupported characters."] = "局域网地址含有不支持的字符。",
        ["Tailscale address contains unsupported characters."] = "Tailscale 地址含有不支持的字符。",
        ["无法建立 SSH 连接。请检查地址、网络和认证信息。"] = "无法建立 SSH 连接。请检查地址、网络和认证信息。",
        ["SSH 连接没有建立。请检查树莓派是否已启动并启用 SSH。"] = "SSH 连接没有建立。请检查树莓派是否已启动并启用 SSH。",
        ["发布包尚未上传。"] = "发布包尚未上传。",
        ["健康检查返回了响应，但没有报告 ok=true。"] = "健康检查返回了响应，但没有报告 ok=true。",
        ["缺少所选 SSH 认证方式需要的信息。"] = "缺少所选 SSH 认证方式需要的信息。",
        ["当前账户不能无交互使用 sudo。请在树莓派系统中授予该管理员账户 sudo 权限后重试。"] = "当前账户无法使用 sudo。请确认管理员密码或 sudo 权限后重试。",
        ["SSH 连接已经断开，请重新连接后再试。"] = "SSH 连接已经断开，请重新连接后再试。",
        ["正在读取树莓派 SSH 主机密钥…"] = "正在读取树莓派 SSH 主机密钥…",
        ["没有信任该树莓派的 SSH 主机密钥，连接已安全取消。"] = "没有信任该树莓派的 SSH 主机密钥，连接已安全取消。",
        ["树莓派返回了无效的 SSH SHA-256 主机密钥指纹。"] = "树莓派返回了无效的 SSH SHA-256 主机密钥指纹。",
        ["sudo 非交互检查通过。"] = "sudo 非交互检查通过。",
        ["sudo 密码验证通过；密码未进入命令行或日志。"] = "sudo 密码验证通过；密码未进入命令行或日志。",
        ["sudo 验证没有成功，请检查管理员密码。"] = "sudo 验证没有成功，请检查管理员密码。",
        ["正在安装 Python 环境、菌落计数后端和应用文件；这一步通常最久。"] = "正在安装 Python 环境、菌落计数后端和应用文件；这一步通常最久。",
        ["健康检查通过。核心服务已经在树莓派上独立运行。"] = "健康检查通过。核心服务已经在树莓派上独立运行。",
        ["SSH 主机密钥探测意外建立了连接，已中止以避免未确认的信任。"] = "SSH 主机密钥探测意外建立了连接，已中止以避免未确认的信任。",
    };

    private static IReadOnlyDictionary<string, string> CreateEnglish() => new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["Device id is required."] = "Device ID is required.",
        ["Device id contains unsupported characters."] = "The device ID contains unsupported characters.",
        ["Display name is required."] = "Display name is required.",
        ["Host name contains unsupported characters."] = "The host name contains unsupported characters.",
        ["SSH user name contains unsupported characters."] = "The SSH user name contains unsupported characters.",
        ["SSH port must be between 1 and 65535."] = "The SSH port must be between 1 and 65535.",
        ["Web port must be between 1 and 65535."] = "The web port must be between 1 and 65535.",
        ["A private key path is required for private-key authentication."] = "A private-key path is required for private-key authentication.",
        ["Local address contains unsupported characters."] = "The local address contains unsupported characters.",
        ["Tailscale address contains unsupported characters."] = "The Tailscale address contains unsupported characters.",
        ["无法建立 SSH 连接。请检查地址、网络和认证信息。"] = "Could not establish the SSH connection. Check the address, network, and authentication details.",
        ["SSH 连接没有建立。请检查树莓派是否已启动并启用 SSH。"] = "The SSH connection was not established. Check that the Raspberry Pi is running and SSH is enabled.",
        ["发布包尚未上传。"] = "The release package has not been uploaded.",
        ["健康检查返回了响应，但没有报告 ok=true。"] = "The health check responded but did not report ok=true.",
        ["缺少所选 SSH 认证方式需要的信息。"] = "Information required by the selected SSH authentication method is missing.",
        ["当前账户不能无交互使用 sudo。请在树莓派系统中授予该管理员账户 sudo 权限后重试。"] = "The current account cannot use sudo. Check the administrator password or sudo permissions and try again.",
        ["SSH 连接已经断开，请重新连接后再试。"] = "The SSH connection was lost. Reconnect and try again.",
        ["正在读取树莓派 SSH 主机密钥…"] = "Reading the Raspberry Pi SSH host key…",
        ["没有信任该树莓派的 SSH 主机密钥，连接已安全取消。"] = "The Raspberry Pi SSH host key was not trusted. The connection was cancelled safely.",
        ["树莓派返回了无效的 SSH SHA-256 主机密钥指纹。"] = "The Raspberry Pi returned an invalid SSH SHA-256 host-key fingerprint.",
        ["sudo 非交互检查通过。"] = "Non-interactive sudo check passed.",
        ["sudo 密码验证通过；密码未进入命令行或日志。"] = "sudo password verification passed; the password was not placed in a command or log.",
        ["sudo 验证没有成功，请检查管理员密码。"] = "sudo verification failed. Check the administrator password.",
        ["正在安装 Python 环境、菌落计数后端和应用文件；这一步通常最久。"] = "Installing the Python environment, colony-counting backend, and application files; this usually takes the longest.",
        ["健康检查通过。核心服务已经在树莓派上独立运行。"] = "Health check passed. Core services are now running independently on the Raspberry Pi.",
        ["SSH 主机密钥探测意外建立了连接，已中止以避免未确认的信任。"] = "SSH host-key probing unexpectedly established a connection; it was aborted to avoid unconfirmed trust.",
    };

    private static IReadOnlyDictionary<string, string> CreateGerman() => new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["Device id is required."] = "Geräte-ID ist erforderlich.",
        ["Device id contains unsupported characters."] = "Die Geräte-ID enthält nicht unterstützte Zeichen.",
        ["Display name is required."] = "Anzeigename ist erforderlich.",
        ["Host name contains unsupported characters."] = "Der Hostname enthält nicht unterstützte Zeichen.",
        ["SSH user name contains unsupported characters."] = "Der SSH-Benutzername enthält nicht unterstützte Zeichen.",
        ["SSH port must be between 1 and 65535."] = "Der SSH-Port muss zwischen 1 und 65535 liegen.",
        ["Web port must be between 1 and 65535."] = "Der Web-Port muss zwischen 1 und 65535 liegen.",
        ["A private key path is required for private-key authentication."] = "Für die Authentifizierung mit privatem Schlüssel ist ein Schlüsselpfad erforderlich.",
        ["Local address contains unsupported characters."] = "Die lokale Adresse enthält nicht unterstützte Zeichen.",
        ["Tailscale address contains unsupported characters."] = "Die Tailscale-Adresse enthält nicht unterstützte Zeichen.",
        ["无法建立 SSH 连接。请检查地址、网络和认证信息。"] = "Die SSH-Verbindung konnte nicht hergestellt werden. Adresse, Netzwerk und Anmeldedaten prüfen.",
        ["SSH 连接没有建立。请检查树莓派是否已启动并启用 SSH。"] = "Die SSH-Verbindung wurde nicht hergestellt. Prüfen, ob der Raspberry Pi läuft und SSH aktiviert ist.",
        ["发布包尚未上传。"] = "Das Veröffentlichungspaket wurde noch nicht hochgeladen.",
        ["健康检查返回了响应，但没有报告 ok=true。"] = "Die Integritätsprüfung antwortete, meldete aber nicht ok=true.",
        ["缺少所选 SSH 认证方式需要的信息。"] = "Für die gewählte SSH-Authentifizierung fehlen erforderliche Angaben.",
        ["当前账户不能无交互使用 sudo。请在树莓派系统中授予该管理员账户 sudo 权限后重试。"] = "Das aktuelle Konto kann sudo nicht verwenden. Administratorpasswort oder sudo-Rechte prüfen und erneut versuchen.",
        ["SSH 连接已经断开，请重新连接后再试。"] = "Die SSH-Verbindung wurde getrennt. Neu verbinden und erneut versuchen.",
        ["正在读取树莓派 SSH 主机密钥…"] = "SSH-Hostschlüssel des Raspberry Pi wird gelesen…",
        ["没有信任该树莓派的 SSH 主机密钥，连接已安全取消。"] = "Dem SSH-Hostschlüssel des Raspberry Pi wurde nicht vertraut. Die Verbindung wurde sicher abgebrochen.",
        ["树莓派返回了无效的 SSH SHA-256 主机密钥指纹。"] = "Der Raspberry Pi lieferte einen ungültigen SHA-256-Fingerabdruck des SSH-Hostschlüssels.",
        ["sudo 非交互检查通过。"] = "Nicht interaktive sudo-Prüfung bestanden.",
        ["sudo 密码验证通过；密码未进入命令行或日志。"] = "sudo-Passwortprüfung bestanden; das Passwort wurde weder in einen Befehl noch in ein Protokoll geschrieben.",
        ["sudo 验证没有成功，请检查管理员密码。"] = "sudo-Prüfung fehlgeschlagen. Administratorpasswort prüfen.",
        ["正在安装 Python 环境、菌落计数后端和应用文件；这一步通常最久。"] = "Python-Umgebung, Koloniezählungs-Backend und Anwendungsdateien werden installiert; dies dauert meist am längsten.",
        ["健康检查通过。核心服务已经在树莓派上独立运行。"] = "Integritätsprüfung bestanden. Die Kerndienste laufen nun selbstständig auf dem Raspberry Pi.",
        ["SSH 主机密钥探测意外建立了连接，已中止以避免未确认的信任。"] = "Die SSH-Hostschlüsselprüfung stellte unerwartet eine Verbindung her; sie wurde abgebrochen, um unbestätigtes Vertrauen zu vermeiden.",
    };

    private static string FormatPathMessage(string language, string prefix, string path) => (language, prefix) switch
    {
        (LocalizationService.English, "发布包缺少文件") => $"The release package is missing a file: {path}",
        (LocalizationService.German, "发布包缺少文件") => $"Im Veröffentlichungspaket fehlt eine Datei: {path}",
        (LocalizationService.English, "发布文件大小不匹配") => $"Release-file size mismatch: {path}",
        (LocalizationService.German, "发布文件大小不匹配") => $"Größe der Veröffentlichungsdatei stimmt nicht überein: {path}",
        (LocalizationService.English, "发布文件校验失败") => $"Release-file verification failed: {path}",
        (LocalizationService.German, "发布文件校验失败") => $"Prüfung der Veröffentlichungsdatei fehlgeschlagen: {path}",
        _ => $"{prefix}：{path}",
    };

    private static string FormatCommandFailure(string language, string exitCode, string detail) => language switch
    {
        LocalizationService.English => $"Raspberry Pi command failed (exit code {exitCode}): {detail}",
        LocalizationService.German => $"Raspberry-Pi-Befehl fehlgeschlagen (Exit-Code {exitCode}): {detail}",
        _ => $"树莓派命令失败（退出码 {exitCode}）：{detail}",
    };

    [GeneratedRegex(@"^(发布包缺少文件|发布文件大小不匹配|发布文件校验失败)：(.+)$", RegexOptions.CultureInvariant)]
    private static partial Regex PathMessage();

    [GeneratedRegex(@"^树莓派命令失败（退出码 ([^)]+)）：(.+)$", RegexOptions.CultureInvariant | RegexOptions.Singleline)]
    private static partial Regex CommandFailure();

    [GeneratedRegex(@"^正在连接 (.+)…$", RegexOptions.CultureInvariant)]
    private static partial Regex Connecting();

    [GeneratedRegex(@"^SSH 连接成功；已核对 (.+)。密码不会写入磁盘或部署日志。$", RegexOptions.CultureInvariant)]
    private static partial Regex ConnectionSucceeded();

    [GeneratedRegex(@"^已校验并上传 ([0-9]+) 个发布文件。临时目录将在安装结束后清理。$", RegexOptions.CultureInvariant)]
    private static partial Regex UploadedFiles();

    [GeneratedRegex(@"^后台服务状态：(.+)$", RegexOptions.CultureInvariant | RegexOptions.Singleline)]
    private static partial Regex ServiceStatus();

    [GeneratedRegex(@"^无法建立 SSH 连接（(.+)）。请检查地址、网络和认证信息。$", RegexOptions.CultureInvariant | RegexOptions.Singleline)]
    private static partial Regex ConnectionFailure();

    [GeneratedRegex(@"^树莓派的 SSH 主机密钥与已保存记录不一致。为防止连接到错误设备，管理器已拒绝连接。\n已保存：(.+)\n当前设备：(.+)$", RegexOptions.CultureInvariant)]
    private static partial Regex HostKeyMismatch();
}
