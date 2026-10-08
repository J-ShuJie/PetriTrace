using System.Security.Cryptography;
using System.IO;
using PiCameraControl.Manager.Core.Configuration;
using PiCameraControl.Manager.Core.Deployment;
using Renci.SshNet;
using Renci.SshNet.Common;

namespace PiCameraControl.Manager.Services;

internal sealed class SshDeploymentBackend : IDeploymentBackend, IDisposable
{
    private readonly string? _password;
    private readonly string? _sudoPassword;
    private readonly Func<string, bool> _confirmHostKey;
    private SshClient? _ssh;
    private SftpClient? _sftp;
    private string? _acceptedHostKeyAlgorithm;
    private string? _acceptedHostKeySha256;
    private HostKeyIdentity? _rejectedHostKey;
    private string? _remoteRoot;
    private ReleaseManifest? _manifest;

    public SshDeploymentBackend(
        string? password,
        string? sudoPassword,
        Func<string, bool> confirmHostKey)
    {
        _password = password;
        _sudoPassword = sudoPassword;
        _confirmHostKey = confirmHostKey;
    }

    public event EventHandler<string>? Log;

    public string? AcceptedHostKeyAlgorithm => _acceptedHostKeyAlgorithm;
    public string? AcceptedHostKeySha256 => _acceptedHostKeySha256;

    public async Task ConnectAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        _acceptedHostKeyAlgorithm = request.Profile.TrustedSshHostKeyAlgorithm;
        _acceptedHostKeySha256 = request.Profile.TrustedSshHostKeySha256;

        if (string.IsNullOrWhiteSpace(_acceptedHostKeyAlgorithm) ||
            string.IsNullOrWhiteSpace(_acceptedHostKeySha256))
        {
            OnLog("正在读取树莓派 SSH 主机密钥…");
            var candidate = await ProbeHostKeyAsync(request.Profile, cancellationToken);
            var display = $"算法：{candidate.Algorithm}\n指纹：SHA256:{candidate.Sha256}";
            if (!_confirmHostKey(display))
                throw new InvalidOperationException("没有信任该树莓派的 SSH 主机密钥，连接已安全取消。");
            if (!HostKeyTrustPolicy.TryNormalizeSha256(candidate.Sha256, out var normalizedSha256))
                throw new InvalidOperationException("树莓派返回了无效的 SSH SHA-256 主机密钥指纹。");
            _acceptedHostKeyAlgorithm = candidate.Algorithm;
            _acceptedHostKeySha256 = normalizedSha256;
        }

        _ssh = new SshClient(BuildConnectionInfo(request.Profile))
        {
            KeepAliveInterval = TimeSpan.FromSeconds(10),
        };
        _ssh.HostKeyReceived += ValidateHostKey;
        _rejectedHostKey = null;
        try
        {
            OnLog($"正在连接 {request.Profile.HostName}:{request.Profile.SshPort}…");
            await _ssh.ConnectAsync(cancellationToken);
        }
        catch (Exception exception) when (_rejectedHostKey is not null)
        {
            throw new InvalidOperationException(
                "树莓派的 SSH 主机密钥与已保存记录不一致。为防止连接到错误设备，管理器已拒绝连接。" +
                $"\n已保存：{_acceptedHostKeyAlgorithm} SHA256:{_acceptedHostKeySha256}" +
                $"\n当前设备：{_rejectedHostKey.Algorithm} SHA256:{_rejectedHostKey.Sha256}",
                exception);
        }
        catch (Exception exception) when (exception is SshException or System.Net.Sockets.SocketException)
        {
            throw new DeviceOfflineException(
                $"无法建立 SSH 连接（{exception.GetType().Name}：{exception.Message}）。请检查地址、网络和认证信息。",
                exception);
        }

        if (!_ssh.IsConnected)
            throw new DeviceOfflineException("SSH 连接没有建立。请检查树莓派是否已启动并启用 SSH。");

        OnLog($"SSH 连接成功；已核对 {_acceptedHostKeyAlgorithm} SHA256:{_acceptedHostKeySha256}。密码不会写入磁盘或部署日志。");
    }

    public Task CheckPrerequisitesAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            var output = RunChecked(
                "arch=$(uname -m); " +
                "case \"$arch\" in aarch64|arm64) ;; *) echo PICAMERA_ERROR_ARCH:$arch; exit 41;; esac; " +
                "command -v python3 >/dev/null || { echo PICAMERA_ERROR_PYTHON; exit 42; }; " +
                "command -v systemctl >/dev/null || { echo PICAMERA_ERROR_SYSTEMD; exit 43; }; " +
                "free_kb=$(df -Pk \"$HOME\" | awk 'NR==2 {print $4}'); " +
                "[ \"$free_kb\" -ge 2097152 ] || { echo PICAMERA_ERROR_SPACE:$free_kb; exit 44; }; " +
                "printf 'PICAMERA_PREFLIGHT arch=%s free_kb=%s\\n' \"$arch\" \"$free_kb\"");
            OnLog(output.Trim());

            if (HasNonInteractiveSudo())
            {
                OnLog("sudo 非交互检查通过。");
                return;
            }
            if (string.IsNullOrEmpty(_sudoPassword))
                throw new InvalidOperationException(
                    "该树莓派的 sudo 需要密码。请填写“管理员（sudo）密码”后重试；密码只会通过 SSH 标准输入发送一次。");

            var sudoCheck = RunCheckedWithInput(
                "sudo -S -p '' -v && printf 'PICAMERA_SUDO_OK\\n'",
                _sudoPassword.AsMemory(),
                TimeSpan.FromSeconds(20));
            if (!sudoCheck.Contains("PICAMERA_SUDO_OK", StringComparison.Ordinal))
                throw new InvalidOperationException("sudo 验证没有成功，请检查管理员密码。");
            OnLog("sudo 密码验证通过；密码未进入命令行或日志。");
        }, cancellationToken);
    }

    public async Task UploadAsync(
        DeploymentRequest request,
        IProgress<double>? progress,
        CancellationToken cancellationToken)
    {
        EnsureConnected();
        var manifestPath = Path.Combine(request.PayloadDirectory, "release-manifest.json");
        var manifest = await ReleaseManifest.LoadAsync(manifestPath, cancellationToken).ConfigureAwait(false);
        _manifest = manifest;
        _remoteRoot = $"/tmp/pi-camera-control-{Guid.NewGuid():N}";

        _sftp = new SftpClient(BuildConnectionInfo(request.Profile));
        _sftp.HostKeyReceived += ValidateHostKey;
        await Task.Run(() => _sftp.Connect(), cancellationToken).ConfigureAwait(false);
        CreateRemoteDirectory(_remoteRoot);

        var completed = 0;
        foreach (var file in manifest.Files)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var localPath = Path.Combine(request.PayloadDirectory, file.Path.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(localPath))
                throw new FileNotFoundException($"发布包缺少文件：{file.Path}", localPath);

            await VerifyLocalFileAsync(localPath, file, cancellationToken).ConfigureAwait(false);
            var remotePath = _remoteRoot + "/" + file.Path;
            CreateRemoteDirectory(remotePath[..remotePath.LastIndexOf('/')]);
            await using var stream = new FileStream(localPath, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true);
            await Task.Run(() => _sftp.UploadFile(stream, remotePath, true), cancellationToken).ConfigureAwait(false);
            completed++;
            progress?.Report((double)completed / manifest.Files.Count);
        }

        await using (var manifestStream = new FileStream(
            manifestPath, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true))
        {
            await Task.Run(
                () => _sftp.UploadFile(manifestStream, _remoteRoot + "/release-manifest.json", true),
                cancellationToken).ConfigureAwait(false);
        }

        OnLog($"已校验并上传 {completed} 个发布文件。临时目录将在安装结束后清理。");
    }

    public Task InstallAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (string.IsNullOrWhiteSpace(_remoteRoot) || _manifest is null)
                throw new InvalidOperationException("发布包尚未上传。");
            var installerPath = _remoteRoot + "/" + _manifest.InstallScript;
            RunChecked($"chmod 0700 {PosixShell.Quote(installerPath)}");
            OnLog("正在安装 Python 环境、菌落计数后端和应用文件；这一步通常最久。");
            var command = DeploymentCommandBuilder.BuildInstallerCommand(
                request.Profile,
                _remoteRoot,
                _manifest.InstallScript,
                request.ConfigureTouchDisplay,
                request.ConfigureTailscale,
                string.IsNullOrEmpty(_sudoPassword)
                    ? DeploymentCommandBuilder.SudoAuthenticationMode.NonInteractive
                    : DeploymentCommandBuilder.SudoAuthenticationMode.StandardInput,
                PiCameraControl.Manager.Core.Localization.LocalizationService.Instance.CurrentLanguage);
            var output = string.IsNullOrEmpty(_sudoPassword)
                ? RunChecked(command, TimeSpan.FromMinutes(30))
                : RunCheckedWithInput(command, _sudoPassword.AsMemory(), TimeSpan.FromMinutes(30));
            OnLog(KeepRelevantOutput(output));
        }, cancellationToken);
    }

    public Task ConfigureServicesAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            var output = RunChecked(
                "systemctl --user daemon-reload && " +
                "systemctl --user enable --now pi-camera-web.service && " +
                "systemctl --user is-active pi-camera-web.service");
            OnLog("后台服务状态：" + output.Trim());
        }, cancellationToken);
    }

    public Task VerifyAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            var output = RunChecked(
                $"curl --fail --silent --show-error --max-time 10 http://127.0.0.1:{request.Profile.WebPort}/health");
            if (!output.Contains("\"ok\":true", StringComparison.OrdinalIgnoreCase) &&
                !output.Contains("\"ok\": true", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("健康检查返回了响应，但没有报告 ok=true。");
            OnLog("健康检查通过。核心服务已经在树莓派上独立运行。");
            if (!string.IsNullOrWhiteSpace(_remoteRoot))
                RunChecked($"rm -rf -- {PosixShell.Quote(_remoteRoot)}");
        }, cancellationToken);
    }

    private ConnectionInfo BuildConnectionInfo(DeviceProfile profile)
    {
        AuthenticationMethod authentication = profile.AuthenticationMode switch
        {
            SshAuthenticationMode.Password when !string.IsNullOrEmpty(_password) =>
                new PasswordAuthenticationMethod(profile.SshUserName, _password),
            SshAuthenticationMode.PrivateKey when !string.IsNullOrWhiteSpace(profile.PrivateKeyPath) =>
                new PrivateKeyAuthenticationMethod(profile.SshUserName, new PrivateKeyFile(profile.PrivateKeyPath)),
            _ => throw new InvalidOperationException("缺少所选 SSH 认证方式需要的信息。"),
        };
        return new ConnectionInfo(profile.HostName, profile.SshPort, profile.SshUserName, authentication)
        {
            Timeout = TimeSpan.FromSeconds(12),
        };
    }

    private void ValidateHostKey(object? sender, HostKeyEventArgs args)
    {
        args.CanTrust = false;
        var candidate = new HostKeyIdentity(args.HostKeyName, args.FingerPrintSHA256);
        args.CanTrust = HostKeyTrustPolicy.Evaluate(
            _acceptedHostKeyAlgorithm,
            _acceptedHostKeySha256,
            candidate.Algorithm,
            candidate.Sha256).CanTrust;
        if (!args.CanTrust)
            _rejectedHostKey = candidate;
    }

    private async Task<HostKeyIdentity> ProbeHostKeyAsync(
        DeviceProfile profile,
        CancellationToken cancellationToken)
    {
        HostKeyIdentity? candidate = null;
        using var probe = new SshClient(BuildConnectionInfo(profile));
        probe.HostKeyReceived += (_, args) =>
        {
            args.CanTrust = false;
            candidate = new HostKeyIdentity(args.HostKeyName, args.FingerPrintSHA256);
        };
        try
        {
            await probe.ConnectAsync(cancellationToken);
            throw new InvalidOperationException("SSH 主机密钥探测意外建立了连接，已中止以避免未确认的信任。");
        }
        catch (SshException) when (candidate is not null)
        {
            return candidate;
        }
        catch (Exception exception) when (exception is SshException or System.Net.Sockets.SocketException)
        {
            throw new DeviceOfflineException(
                $"无法读取 SSH 主机密钥（{exception.GetType().Name}：{exception.Message}）。请检查地址和网络。",
                exception);
        }
    }

    private string RunChecked(string commandText, TimeSpan? timeout = null)
    {
        EnsureConnected();
        using var command = _ssh!.CreateCommand(commandText);
        command.CommandTimeout = timeout ?? TimeSpan.FromMinutes(2);
        var result = command.Execute();
        ThrowIfCommandFailed(command, result);
        return result;
    }

    private string RunCheckedWithInput(
        string commandText,
        ReadOnlyMemory<char> secret,
        TimeSpan? timeout = null)
    {
        EnsureConnected();
        using var command = _ssh!.CreateCommand(commandText);
        command.CommandTimeout = timeout ?? TimeSpan.FromMinutes(2);
        var execution = command.ExecuteAsync(CancellationToken.None);
        SensitiveCommandInput.WriteUtf8LineAndCloseAsync(
            command.CreateInputStream(), secret, CancellationToken.None).GetAwaiter().GetResult();
        execution.GetAwaiter().GetResult();
        var result = command.Result;
        ThrowIfCommandFailed(command, result);
        return result;
    }

    private bool HasNonInteractiveSudo()
    {
        EnsureConnected();
        using var command = _ssh!.CreateCommand("sudo -n true >/dev/null 2>&1");
        command.CommandTimeout = TimeSpan.FromSeconds(10);
        command.Execute();
        return command.ExitStatus == 0;
    }

    private static void ThrowIfCommandFailed(SshCommand command, string result)
    {
        if (command.ExitStatus != 0)
        {
            var detail = string.IsNullOrWhiteSpace(command.Error) ? result : command.Error;
            if (detail.Contains("PICAMERA_ERROR_SUDO", StringComparison.Ordinal))
                throw new InvalidOperationException("当前账户不能无交互使用 sudo。请在树莓派系统中授予该管理员账户 sudo 权限后重试。");
            throw new InvalidOperationException($"树莓派命令失败（退出码 {command.ExitStatus}）：{detail.Trim()}");
        }
    }

    private void EnsureConnected()
    {
        if (_ssh is null || !_ssh.IsConnected)
            throw new DeviceOfflineException("SSH 连接已经断开，请重新连接后再试。");
    }

    private void CreateRemoteDirectory(string path)
    {
        if (_sftp is null || string.IsNullOrWhiteSpace(path) || path == "/")
            return;
        var current = string.Empty;
        foreach (var segment in path.Split('/', StringSplitOptions.RemoveEmptyEntries))
        {
            current += "/" + segment;
            if (!_sftp.Exists(current))
                _sftp.CreateDirectory(current);
        }
    }

    private static async Task VerifyLocalFileAsync(
        string localPath,
        ReleaseFile expected,
        CancellationToken cancellationToken)
    {
        var info = new FileInfo(localPath);
        if (info.Length != expected.Size)
            throw new InvalidDataException($"发布文件大小不匹配：{expected.Path}");
        await using var stream = new FileStream(localPath, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true);
        var hash = Convert.ToHexString(await SHA256.HashDataAsync(stream, cancellationToken)).ToLowerInvariant();
        if (!hash.Equals(expected.Sha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException($"发布文件校验失败：{expected.Path}");
    }

    private static string KeepRelevantOutput(string value)
    {
        var lines = value.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        return string.Join(Environment.NewLine, lines.TakeLast(40));
    }

    private void OnLog(string message)
    {
        if (!string.IsNullOrWhiteSpace(message))
            Log?.Invoke(this, message.Trim());
    }

    public void Dispose()
    {
        if (_sftp?.IsConnected == true)
            _sftp.Disconnect();
        if (_ssh?.IsConnected == true)
            _ssh.Disconnect();
        _sftp?.Dispose();
        _ssh?.Dispose();
    }

    private sealed record HostKeyIdentity(string Algorithm, string Sha256);
}
