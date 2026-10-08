using PiCameraControl.Manager.Core.Configuration;

namespace PiCameraControl.Manager.Core.Navigation;

public enum ManagerSurface
{
    UnconfiguredHome,
    Dashboard,
    Setup,
    DeviceSettings,
    Repair,
}

public enum ManagerWorkflow
{
    None,
    FirstDeployment,
    AddDevice,
    EditDevice,
    RepairDevice,
}

public enum SetupStep
{
    Prerequisites,
    Connection,
    Options,
    Review,
    Deploying,
}

public enum RepairPhase
{
    Connection,
    Options,
    Review,
    Executing,
}

public enum NavigationExitReason
{
    None,
    Cancelled,
    SettingsSaved,
    SetupCompleted,
    RepairCompleted,
    RepairFailed,
}

public sealed record ManagerNavigationState(
    ManagerSurface Surface,
    ManagerWorkflow Workflow = ManagerWorkflow.None,
    DeviceProfile? Device = null,
    SetupStep? WizardStep = null,
    RepairPhase? Phase = null,
    NavigationExitReason ExitReason = NavigationExitReason.None)
{
    public bool IsRoot => Surface is ManagerSurface.UnconfiguredHome or ManagerSurface.Dashboard;

    public bool CanGoBack => !IsRoot;

    public bool CanCancel => !IsRoot;

    public bool RequiresExplicitExecution =>
        Surface == ManagerSurface.Setup && WizardStep == SetupStep.Review ||
        Surface == ManagerSurface.Repair && Phase == RepairPhase.Review;
}

/// <summary>
/// Owns manager navigation only. The UI remains responsible for editing drafts,
/// persisting profiles and cancelling an in-flight deployment before leaving an
/// executing page.
/// </summary>
public sealed class ManagerNavigationController
{
    private readonly List<DeviceProfile> _profiles;
    private string? _activeDeviceId;
    private string? _returnDeviceId;

    public ManagerNavigationController(
        IEnumerable<DeviceProfile> profiles,
        string? currentDeviceId = null)
    {
        ArgumentNullException.ThrowIfNull(profiles);
        _profiles = profiles.ToList();
        if (_profiles.Select(profile => profile.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() !=
            _profiles.Count)
        {
            throw new ArgumentException("Device ids must be unique.", nameof(profiles));
        }

        if (_profiles.Count == 0)
        {
            Current = new ManagerNavigationState(ManagerSurface.UnconfiguredHome);
            return;
        }

        _activeDeviceId = string.IsNullOrWhiteSpace(currentDeviceId)
            ? _profiles[0].Id
            : FindProfile(currentDeviceId).Id;
        Current = DashboardState();
    }

    public ManagerNavigationState Current { get; private set; }

    public IReadOnlyList<DeviceProfile> Profiles => _profiles.ToArray();

    public event EventHandler<ManagerNavigationState>? Changed;

    public void SelectDevice(string deviceId)
    {
        RequireSurface(ManagerSurface.Dashboard);
        _activeDeviceId = FindProfile(deviceId).Id;
        SetCurrent(DashboardState());
    }

    public void BeginFirstDeployment()
    {
        if (_profiles.Count != 0 || Current.Surface != ManagerSurface.UnconfiguredHome)
            throw new InvalidOperationException("First deployment is available only when no device is configured.");

        _returnDeviceId = null;
        SetCurrent(SetupState(ManagerWorkflow.FirstDeployment, SetupStep.Prerequisites));
    }

    public void BeginAddDevice()
    {
        RequireSurface(ManagerSurface.Dashboard);
        _returnDeviceId = _activeDeviceId;
        SetCurrent(SetupState(ManagerWorkflow.AddDevice, SetupStep.Prerequisites));
    }

    public void AdvanceSetup()
    {
        RequireSurface(ManagerSurface.Setup);
        var next = Current.WizardStep switch
        {
            SetupStep.Prerequisites => SetupStep.Connection,
            SetupStep.Connection => SetupStep.Options,
            SetupStep.Options => SetupStep.Review,
            SetupStep.Review => throw new InvalidOperationException(
                "Call ConfirmSetupExecution to leave the review step."),
            SetupStep.Deploying => throw new InvalidOperationException(
                "The setup deployment is already executing."),
            _ => throw new InvalidOperationException("The setup step is missing."),
        };
        SetCurrent(SetupState(Current.Workflow, next));
    }

    public void ConfirmSetupExecution()
    {
        RequireSurface(ManagerSurface.Setup);
        if (Current.WizardStep != SetupStep.Review)
            throw new InvalidOperationException("Setup can execute only after review.");
        SetCurrent(SetupState(Current.Workflow, SetupStep.Deploying));
    }

    public void CompleteSetup(DeviceProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);
        RequireSurface(ManagerSurface.Setup);
        if (Current.WizardStep != SetupStep.Deploying)
            throw new InvalidOperationException("Setup has not been explicitly started.");

        var errors = profile.Validate().ToArray();
        if (errors.Length > 0)
            throw new ArgumentException(string.Join(" ", errors), nameof(profile));
        if (_profiles.Any(existing => existing.Id.Equals(profile.Id, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidOperationException($"A device named '{profile.Id}' already exists.");

        _profiles.Add(profile);
        _activeDeviceId = profile.Id;
        _returnDeviceId = null;
        SetCurrent(DashboardState(NavigationExitReason.SetupCompleted));
    }

    public void BeginDeviceSettings()
    {
        RequireSurface(ManagerSurface.Dashboard);
        SetCurrent(new ManagerNavigationState(
            ManagerSurface.DeviceSettings,
            ManagerWorkflow.EditDevice,
            ActiveProfile()));
    }

    public void SaveDeviceSettings(DeviceProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);
        RequireSurface(ManagerSurface.DeviceSettings);
        if (!profile.Id.Equals(Current.Device!.Id, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Editing a device cannot silently change its identity.");

        var errors = profile.Validate().ToArray();
        if (errors.Length > 0)
            throw new ArgumentException(string.Join(" ", errors), nameof(profile));

        var index = _profiles.FindIndex(existing =>
            existing.Id.Equals(profile.Id, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
            throw new InvalidOperationException("The device being edited no longer exists.");
        _profiles[index] = profile;
        _activeDeviceId = profile.Id;
        SetCurrent(DashboardState(NavigationExitReason.SettingsSaved));
    }

    public void BeginRepair()
    {
        RequireSurface(ManagerSurface.Dashboard);
        SetCurrent(new ManagerNavigationState(
            ManagerSurface.Repair,
            ManagerWorkflow.RepairDevice,
            ActiveProfile(),
            Phase: RepairPhase.Connection));
    }

    public void AdvanceRepair()
    {
        RequireSurface(ManagerSurface.Repair);
        var next = Current.Phase switch
        {
            RepairPhase.Connection => RepairPhase.Options,
            RepairPhase.Options => RepairPhase.Review,
            RepairPhase.Review => throw new InvalidOperationException(
                "Call ConfirmRepairExecution to leave the review phase."),
            RepairPhase.Executing => throw new InvalidOperationException(
                "Repair is already executing."),
            _ => throw new InvalidOperationException("The repair phase is missing."),
        };
        SetCurrent(Current with { Phase = next });
    }

    public void ConfirmRepairExecution()
    {
        RequireSurface(ManagerSurface.Repair);
        if (Current.Phase != RepairPhase.Review)
            throw new InvalidOperationException("Repair can execute only after review.");
        SetCurrent(Current with { Phase = RepairPhase.Executing });
    }

    public void CompleteRepair(bool succeeded)
    {
        RequireSurface(ManagerSurface.Repair);
        if (Current.Phase != RepairPhase.Executing)
            throw new InvalidOperationException("Repair has not been explicitly started.");
        SetCurrent(DashboardState(succeeded
            ? NavigationExitReason.RepairCompleted
            : NavigationExitReason.RepairFailed));
    }

    public void Back()
    {
        switch (Current.Surface)
        {
            case ManagerSurface.UnconfiguredHome:
            case ManagerSurface.Dashboard:
                return;
            case ManagerSurface.Setup when Current.WizardStep == SetupStep.Deploying:
                ExitDeepWorkflow(NavigationExitReason.Cancelled);
                return;
            case ManagerSurface.Setup when Current.WizardStep is { } step && step > SetupStep.Prerequisites:
                var previous = (SetupStep)((int)step - 1);
                SetCurrent(SetupState(Current.Workflow, previous));
                return;
            case ManagerSurface.Repair when Current.Phase == RepairPhase.Executing:
                ExitDeepWorkflow(NavigationExitReason.Cancelled);
                return;
            case ManagerSurface.Repair when Current.Phase is { } phase && phase > RepairPhase.Connection:
                SetCurrent(Current with { Phase = (RepairPhase)((int)phase - 1) });
                return;
            default:
                ExitDeepWorkflow(NavigationExitReason.Cancelled);
                return;
        }
    }

    public void Cancel()
    {
        if (!Current.IsRoot)
            ExitDeepWorkflow(NavigationExitReason.Cancelled);
    }

    private void ExitDeepWorkflow(NavigationExitReason reason)
    {
        if (Current.Workflow == ManagerWorkflow.FirstDeployment && _profiles.Count == 0)
        {
            _returnDeviceId = null;
            SetCurrent(new ManagerNavigationState(
                ManagerSurface.UnconfiguredHome,
                ExitReason: reason));
            return;
        }

        if (!string.IsNullOrWhiteSpace(_returnDeviceId))
            _activeDeviceId = FindProfile(_returnDeviceId).Id;
        _returnDeviceId = null;
        SetCurrent(DashboardState(reason));
    }

    private ManagerNavigationState SetupState(ManagerWorkflow workflow, SetupStep step) =>
        new(ManagerSurface.Setup, workflow, WizardStep: step);

    private ManagerNavigationState DashboardState(
        NavigationExitReason exitReason = NavigationExitReason.None) =>
        new(ManagerSurface.Dashboard, Device: ActiveProfile(), ExitReason: exitReason);

    private DeviceProfile ActiveProfile()
    {
        if (string.IsNullOrWhiteSpace(_activeDeviceId))
            throw new InvalidOperationException("No active device is configured.");
        return FindProfile(_activeDeviceId);
    }

    private DeviceProfile FindProfile(string deviceId) =>
        _profiles.FirstOrDefault(profile =>
            profile.Id.Equals(deviceId, StringComparison.OrdinalIgnoreCase))
        ?? throw new KeyNotFoundException($"Device '{deviceId}' was not found.");

    private void RequireSurface(ManagerSurface surface)
    {
        if (Current.Surface != surface)
            throw new InvalidOperationException(
                $"This navigation action requires {surface}, but the current surface is {Current.Surface}.");
    }

    private void SetCurrent(ManagerNavigationState state)
    {
        Current = state;
        Changed?.Invoke(this, state);
    }
}
