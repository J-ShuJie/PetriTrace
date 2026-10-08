using PiCameraControl.Manager.Core.Configuration;
using PiCameraControl.Manager.Core.Connectivity;

namespace PiCameraControl.Manager.Core.Startup;

public enum StartupOutcomeKind
{
    SetupRequired,
    OpenControlPanel,
    DeviceOffline,
    DeviceNotFound,
}

public sealed record StartupOutcome(
    StartupOutcomeKind Kind,
    DeviceProfile? Profile = null,
    Uri? ControlPanelUri = null,
    IReadOnlyList<HealthProbeResult>? Attempts = null);

public sealed class ManagerStartupService
{
    private readonly IDeviceProfileStore _store;
    private readonly ConnectionResolver _resolver;
    private readonly TimeProvider _timeProvider;

    public ManagerStartupService(
        IDeviceProfileStore store,
        ConnectionResolver resolver,
        TimeProvider? timeProvider = null)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
        _resolver = resolver ?? throw new ArgumentNullException(nameof(resolver));
        _timeProvider = timeProvider ?? TimeProvider.System;
    }

    public async Task<StartupOutcome> StartAsync(
        string? requestedDeviceId = null,
        CancellationToken cancellationToken = default)
    {
        var profiles = (await _store.LoadAsync(cancellationToken).ConfigureAwait(false)).ToArray();
        if (profiles.Length == 0)
            return new StartupOutcome(StartupOutcomeKind.SetupRequired);

        var selected = string.IsNullOrWhiteSpace(requestedDeviceId)
            ? profiles[0]
            : profiles.FirstOrDefault(profile =>
                profile.Id.Equals(requestedDeviceId, StringComparison.OrdinalIgnoreCase));
        if (selected is null)
            return new StartupOutcome(StartupOutcomeKind.DeviceNotFound);

        var resolution = await _resolver.ResolveAsync(selected, cancellationToken).ConfigureAwait(false);
        if (!resolution.IsConnected)
            return new StartupOutcome(
                StartupOutcomeKind.DeviceOffline,
                selected,
                Attempts: resolution.Attempts);

        var updated = selected with
        {
            LastConnectedAt = _timeProvider.GetUtcNow(),
            LastSuccessfulBaseUrl = resolution.Endpoint!.BaseUri.AbsoluteUri,
        };
        for (var index = 0; index < profiles.Length; index++)
        {
            if (profiles[index].Id.Equals(updated.Id, StringComparison.OrdinalIgnoreCase))
                profiles[index] = updated;
        }
        await _store.SaveAsync(profiles, cancellationToken).ConfigureAwait(false);

        return new StartupOutcome(
            StartupOutcomeKind.OpenControlPanel,
            updated,
            ManagerUrlBuilder.Build(resolution.Endpoint.BaseUri),
            resolution.Attempts);
    }
}
