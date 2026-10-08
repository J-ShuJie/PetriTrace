using System.Net;
using System.Globalization;
using PiCameraControl.Manager.Core.Configuration;
using PiCameraControl.Manager.Core.Connectivity;
using PiCameraControl.Manager.Core.Deployment;
using PiCameraControl.Manager.Core.Localization;
using PiCameraControl.Manager.Core.Navigation;
using PiCameraControl.Manager.Core.Protocol;
using PiCameraControl.Manager.Core.Startup;

var tests = new (string Name, Func<Task> Run)[]
{
    ("Profile store round trip excludes passwords", ProfileStoreRoundTrip),
    ("Profile store remains compatible and persists host-key pin", ProfileHostKeyRoundTrip),
    ("Host-key trust defaults to reject and detects changes", HostKeyTrust),
    ("Endpoint catalog respects Tailscale preference", EndpointOrdering),
    ("Share links preserve both networks and HTTPS IPv6", ShareLinks),
    ("Connection resolver stops after first healthy endpoint", ResolverStopsAfterSuccess),
    ("Manager URL preserves query and sets explicit entry", ManagerUrl),
    ("Manager protocol accepts only allow-listed actions", ProtocolAllowList),
    ("Privileged protocol actions require confirmation", ProtocolConfirmation),
    ("State machine rejects invalid transition", StateMachineInvalidTransition),
    ("Coordinator completes ordered deployment", CoordinatorCompletes),
    ("Coordinator reports offline state", CoordinatorReportsOffline),
    ("POSIX quoting blocks shell expansion", PosixQuoting),
    ("Installer command contains explicit feature switches", InstallerCommand),
    ("Sudo password is written only to command stdin", SudoPasswordInput),
    ("Installer command selects stdin auth without embedding password", InstallerStdinAuth),
    ("Release manifest rejects traversal paths", ManifestRejectsTraversal),
    ("Startup remains available when device is offline", StartupOffline),
    ("Startup opens manager-tagged URL when reachable", StartupConnected),
    ("Unconfigured manager permits only first deployment", NavigationFirstDeploymentGate),
    ("First deployment completes only after explicit execution", NavigationFirstDeploymentCompletes),
    ("Configured manager starts at dashboard and requires explicit add", NavigationConfiguredGate),
    ("Add-device cancellation returns to the original dashboard", NavigationAddDeviceCancel),
    ("Completed add-device flow selects the new device", NavigationAddDeviceCompletes),
    ("Device settings save directly to dashboard without setup", NavigationSettingsSave),
    ("Device settings cancel preserves the profile", NavigationSettingsCancel),
    ("Repair reads the active profile and executes explicitly", NavigationRepairExplicitExecution),
    ("Repair cancellation returns to dashboard", NavigationRepairCancel),
    ("Setup back navigation has a predictable root", NavigationSetupBack),
    ("Localization normalizes supported system languages", LocalizationNormalizesLanguages),
    ("Localization provides complete distinct translations", LocalizationCatalogCoverage),
    ("Language preference persists and tolerates invalid JSON", LanguagePreferenceRoundTrip),
    ("Runtime messages follow the active language", RuntimeMessagesFollowLanguage),
};

var failures = 0;
foreach (var test in tests)
{
    try
    {
        await test.Run();
        Console.WriteLine($"PASS {test.Name}");
    }
    catch (Exception exception)
    {
        failures++;
        Console.Error.WriteLine($"FAIL {test.Name}: {exception}");
    }
}

Console.WriteLine($"{tests.Length - failures}/{tests.Length} tests passed.");
return failures == 0 ? 0 : 1;

static DeviceProfile Profile(PreferredConnection preferred = PreferredConnection.Automatic) => new()
{
    Id = "lab-pi",
    DisplayName = "Lab Raspberry Pi",
    HostName = "piuser",
    SshUserName = "piuser",
    PrivateKeyPath = @"C:\Users\tester\.ssh\id_ed25519",
    LocalAddress = "192.168.1.27",
    TailscaleAddress = "100.64.0.27",
    PreferredConnection = preferred,
};

static Task LocalizationNormalizesLanguages()
{
    Assert.Equal(LocalizationService.Chinese, LocalizationService.NormalizeLanguage("zh-TW"));
    Assert.Equal(LocalizationService.German, LocalizationService.NormalizeLanguage("de-AT"));
    Assert.Equal(LocalizationService.English, LocalizationService.NormalizeLanguage("en-GB"));
    Assert.Equal(LocalizationService.English, LocalizationService.NormalizeLanguage("fr-FR"));

    var preference = new MemoryLanguagePreferenceStore(LocalizationService.Chinese);
    var remembered = new LocalizationService(preference, new CultureInfo("de-DE"));
    Assert.Equal(LocalizationService.Chinese, remembered.CurrentLanguage);
    var deploy = DeploymentCommandBuilder.BuildInstallerCommand(Profile(), "/tmp/package", "deploy/install_pi.sh", false, false, uiLanguage: "de-AT");
    Assert.True(deploy.Contains("--ui-language 'de'"));
    var german = new LocalizationService(new MemoryLanguagePreferenceStore(), new CultureInfo("de-AT"));
    Assert.Equal(LocalizationService.German, german.CurrentLanguage);
    var fallback = new LocalizationService(new MemoryLanguagePreferenceStore(), new CultureInfo("fr-FR"));
    Assert.Equal(LocalizationService.English, fallback.CurrentLanguage);
    return Task.CompletedTask;
}

static Task LocalizationCatalogCoverage()
{
    var store = new MemoryLanguagePreferenceStore();
    var service = new LocalizationService(store, new CultureInfo("en-US"));
    var changed = new List<string?>();
    service.PropertyChanged += (_, args) => changed.Add(args.PropertyName);
    Assert.True(LocalizationService.TranslationKeys.Count > 100);
    foreach (var language in service.SupportedLanguages)
    {
        service.SetLanguage(language.Code, persist: false);
        foreach (var key in LocalizationService.TranslationKeys)
            Assert.False(string.IsNullOrWhiteSpace(service[key]));
    }

    service.SetLanguage(LocalizationService.Chinese, persist: false);
    var chinese = service["Action.StartDeploy"];
    service.SetLanguage(LocalizationService.English, persist: false);
    var english = service["Action.StartDeploy"];
    service.SetLanguage(LocalizationService.German, persist: false);
    var german = service["Action.StartDeploy"];
    Assert.False(chinese == english);
    Assert.False(english == german);
    service.SetLanguage(LocalizationService.Chinese);
    Assert.Equal(LocalizationService.Chinese, store.Language);
    Assert.True(changed.Contains(nameof(LocalizationService.CurrentLanguage)));
    Assert.True(changed.Contains("Item[]"));
    return Task.CompletedTask;
}

static Task LanguagePreferenceRoundTrip()
{
    var directory = Path.Combine(Path.GetTempPath(), "PiCameraControl.Localization.Tests", Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "manager-settings.json");
    var store = new JsonLanguagePreferenceStore(path);
    store.Save(LocalizationService.German);
    Assert.Equal(LocalizationService.German, store.Load());

    File.WriteAllText(path, "{not-json");
    Assert.Equal<string?>(null, store.Load());
    Directory.Delete(directory, recursive: true);
    return Task.CompletedTask;
}

static Task RuntimeMessagesFollowLanguage()
{
    var service = new LocalizationService(new MemoryLanguagePreferenceStore(), new CultureInfo("en-US"));
    var source = "SSH 连接已经断开，请重新连接后再试。";
    Assert.Equal("The SSH connection was lost. Reconnect and try again.",
        RuntimeMessageLocalizer.Translate(service, source));
    service.SetLanguage(LocalizationService.German, persist: false);
    Assert.Equal("Die SSH-Verbindung wurde getrennt. Neu verbinden und erneut versuchen.",
        RuntimeMessageLocalizer.Translate(service, source));
    Assert.Equal("Unbekannter Remote-Fehler",
        RuntimeMessageLocalizer.Translate(service, "Unbekannter Remote-Fehler"));
    return Task.CompletedTask;
}

static async Task ProfileStoreRoundTrip()
{
    var directory = Path.Combine(Path.GetTempPath(), "PiCameraControl.Tests", Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "devices.json");
    var store = new JsonDeviceProfileStore(path);
    await store.SaveAsync([Profile()]);
    var json = await File.ReadAllTextAsync(path);
    Assert.False(json.Contains("password", StringComparison.OrdinalIgnoreCase));
    var loaded = await store.LoadAsync();
    Assert.Equal(1, loaded.Count);
    Assert.Equal("piuser", loaded[0].HostName);
    File.Delete(path);
    Directory.Delete(directory);
}

static async Task ProfileHostKeyRoundTrip()
{
    var directory = Path.Combine(Path.GetTempPath(), "PiCameraControl.Tests", Guid.NewGuid().ToString("N"));
    var path = Path.Combine(directory, "devices.json");
    Directory.CreateDirectory(directory);
    await File.WriteAllTextAsync(path,
        "[{\"schemaVersion\":1,\"id\":\"old\",\"displayName\":\"Old\",\"hostName\":\"pi.local\",\"sshUserName\":\"pi\",\"privateKeyPath\":\"C:\\\\key\"}]");
    var store = new JsonDeviceProfileStore(path);
    var old = (await store.LoadAsync()).Single();
    Assert.Equal<string?>(null, old.TrustedSshHostKeySha256);

    var sha = Convert.ToBase64String(new byte[32]).TrimEnd('=');
    var pinned = old with
    {
        TrustedSshHostKeyAlgorithm = "ssh-ed25519",
        TrustedSshHostKeySha256 = sha,
    };
    await store.SaveAsync([pinned]);
    var loaded = (await store.LoadAsync()).Single();
    Assert.Equal("ssh-ed25519", loaded.TrustedSshHostKeyAlgorithm);
    Assert.Equal(sha, loaded.TrustedSshHostKeySha256);
    File.Delete(path);
    Directory.Delete(directory);
}

static Task HostKeyTrust()
{
    var sha = Convert.ToBase64String(new byte[32]).TrimEnd('=');
    var changedSha = Convert.ToBase64String(Enumerable.Repeat((byte)1, 32).ToArray()).TrimEnd('=');
    Assert.Equal(HostKeyTrustStatus.FirstSeen,
        HostKeyTrustPolicy.Evaluate(null, null, "ssh-ed25519", sha).Status);
    Assert.False(HostKeyTrustPolicy.Evaluate(null, null, "ssh-ed25519", sha).CanTrust);
    Assert.Equal(HostKeyTrustStatus.Trusted,
        HostKeyTrustPolicy.Evaluate("ssh-ed25519", sha + "=", "ssh-ed25519", sha).Status);
    Assert.Equal(HostKeyTrustStatus.Mismatch,
        HostKeyTrustPolicy.Evaluate("ssh-rsa", sha, "ssh-ed25519", sha).Status);
    Assert.Equal(HostKeyTrustStatus.Mismatch,
        HostKeyTrustPolicy.Evaluate("ssh-ed25519", sha, "ssh-ed25519", changedSha).Status);
    Assert.Equal(HostKeyTrustStatus.Mismatch,
        HostKeyTrustPolicy.Evaluate(null, null, "ssh-ed25519", "SHA256:" + sha).Status);
    Assert.True(new DeviceProfile
    {
        Id = "partial",
        DisplayName = "Partial",
        HostName = "pi.local",
        SshUserName = "pi",
        PrivateKeyPath = @"C:\key",
        TrustedSshHostKeyAlgorithm = "ssh-ed25519",
    }.Validate().Any());
    return Task.CompletedTask;
}

static Task ShareLinks()
{
    var profile = Profile() with { LocalAddress = "192.168.1.9", TailscaleAddress = "100.100.1.2", UseHttps = true, WebPort = 8443 };
    var links = EndpointCatalog.AccessLinks(profile);
    Assert.Equal("https://192.168.1.9:8443/", links.Local!.AbsoluteUri);
    Assert.Equal("https://100.100.1.2:8443/", links.Tailscale!.AbsoluteUri);
    links = EndpointCatalog.AccessLinks(profile with { LocalAddress = "::1", TailscaleAddress = null });
    Assert.Equal("https://[::1]:8443/", links.Local!.AbsoluteUri);
    Assert.True(links.Tailscale is null);
    links = EndpointCatalog.AccessLinks(profile with { LocalAddress = null, HostName = "test-pi.local" });
    Assert.Equal("test-pi.local", links.Local!.Host);
    links = EndpointCatalog.AccessLinks(profile with { LocalAddress = "100.100.1.2", HostName = "100.100.1.2" });
    Assert.True(links.Local is null);
    Assert.Equal("https://100.100.1.2:8443/", links.Tailscale!.AbsoluteUri);
    return Task.CompletedTask;
}

static Task EndpointOrdering()
{
    var endpoints = EndpointCatalog.Build(Profile(PreferredConnection.Tailscale));
    Assert.Equal(ConnectionKind.Tailscale, endpoints[0].Kind);
    Assert.Equal("100.64.0.27", endpoints[0].BaseUri.Host);
    Assert.True(endpoints.Any(endpoint => endpoint.Kind == ConnectionKind.Mdns));
    return Task.CompletedTask;
}

static async Task ResolverStopsAfterSuccess()
{
    var probe = new FakeHealthProbe(successfulKind: ConnectionKind.Mdns);
    var result = await new ConnectionResolver(probe).ResolveAsync(Profile());
    Assert.True(result.IsConnected);
    Assert.Equal(ConnectionKind.Mdns, result.Endpoint!.Kind);
    Assert.False(result.Attempts.Any(attempt => attempt.Endpoint.Kind == ConnectionKind.Tailscale));
}

static Task ManagerUrl()
{
    var result = ManagerUrlBuilder.Build(new Uri("http://device.local:5000/?display=desktop&entry=old#fragment"));
    Assert.True(result.Query.Contains("display=desktop", StringComparison.Ordinal));
    Assert.True(result.Query.Contains("entry=windows-manager", StringComparison.Ordinal));
    Assert.False(result.Query.Contains("entry=old", StringComparison.Ordinal));
    Assert.Equal(string.Empty, result.Fragment);
    return Task.CompletedTask;
}

static Task ProtocolAllowList()
{
    Assert.True(ManagerProtocolParser.TryParse(
        "picameracontrol://manage?action=diagnose&device=lab-pi", out var request));
    Assert.Equal(ManagerProtocolAction.Diagnose, request!.Action);
    Assert.False(ManagerProtocolParser.TryParse(
        "picameracontrol://manage?action=run-command&command=rm", out _));
    Assert.False(ManagerProtocolParser.TryParse(
        "picameracontrol://manage?action=open&action=repair", out _));
    Assert.False(ManagerProtocolParser.TryParse("https://manage?action=open", out _));
    return Task.CompletedTask;
}

static Task ProtocolConfirmation()
{
    Assert.True(ManagerProtocolParser.TryParse("picameracontrol://manage?action=repair", out var repair));
    Assert.True(repair!.RequiresConfirmation);
    Assert.True(ManagerProtocolParser.TryParse("picameracontrol://manage?action=open", out var open));
    Assert.False(open!.RequiresConfirmation);
    return Task.CompletedTask;
}

static Task StateMachineInvalidTransition()
{
    var machine = new DeploymentStateMachine(configured: true);
    Assert.Throws<InvalidOperationException>(() =>
        machine.TransitionTo(new DeploymentState(DeploymentStage.Installing, "Invalid")));
    return Task.CompletedTask;
}

static async Task CoordinatorCompletes()
{
    var backend = new FakeDeploymentBackend();
    var machine = new DeploymentStateMachine(configured: true);
    var states = new List<DeploymentStage>();
    machine.Changed += (_, state) => states.Add(state.Stage);
    var coordinator = new DeploymentCoordinator(backend, machine);
    var result = await coordinator.RunAsync(new DeploymentRequest(Profile(), AppContext.BaseDirectory));
    Assert.Equal(DeploymentStage.Completed, result.Stage);
    Assert.SequenceEqual(
        [DeploymentStage.Connecting, DeploymentStage.CheckingPrerequisites, DeploymentStage.Uploading,
         DeploymentStage.Installing, DeploymentStage.ConfiguringServices, DeploymentStage.Verifying,
         DeploymentStage.Completed],
        states.Distinct());
}

static async Task CoordinatorReportsOffline()
{
    var backend = new FakeDeploymentBackend { OfflineAt = DeploymentStage.Uploading };
    var machine = new DeploymentStateMachine(configured: true);
    var result = await new DeploymentCoordinator(backend, machine)
        .RunAsync(new DeploymentRequest(Profile(), AppContext.BaseDirectory));
    Assert.Equal(DeploymentStage.Offline, result.Stage);
    Assert.Equal("device-offline", result.ErrorCode);
}

static Task PosixQuoting()
{
    Assert.Equal("'normal'", PosixShell.Quote("normal"));
    Assert.Equal("'a'\"'\"'b'", PosixShell.Quote("a'b"));
    Assert.Equal("'$(touch /tmp/nope)'", PosixShell.Quote("$(touch /tmp/nope)"));
    return Task.CompletedTask;
}

static Task InstallerCommand()
{
    var command = DeploymentCommandBuilder.BuildInstallerCommand(
        Profile(), "/tmp/pi camera", "deploy/install_pi.sh", configureTouchDisplay: true, configureTailscale: false);
    Assert.True(command.Contains("'/tmp/pi camera/deploy/install_pi.sh'", StringComparison.Ordinal));
    Assert.True(command.Contains("--source '/tmp/pi camera'", StringComparison.Ordinal));
    Assert.True(command.Contains("--enable-kiosk", StringComparison.Ordinal));
    Assert.True(command.Contains("--tailscale skip", StringComparison.Ordinal));
    return Task.CompletedTask;
}

static async Task SudoPasswordInput()
{
    const string password = "s3crèt-$()'\"";
    var stream = new TrackingMemoryStream();
    await SensitiveCommandInput.WriteUtf8LineAndCloseAsync(stream, password.AsMemory());
    Assert.True(stream.WasDisposed);
    Assert.Equal(password + "\n", System.Text.Encoding.UTF8.GetString(stream.WrittenBytes));

    var invalid = new TrackingMemoryStream();
    await Assert.ThrowsAsync<ArgumentException>(() =>
        SensitiveCommandInput.WriteUtf8LineAndCloseAsync(invalid, "first\nsecond".AsMemory()));
    Assert.True(invalid.WasDisposed);
}

static Task InstallerStdinAuth()
{
    const string password = "must-never-appear";
    var command = DeploymentCommandBuilder.BuildInstallerCommand(
        Profile(), "/tmp/pi-camera", "deploy/install_pi.sh", true, false,
        DeploymentCommandBuilder.SudoAuthenticationMode.StandardInput);
    Assert.True(command.Contains("--sudo-auth stdin", StringComparison.Ordinal));
    Assert.False(command.Contains(password, StringComparison.Ordinal));
    Assert.False(Profile().ToString().Contains(password, StringComparison.Ordinal));
    return Task.CompletedTask;
}

static Task ManifestRejectsTraversal()
{
    var validHash = new string('a', 64);
    var valid = new ReleaseManifest(1, "1.0.0", "deploy/install_pi.sh",
        [new ReleaseFile("deploy/install_pi.sh", validHash, 12)]);
    valid.Validate();
    var invalid = valid with
    {
        InstallScript = "../install.sh",
        Files = [new ReleaseFile("../install.sh", validHash, 12)],
    };
    Assert.Throws<InvalidDataException>(invalid.Validate);
    return Task.CompletedTask;
}

static async Task StartupOffline()
{
    var store = new MemoryProfileStore([Profile()]);
    var service = new ManagerStartupService(
        store,
        new ConnectionResolver(new FakeHealthProbe((ConnectionKind)(-1))));
    var outcome = await service.StartAsync();
    Assert.Equal(StartupOutcomeKind.DeviceOffline, outcome.Kind);
    Assert.True(outcome.Attempts!.Count > 0);
}

static async Task StartupConnected()
{
    var store = new MemoryProfileStore([Profile()]);
    var service = new ManagerStartupService(
        store,
        new ConnectionResolver(new FakeHealthProbe(ConnectionKind.Mdns)),
        new FixedTimeProvider(new DateTimeOffset(2026, 8, 16, 0, 0, 0, TimeSpan.Zero)));
    var outcome = await service.StartAsync("LAB-PI");
    Assert.Equal(StartupOutcomeKind.OpenControlPanel, outcome.Kind);
    Assert.True(outcome.ControlPanelUri!.Query.Contains("entry=windows-manager", StringComparison.Ordinal));
    Assert.Equal(2026, store.Profiles[0].LastConnectedAt!.Value.Year);
}

static Task NavigationFirstDeploymentGate()
{
    var navigation = new ManagerNavigationController([]);
    Assert.Equal(ManagerSurface.UnconfiguredHome, navigation.Current.Surface);
    Assert.Throws<InvalidOperationException>(navigation.BeginDeviceSettings);
    Assert.Throws<InvalidOperationException>(navigation.BeginRepair);
    Assert.Throws<InvalidOperationException>(navigation.BeginAddDevice);

    navigation.BeginFirstDeployment();
    Assert.Equal(ManagerWorkflow.FirstDeployment, navigation.Current.Workflow);
    Assert.Equal(SetupStep.Prerequisites, navigation.Current.WizardStep);
    navigation.Cancel();
    Assert.Equal(ManagerSurface.UnconfiguredHome, navigation.Current.Surface);
    Assert.Equal(NavigationExitReason.Cancelled, navigation.Current.ExitReason);
    return Task.CompletedTask;
}

static Task NavigationConfiguredGate()
{
    var navigation = new ManagerNavigationController([Profile()]);
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Throws<InvalidOperationException>(navigation.BeginFirstDeployment);

    navigation.BeginAddDevice();
    Assert.Equal(ManagerSurface.Setup, navigation.Current.Surface);
    Assert.Equal(ManagerWorkflow.AddDevice, navigation.Current.Workflow);
    return Task.CompletedTask;
}

static Task NavigationFirstDeploymentCompletes()
{
    var navigation = new ManagerNavigationController([]);
    navigation.BeginFirstDeployment();
    navigation.AdvanceSetup();
    navigation.AdvanceSetup();
    navigation.AdvanceSetup();
    Assert.Equal(SetupStep.Review, navigation.Current.WizardStep);
    Assert.True(navigation.Current.RequiresExplicitExecution);
    Assert.Throws<InvalidOperationException>(navigation.AdvanceSetup);
    Assert.Throws<InvalidOperationException>(() => navigation.CompleteSetup(Profile()));

    navigation.ConfirmSetupExecution();
    navigation.CompleteSetup(Profile());
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(NavigationExitReason.SetupCompleted, navigation.Current.ExitReason);
    Assert.Equal("lab-pi", navigation.Current.Device!.Id);
    Assert.Equal(1, navigation.Profiles.Count);
    return Task.CompletedTask;
}

static Task NavigationAddDeviceCancel()
{
    var original = Profile();
    var second = original with
    {
        Id = "second-pi",
        DisplayName = "Second Raspberry Pi",
        HostName = "second-pi",
    };
    var navigation = new ManagerNavigationController([original, second], second.Id);
    navigation.BeginAddDevice();
    navigation.AdvanceSetup();
    navigation.Cancel();

    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(second.Id, navigation.Current.Device!.Id);
    Assert.Equal(2, navigation.Profiles.Count);
    Assert.Equal(NavigationExitReason.Cancelled, navigation.Current.ExitReason);
    return Task.CompletedTask;
}

static Task NavigationSettingsSave()
{
    var original = Profile();
    var navigation = new ManagerNavigationController([original]);
    navigation.BeginDeviceSettings();
    Assert.Equal(ManagerSurface.DeviceSettings, navigation.Current.Surface);
    Assert.Equal(ManagerWorkflow.EditDevice, navigation.Current.Workflow);
    Assert.Equal(original, navigation.Current.Device);

    var changed = original with { DisplayName = "Updated display name", WebPort = 5100 };
    navigation.SaveDeviceSettings(changed);
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(NavigationExitReason.SettingsSaved, navigation.Current.ExitReason);
    Assert.Equal("Updated display name", navigation.Current.Device!.DisplayName);
    Assert.Equal(5100, navigation.Profiles[0].WebPort);
    Assert.False(navigation.Current.Workflow == ManagerWorkflow.FirstDeployment);
    Assert.False(navigation.Current.Workflow == ManagerWorkflow.AddDevice);
    return Task.CompletedTask;
}

static Task NavigationAddDeviceCompletes()
{
    var original = Profile();
    var added = original with
    {
        Id = "new-pi",
        DisplayName = "New Raspberry Pi",
        HostName = "new-pi",
    };
    var navigation = new ManagerNavigationController([original]);
    navigation.BeginAddDevice();
    navigation.AdvanceSetup();
    navigation.AdvanceSetup();
    navigation.AdvanceSetup();
    navigation.ConfirmSetupExecution();
    navigation.CompleteSetup(added);

    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(added, navigation.Current.Device);
    Assert.Equal(2, navigation.Profiles.Count);
    Assert.True(navigation.Profiles.Contains(original));
    return Task.CompletedTask;
}

static Task NavigationSettingsCancel()
{
    var original = Profile();
    var navigation = new ManagerNavigationController([original]);
    navigation.BeginDeviceSettings();
    navigation.Cancel();

    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(original, navigation.Current.Device);
    Assert.Equal(original, navigation.Profiles[0]);
    return Task.CompletedTask;
}

static Task NavigationRepairExplicitExecution()
{
    var original = Profile();
    var navigation = new ManagerNavigationController([original]);
    navigation.BeginRepair();
    Assert.Equal(ManagerSurface.Repair, navigation.Current.Surface);
    Assert.Equal(original, navigation.Current.Device);
    Assert.Equal(RepairPhase.Connection, navigation.Current.Phase);
    Assert.False(navigation.Current.RequiresExplicitExecution);
    navigation.AdvanceRepair();
    Assert.Equal(RepairPhase.Options, navigation.Current.Phase);
    navigation.AdvanceRepair();
    Assert.Equal(RepairPhase.Review, navigation.Current.Phase);
    Assert.True(navigation.Current.RequiresExplicitExecution);
    Assert.Throws<InvalidOperationException>(() => navigation.CompleteRepair(succeeded: true));

    navigation.ConfirmRepairExecution();
    Assert.Equal(RepairPhase.Executing, navigation.Current.Phase);
    Assert.False(navigation.Current.RequiresExplicitExecution);
    navigation.CompleteRepair(succeeded: true);
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(NavigationExitReason.RepairCompleted, navigation.Current.ExitReason);
    Assert.Equal(original, navigation.Current.Device);
    return Task.CompletedTask;
}

static Task NavigationRepairCancel()
{
    var original = Profile();
    var navigation = new ManagerNavigationController([original]);
    navigation.BeginRepair();
    navigation.Cancel();
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(NavigationExitReason.Cancelled, navigation.Current.ExitReason);

    navigation.BeginRepair();
    navigation.AdvanceRepair();
    navigation.AdvanceRepair();
    navigation.ConfirmRepairExecution();
    navigation.Back();
    Assert.Equal(ManagerSurface.Dashboard, navigation.Current.Surface);
    Assert.Equal(original, navigation.Current.Device);
    return Task.CompletedTask;
}

static Task NavigationSetupBack()
{
    var navigation = new ManagerNavigationController([]);
    navigation.BeginFirstDeployment();
    navigation.AdvanceSetup();
    navigation.AdvanceSetup();
    Assert.Equal(SetupStep.Options, navigation.Current.WizardStep);
    navigation.Back();
    Assert.Equal(SetupStep.Connection, navigation.Current.WizardStep);
    navigation.Back();
    Assert.Equal(SetupStep.Prerequisites, navigation.Current.WizardStep);
    navigation.Back();
    Assert.Equal(ManagerSurface.UnconfiguredHome, navigation.Current.Surface);

    var configured = new ManagerNavigationController([Profile()]);
    configured.BeginAddDevice();
    configured.AdvanceSetup();
    configured.AdvanceSetup();
    configured.AdvanceSetup();
    configured.ConfirmSetupExecution();
    configured.Back();
    Assert.Equal(ManagerSurface.Dashboard, configured.Current.Surface);
    Assert.Equal(NavigationExitReason.Cancelled, configured.Current.ExitReason);
    return Task.CompletedTask;
}

sealed class FakeHealthProbe(ConnectionKind successfulKind) : IHealthProbe
{
    public Task<HealthProbeResult> ProbeAsync(DeviceEndpoint endpoint, CancellationToken cancellationToken = default) =>
        Task.FromResult(new HealthProbeResult(
            endpoint,
            endpoint.Kind == successfulKind,
            TimeSpan.FromMilliseconds(1),
            endpoint.Kind == successfulKind ? "test" : null,
            endpoint.Kind == successfulKind ? null : "unreachable",
            endpoint.Kind == successfulKind ? HttpStatusCode.OK : null));
}

sealed class FakeDeploymentBackend : IDeploymentBackend
{
    public DeploymentStage? OfflineAt { get; init; }

    public Task ConnectAsync(DeploymentRequest request, CancellationToken cancellationToken)
    {
        if (OfflineAt == DeploymentStage.Connecting)
            throw new DeviceOfflineException("The Raspberry Pi could not be reached.");
        return Task.CompletedTask;
    }

    public Task CheckPrerequisitesAsync(DeploymentRequest request, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task UploadAsync(DeploymentRequest request, IProgress<double>? progress, CancellationToken cancellationToken)
    {
        if (OfflineAt == DeploymentStage.Uploading)
            throw new DeviceOfflineException("The Raspberry Pi disconnected during upload.");
        progress?.Report(1);
        return Task.CompletedTask;
    }
    public Task InstallAsync(DeploymentRequest request, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task ConfigureServicesAsync(DeploymentRequest request, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task VerifyAsync(DeploymentRequest request, CancellationToken cancellationToken) => Task.CompletedTask;
}

sealed class MemoryProfileStore(IEnumerable<DeviceProfile> profiles) : IDeviceProfileStore
{
    public List<DeviceProfile> Profiles { get; private set; } = profiles.ToList();

    public Task<IReadOnlyList<DeviceProfile>> LoadAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult<IReadOnlyList<DeviceProfile>>(Profiles.ToArray());

    public Task SaveAsync(IEnumerable<DeviceProfile> profiles, CancellationToken cancellationToken = default)
    {
        Profiles = profiles.ToList();
        return Task.CompletedTask;
    }
}

sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
{
    public override DateTimeOffset GetUtcNow() => now;
}

sealed class MemoryLanguagePreferenceStore(string? language = null) : ILanguagePreferenceStore
{
    public string? Language { get; private set; } = language;

    public string? Load() => Language;

    public void Save(string languageCode) => Language = languageCode;
}

sealed class TrackingMemoryStream : MemoryStream
{
    public bool WasDisposed { get; private set; }
    public byte[] WrittenBytes => GetBuffer()[..checked((int)Length)];

    protected override void Dispose(bool disposing)
    {
        WasDisposed = true;
        // Keep the in-memory bytes readable so the test can verify the exact wire payload.
    }

    public override ValueTask DisposeAsync()
    {
        WasDisposed = true;
        return ValueTask.CompletedTask;
    }
}

static class Assert
{
    public static void True(bool value)
    {
        if (!value) throw new InvalidOperationException("Expected true.");
    }

    public static void False(bool value) => True(!value);

    public static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"Expected {expected}, got {actual}.");
    }

    public static void SequenceEqual<T>(IEnumerable<T> expected, IEnumerable<T> actual)
    {
        if (!expected.SequenceEqual(actual))
            throw new InvalidOperationException(
                $"Expected [{string.Join(", ", expected)}], got [{string.Join(", ", actual)}].");
    }

    public static void Throws<TException>(Action action) where TException : Exception
    {
        try
        {
            action();
        }
        catch (TException)
        {
            return;
        }
        throw new InvalidOperationException($"Expected {typeof(TException).Name}.");
    }

    public static async Task ThrowsAsync<TException>(Func<Task> action) where TException : Exception
    {
        try
        {
            await action();
        }
        catch (TException)
        {
            return;
        }
        throw new InvalidOperationException($"Expected {typeof(TException).Name}.");
    }
}
