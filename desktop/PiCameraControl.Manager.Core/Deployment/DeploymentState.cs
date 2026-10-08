namespace PiCameraControl.Manager.Core.Deployment;

public enum DeploymentStage
{
    NotConfigured,
    Ready,
    Connecting,
    CheckingPrerequisites,
    Uploading,
    Installing,
    ConfiguringServices,
    Verifying,
    Completed,
    Offline,
    Failed,
    Cancelled,
}

public sealed record DeploymentState(
    DeploymentStage Stage,
    string Message,
    double? Progress = null,
    string? ErrorCode = null)
{
    public bool IsTerminal => Stage is DeploymentStage.Completed or DeploymentStage.Offline or
        DeploymentStage.Failed or DeploymentStage.Cancelled;
}

public sealed class DeploymentStateMachine
{
    private static readonly IReadOnlyDictionary<DeploymentStage, DeploymentStage[]> AllowedTransitions =
        new Dictionary<DeploymentStage, DeploymentStage[]>
        {
            [DeploymentStage.NotConfigured] = [DeploymentStage.Ready],
            [DeploymentStage.Ready] = [DeploymentStage.Connecting],
            [DeploymentStage.Connecting] = [DeploymentStage.CheckingPrerequisites, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.CheckingPrerequisites] = [DeploymentStage.Uploading, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.Uploading] = [DeploymentStage.Installing, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.Installing] = [DeploymentStage.ConfiguringServices, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.ConfiguringServices] = [DeploymentStage.Verifying, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.Verifying] = [DeploymentStage.Completed, DeploymentStage.Offline, DeploymentStage.Failed, DeploymentStage.Cancelled],
            [DeploymentStage.Completed] = [DeploymentStage.Connecting],
            [DeploymentStage.Offline] = [DeploymentStage.Connecting],
            [DeploymentStage.Failed] = [DeploymentStage.Connecting],
            [DeploymentStage.Cancelled] = [DeploymentStage.Connecting],
        };

    public DeploymentStateMachine(bool configured)
    {
        Current = configured
            ? new DeploymentState(DeploymentStage.Ready, "Ready")
            : new DeploymentState(DeploymentStage.NotConfigured, "A device has not been configured.");
    }

    public DeploymentState Current { get; private set; }

    public event EventHandler<DeploymentState>? Changed;

    public void MarkConfigured() => TransitionTo(new DeploymentState(DeploymentStage.Ready, "Ready"));

    public void TransitionTo(DeploymentState next)
    {
        ArgumentNullException.ThrowIfNull(next);
        if (!AllowedTransitions.TryGetValue(Current.Stage, out var allowed) || !allowed.Contains(next.Stage))
            throw new InvalidOperationException($"Cannot transition from {Current.Stage} to {next.Stage}.");
        ValidateProgress(next);
        SetCurrent(next);
    }

    internal void UpdateCurrent(DeploymentState next)
    {
        ArgumentNullException.ThrowIfNull(next);
        if (next.Stage != Current.Stage)
            throw new InvalidOperationException("A progress update cannot change the deployment stage.");
        ValidateProgress(next);
        SetCurrent(next);
    }

    private static void ValidateProgress(DeploymentState state)
    {
        if (state.Progress is < 0 or > 1)
            throw new ArgumentOutOfRangeException(nameof(state), "Progress must be between 0 and 1.");
    }

    private void SetCurrent(DeploymentState next)
    {
        Current = next;
        Changed?.Invoke(this, next);
    }
}
