using PiCameraControl.Manager.Core.Configuration;

namespace PiCameraControl.Manager.Core.Deployment;

public sealed record DeploymentRequest(
    DeviceProfile Profile,
    string PayloadDirectory,
    bool ConfigureTouchDisplay = true,
    bool ConfigureTailscale = false);

public interface IDeploymentBackend
{
    Task ConnectAsync(DeploymentRequest request, CancellationToken cancellationToken);
    Task CheckPrerequisitesAsync(DeploymentRequest request, CancellationToken cancellationToken);
    Task UploadAsync(DeploymentRequest request, IProgress<double>? progress, CancellationToken cancellationToken);
    Task InstallAsync(DeploymentRequest request, CancellationToken cancellationToken);
    Task ConfigureServicesAsync(DeploymentRequest request, CancellationToken cancellationToken);
    Task VerifyAsync(DeploymentRequest request, CancellationToken cancellationToken);
}

public sealed class DeviceOfflineException : Exception
{
    public DeviceOfflineException(string message, Exception? innerException = null) : base(message, innerException) { }
}

public sealed class DeploymentCoordinator
{
    private readonly IDeploymentBackend _backend;
    private readonly DeploymentStateMachine _stateMachine;

    public DeploymentCoordinator(IDeploymentBackend backend, DeploymentStateMachine stateMachine)
    {
        _backend = backend ?? throw new ArgumentNullException(nameof(backend));
        _stateMachine = stateMachine ?? throw new ArgumentNullException(nameof(stateMachine));
    }

    public async Task<DeploymentState> RunAsync(
        DeploymentRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var validationErrors = request.Profile.Validate().ToArray();
        if (validationErrors.Length > 0)
            throw new InvalidDataException(string.Join(Environment.NewLine, validationErrors));
        if (!Directory.Exists(request.PayloadDirectory))
            throw new DirectoryNotFoundException(request.PayloadDirectory);

        try
        {
            Move(DeploymentStage.Connecting, "Connecting to Raspberry Pi…", 0.02);
            await _backend.ConnectAsync(request, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.CheckingPrerequisites, "Checking Raspberry Pi prerequisites…", 0.08);
            await _backend.CheckPrerequisitesAsync(request, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.Uploading, "Uploading application files…", 0.15);
            var uploadProgress = new CallbackProgress<double>(value =>
                RaiseProgress("Uploading application files…", 0.15 + Math.Clamp(value, 0, 1) * 0.35));
            await _backend.UploadAsync(request, uploadProgress, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.Installing, "Installing application dependencies…", 0.52);
            await _backend.InstallAsync(request, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.ConfiguringServices, "Configuring background services…", 0.76);
            await _backend.ConfigureServicesAsync(request, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.Verifying, "Verifying the installation…", 0.92);
            await _backend.VerifyAsync(request, cancellationToken).ConfigureAwait(false);

            Move(DeploymentStage.Completed, "Deployment completed.", 1);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            Move(DeploymentStage.Cancelled, "Deployment cancelled.");
        }
        catch (DeviceOfflineException exception)
        {
            Move(DeploymentStage.Offline, exception.Message, errorCode: "device-offline");
        }
        catch (Exception exception)
        {
            Move(DeploymentStage.Failed, exception.Message, errorCode: "deployment-failed");
        }

        return _stateMachine.Current;
    }

    private void RaiseProgress(string message, double progress)
    {
        if (_stateMachine.Current.Stage != DeploymentStage.Uploading)
            return;
        _stateMachine.UpdateCurrent(new DeploymentState(DeploymentStage.Uploading, message, progress));
    }

    private void Move(DeploymentStage stage, string message, double? progress = null, string? errorCode = null) =>
        _stateMachine.TransitionTo(new DeploymentState(stage, message, progress, errorCode));

    private sealed class CallbackProgress<T>(Action<T> callback) : IProgress<T>
    {
        public void Report(T value) => callback(value);
    }
}
