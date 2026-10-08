using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Media;
using Microsoft.Win32;
using PiCameraControl.Manager.Core.Configuration;
using PiCameraControl.Manager.Core.Connectivity;
using PiCameraControl.Manager.Core.Deployment;
using PiCameraControl.Manager.Core.Localization;
using PiCameraControl.Manager.Core.Protocol;
using PiCameraControl.Manager.Services;

namespace PiCameraControl.Manager;

public partial class MainWindow : Window
{
    private readonly JsonDeviceProfileStore _profileStore = new();
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(2.5) };
    private readonly ObservableCollection<DiagnosticRow> _diagnostics = [];
    private readonly LocalizationService _localizer = LocalizationService.Instance;
    private IReadOnlyList<DeviceProfile> _profiles = [];
    private DeviceProfile? _activeProfile;
    private ConnectionResolution? _resolution;
    private Uri? _controlPanelUri;
    private Uri? _tailscaleLoginUri;
    private int _wizardStep = 1;
    private readonly System.Windows.Threading.DispatcherTimer _headerTimer = new() { Interval = TimeSpan.FromSeconds(20) };
    private readonly CancellationTokenSource _headerLifetime = new();
    private string _deviceStatusKey = "Status.Initializing";
    private bool _headerProbeRunning;
    private int _connectionGeneration;
    private bool _busy;
    private string? _busyStatusKey;
    private bool _languageSelectorReady;
    private bool _deploymentCompleted;
    private bool _deploymentNeedsAttention;
    private string? _offlineConfigurationError;
    private string[] _connectionValidationKeys = [];
    private string? _connectionRuntimeMessage;
    private bool _connectionRuntimeSucceeded;
    private ManagerProtocolRequest? _protocolRequest;
    private WorkflowMode _workflowMode = WorkflowMode.FirstDeployment;

    public MainWindow()
    {
        InitializeComponent();
        LanguageSelect.SelectedValue = _localizer.CurrentLanguage;
        _languageSelectorReady = true;
        DisplayNameBox.Text = _localizer["Device.DefaultName"];
        DiagnosticsList.ItemsSource = _diagnostics;
        Loaded += MainWindow_Loaded;
        _headerTimer.Tick += async (_, _) => await RefreshDeviceConnectionAsync();
        Closed += (_, _) => { _headerTimer.Stop(); _headerLifetime.Cancel(); };
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            ManagerProtocolRegistration.EnsureRegistered();
        }
        catch
        {
            // Protocol registration is a convenience. A locked-down registry must not prevent startup.
        }

        var protocolArgument = Environment.GetCommandLineArgs()
            .Skip(1)
            .FirstOrDefault(value => value.StartsWith("picameracontrol:", StringComparison.OrdinalIgnoreCase));
        if (protocolArgument is not null &&
            ManagerProtocolParser.TryParse(protocolArgument, out var parsed))
            _protocolRequest = parsed;

        await LoadAndConnectAsync(openBrowserWhenReady: _protocolRequest is null);
        _headerTimer.Start();
    }

    public async Task HandleProtocolActivationAsync(ManagerProtocolRequest request)
    {
        while (_busy)
            await Task.Delay(100);
        _protocolRequest = request;
        if (request.Action == ManagerProtocolAction.Open)
            return;
        await LoadAndConnectAsync(openBrowserWhenReady: false);
    }

    private async Task LoadAndConnectAsync(bool openBrowserWhenReady)
    {
        if (_busy)
            return;
        SetBusy(true, "Status.FindingDevice");
        _offlineConfigurationError = null;
        SetNavigation(null, showPane: false);
        ShowOnly(LoadingPanel);
        try
        {
            _profiles = await _profileStore.LoadAsync();
            _activeProfile = SelectRequestedProfile(_profiles, _protocolRequest?.DeviceId);
            if (_activeProfile is null)
            {
                _workflowMode = WorkflowMode.FirstDeployment;
                ResetDeploymentAction();
                ShowWizard(1);
                SetDeviceHeader("Status.NotConfigured");
                return;
            }

            await ResolveActiveProfileAsync();
            if (_resolution?.Endpoint is not null)
            {
                _controlPanelUri = ManagerUrlBuilder.Build(_resolution.Endpoint.BaseUri);
                _activeProfile = _activeProfile with
                {
                    LastConnectedAt = DateTimeOffset.Now,
                    LastSuccessfulBaseUrl = _resolution.Endpoint.BaseUri.AbsoluteUri,
                };
                _profiles = _profiles.Select(profile => profile.Id == _activeProfile.Id ? _activeProfile : profile).ToArray();
                await _profileStore.SaveAsync(_profiles);
                ShowConnected();
                if (_protocolRequest?.Action == ManagerProtocolAction.Diagnose)
                    ShowDiagnostics();
                else if (_protocolRequest is { RequiresConfirmation: true })
                    HandlePrivilegedProtocolRequest(_protocolRequest);
                else if (openBrowserWhenReady)
                    OpenUri(_controlPanelUri);
            }
            else
            {
                ShowOffline();
                if (_protocolRequest?.Action == ManagerProtocolAction.Diagnose)
                    ShowDiagnostics();
            }
        }
        catch (Exception exception)
        {
            _offlineConfigurationError = exception.Message;
            ShowOffline();
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async Task ResolveActiveProfileAsync()
    {
        if (_activeProfile is null)
            return;
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var resolver = new ConnectionResolver(new HttpHealthProbe(_httpClient));
        _resolution = await resolver.ResolveAsync(_activeProfile, cancellation.Token);
        PopulateDiagnostics(_resolution);
        SetDeviceHeader(_resolution.IsConnected ? "Status.DeviceOnline" : "Status.DeviceOffline");
    }

    private static DeviceProfile? SelectRequestedProfile(
        IReadOnlyList<DeviceProfile> profiles,
        string? requestedId)
    {
        if (!string.IsNullOrWhiteSpace(requestedId))
            return profiles.FirstOrDefault(profile => profile.Id.Equals(requestedId, StringComparison.Ordinal));
        return profiles.FirstOrDefault();
    }

    private void ShowConnected()
    {
        if (_activeProfile is null || _resolution?.Endpoint is null)
            return;
        HomeDeviceName.Text = _activeProfile.DisplayName;
        HomeEndpoint.Text = _resolution.Endpoint.BaseUri.AbsoluteUri.TrimEnd('/');
        var (local, remote) = EndpointCatalog.AccessLinks(_activeProfile);
        HomeLocalAddress.Text = local?.AbsoluteUri.TrimEnd('/') ?? "";
        HomeTailscaleAddress.Text = remote?.AbsoluteUri.TrimEnd('/') ?? "";
        CopyLocalAddress.IsEnabled = local is not null;
        HomeLocalHelp.Text = _localizer[local is null ? "Home.LocalSetup" : "Home.LocalHelp"];
        CopyTailscaleAddress.IsEnabled = remote is not null;
        HomeTailscaleHelp.Text = _localizer[remote is null ? "Home.TailscaleSetup" : "Home.TailscaleHelp"];
        HomeCopyFeedback.Text = "";
        ShowOnly(HomePanel);
        SetNavigation(NavigationSection.Dashboard);
        SetDeviceHeader(_deviceStatusKey);
    }

    private void CopyHomeAddress_Click(object sender, RoutedEventArgs e)
    {
        var address = ReferenceEquals(sender, CopyLocalAddress) ? HomeLocalAddress.Text : HomeTailscaleAddress.Text;
        if (string.IsNullOrWhiteSpace(address)) return;
        try
        {
            Clipboard.SetText(address);
            HomeCopyFeedback.Text = _localizer["Home.Copied"];
        }
        catch (System.Runtime.InteropServices.COMException)
        {
            HomeCopyFeedback.Text = _localizer["Home.CopyFailed"];
        }
    }

    private void ShowOffline()
    {
        OfflineDeviceName.Text = _activeProfile?.DisplayName ?? _localizer["Offline.DefaultConfiguredDevice"];
        var attempts = _resolution?.Attempts.Count ?? 0;
        OfflineReason.Text = _offlineConfigurationError is not null
            ? _localizer.Format("Offline.ConfigReadFailed", LocalizeRuntimeMessage(_offlineConfigurationError))
            : attempts == 0
            ? _localizer["Offline.NoAddress"]
            : _localizer.Format("Offline.AttemptsNoResponse", attempts);
        ShowOnly(OfflinePanel);
        SetNavigation(NavigationSection.Dashboard);
        SetDeviceHeader(_offlineConfigurationError is null ? _deviceStatusKey : "Status.NeedsAttention");
    }

    private void ShowWizard(int step)
    {
        _wizardStep = Math.Clamp(step, 1, 4);
        ShowOnly(WizardPanel);
        var isFirstDeployment = _workflowMode == WorkflowMode.FirstDeployment;
        WizardOutline.Visibility = isFirstDeployment ? Visibility.Visible : Visibility.Collapsed;
        WizardOutlineColumn.Width = isFirstDeployment ? new GridLength(230) : new GridLength(0);
        WizardOutlineGapColumn.Width = isFirstDeployment ? new GridLength(22) : new GridLength(0);
        SetNavigation(
            _workflowMode == WorkflowMode.DeviceSettings ? NavigationSection.DeviceSettings : NavigationSection.Repair,
            showPane: !isFirstDeployment);
        WizardStep1.Visibility = _wizardStep == 1 ? Visibility.Visible : Visibility.Collapsed;
        WizardStep2.Visibility = _wizardStep == 2 ? Visibility.Visible : Visibility.Collapsed;
        WizardStep3.Visibility = _wizardStep == 3 ? Visibility.Visible : Visibility.Collapsed;
        WizardStep4.Visibility = _wizardStep == 4 ? Visibility.Visible : Visibility.Collapsed;
        var markers = new[] { Step1Marker, Step2Marker, Step3Marker, Step4Marker };
        for (var index = 0; index < markers.Length; index++)
        {
            markers[index].Background = index + 1 == _wizardStep
                ? new SolidColorBrush(Color.FromRgb(238, 246, 255))
                : Brushes.Transparent;
            if (markers[index].Child is TextBlock text)
                text.FontWeight = index + 1 == _wizardStep ? FontWeights.SemiBold : FontWeights.Normal;
        }
        ApplyWorkflowPresentation();
        if (_wizardStep == 4)
        {
            DeploySummary.Text = _localizer.Format(
                "Wizard.Deploy.Summary",
                DisplayNameBox.Text.Trim(),
                UserBox.Text.Trim(),
                HostBox.Text.Trim(),
                _localizer[TouchDisplayCheck.IsChecked == true ? "Option.Enabled" : "Option.Disabled"],
                _localizer[TailscaleCheck.IsChecked == true ? "Option.Configure" : "Option.Skip"]);
        }
    }

    private void ApplyWorkflowPresentation()
    {
        var isSetup = _workflowMode == WorkflowMode.FirstDeployment;
        var isSettings = _workflowMode == WorkflowMode.DeviceSettings;

        WizardTitleText.Text = _localizer[isSetup ? "Wizard.Title" : isSettings ? "DeviceSettings.Title" : "Repair.Title"];
        WizardDetailText.Text = _localizer[isSetup ? "Wizard.Detail" : isSettings ? "DeviceSettings.Detail" : "Repair.Detail"];
        ConnectionTitleText.Text = _localizer[isSettings ? "DeviceSettings.PageTitle" : "Wizard.Connection.Title"];
        ConnectionDetailText.Text = _localizer[isSettings ? "DeviceSettings.PageDetail" : "Wizard.Connection.Detail"];
        DeployTitleText.Text = _localizer[_workflowMode == WorkflowMode.Repair ? "Repair.DeployTitle" : "Wizard.Deploy.Title"];

        Step1Marker.Visibility = isSetup ? Visibility.Visible : Visibility.Collapsed;
        Step3Marker.Visibility = isSettings ? Visibility.Collapsed : Visibility.Visible;
        Step4Marker.Visibility = isSettings ? Visibility.Collapsed : Visibility.Visible;
        Step1Text.Text = _localizer["Wizard.Step1"];
        Step2Text.Text = _localizer[isSettings ? "DeviceSettings.Step" : _workflowMode == WorkflowMode.Repair ? "Repair.Step1" : "Wizard.Step2"];
        Step3Text.Text = _localizer[_workflowMode == WorkflowMode.Repair ? "Repair.Step2" : "Wizard.Step3"];
        Step4Text.Text = _localizer[_workflowMode == WorkflowMode.Repair ? "Repair.Step3" : "Wizard.Step4"];

        ConnectionBackButton.Content = _localizer[isSettings || _workflowMode == WorkflowMode.Repair ? "Action.Cancel" : "Action.Back"];
        ConnectionNextButton.Content = _localizer[isSettings ? "Action.SaveSettings" : "Action.Next"];
        OptionsNextButton.Content = _localizer[_workflowMode == WorkflowMode.Repair ? "Action.ReviewRepair" : "Action.ReviewDeploy"];
        DeployButton.Content = _localizer[_deploymentCompleted
            ? "Action.OpenConsole"
            : _workflowMode == WorkflowMode.Repair ? "Action.StartRepair" : "Action.StartDeploy"];

        var status = _workflowMode switch
        {
            WorkflowMode.DeviceSettings => _localizer["Status.DeviceSettings"],
            WorkflowMode.Repair => _localizer.Format("Status.RepairStep", Math.Max(1, _wizardStep - 1)),
            _ => _localizer.Format("Status.WizardStep", _wizardStep),
        };
        if (_wizardStep == 4 && _deploymentCompleted)
            SetHeader(_localizer["Status.DeploymentCompleted"], "#067647", "#ECFDF3", "#ABEFC6");
        else if (_wizardStep == 4 && _deploymentNeedsAttention)
            SetHeader(_localizer["Status.DeploymentAttention"], "#B42318", "#FEF3F2", "#FECDCA");
        else
            SetHeader(status, "#174D8C", "#EEF6FF", "#A8C4E6");
    }

    private void ShowDiagnostics()
    {
        ShowOnly(DiagnosticsPanel);
        SetNavigation(NavigationSection.Diagnostics);
        SetHeader(_localizer["Status.Diagnostics"], "#174D8C", "#EEF6FF", "#A8C4E6");
    }

    private void ShowNotices()
    {
        ShowOnly(NoticesPanel);
        if (NoticeSelect.SelectedIndex < 0) NoticeSelect.SelectedIndex = 0;
        else if (NoticeSelect.SelectedItem is ComboBoxItem { Tag: string selected }) LoadNotice(selected);
        SetNavigation(NavigationSection.Notices);

    }

    private void ShowPrivacy()
    {
        ShowOnly(PrivacyPanel);
        SetNavigation(NavigationSection.Privacy);

    }

    private void PopulateDiagnostics(ConnectionResolution resolution)
    {
        _diagnostics.Clear();
        foreach (var attempt in resolution.Attempts)
        {
            _diagnostics.Add(new DiagnosticRow(
                TranslateKind(attempt.Endpoint.Kind),
                attempt.Endpoint.BaseUri.AbsoluteUri.TrimEnd('/'),
                attempt.IsHealthy ? _localizer["Diagnostics.Healthy"] : LocalizeRuntimeMessage(attempt.Error ?? _localizer["Diagnostics.NoResponse"]),
                $"{attempt.Duration.TotalMilliseconds:0} ms"));
        }
        if (_diagnostics.Count == 0)
            _diagnostics.Add(new DiagnosticRow(_localizer["Diagnostics.Configuration"], "—", _localizer["Diagnostics.NoCandidate"], "—"));
    }

    private string TranslateKind(ConnectionKind kind) => kind switch
    {
        ConnectionKind.LastSuccessful => _localizer["Connection.LastSuccessful"],
        ConnectionKind.LocalNetwork => _localizer["Connection.LocalNetwork"],
        ConnectionKind.Mdns => _localizer["Connection.Mdns"],
        ConnectionKind.Tailscale => _localizer["Connection.Tailscale"],
        _ => kind.ToString(),
    };

    private void ShowOnly(UIElement panel)
    {
        if (!_busy) OperationStatusPill.Visibility = Visibility.Collapsed;
        foreach (var candidate in new UIElement[]
                 {
                     LoadingPanel, HomePanel, OfflinePanel, WizardPanel, DiagnosticsPanel, NoticesPanel, PrivacyPanel,
                 })
            candidate.Visibility = ReferenceEquals(candidate, panel) ? Visibility.Visible : Visibility.Collapsed;
    }

    private void SetNavigation(NavigationSection? selected, bool showPane = true)
    {
        NavigationPane.Visibility = showPane ? Visibility.Visible : Visibility.Collapsed;
        var buttons = new (Button Button, NavigationSection Section)[]
        {
            (DashboardNavButton, NavigationSection.Dashboard),
            (DeviceSettingsNavButton, NavigationSection.DeviceSettings),
            (DiagnosticsNavButton, NavigationSection.Diagnostics),
            (RepairNavButton, NavigationSection.Repair),
            (NoticesNavButton, NavigationSection.Notices),
            (PrivacyNavButton, NavigationSection.Privacy),
        };
        foreach (var (button, section) in buttons)
            button.Tag = selected == section ? "Selected" : null;
    }

    private void SetDeviceHeader(string key)
    {
        _deviceStatusKey = key;
        var online = key == "Status.DeviceOnline";
        var problem = key is "Status.DeviceOffline" or "Status.NeedsAttention";
        var foreground = online ? "#067647" : problem ? "#B42318" : "#667085";
        HeaderStatusText.Text = _localizer[key];
        HeaderStatusText.Foreground = BrushFrom(foreground);
        HeaderStatusDot.Fill = BrushFrom(foreground);
        HeaderStatusPill.Background = BrushFrom(online ? "#ECFDF3" : problem ? "#FEF3F2" : "#F2F4F7");
        HeaderStatusPill.BorderBrush = BrushFrom(online ? "#ABEFC6" : problem ? "#FECDCA" : "#D0D5DD");
    }

    private void SetHeader(string text, string foreground, string background, string border)
    {
        OperationStatusPill.Visibility = Visibility.Visible;
        OperationStatusText.Text = text;
        OperationStatusText.Foreground = BrushFrom(foreground);
        OperationStatusPill.Background = BrushFrom(background);
        OperationStatusPill.BorderBrush = BrushFrom(border);
    }

    private async Task RefreshDeviceConnectionAsync()
    {
        if (_busy || _headerProbeRunning || _activeProfile is null || _headerLifetime.IsCancellationRequested) return;
        var profile = _activeProfile;
        var generation = _connectionGeneration;
        _headerProbeRunning = true;
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(_headerLifetime.Token);
            timeout.CancelAfter(TimeSpan.FromSeconds(10));
            var resolver = new ConnectionResolver(new HttpHealthProbe(_httpClient));
            var resolution = await resolver.ResolveAsync(profile, timeout.Token);
            // Ignore results overtaken by editing, deployment or a different device.
            if (_busy || generation != _connectionGeneration || !ReferenceEquals(profile, _activeProfile) || _headerLifetime.IsCancellationRequested) return;
            _resolution = resolution;
            _controlPanelUri = resolution.Endpoint is null ? null : ManagerUrlBuilder.Build(resolution.Endpoint.BaseUri);
            SetDeviceHeader(resolution.IsConnected ? "Status.DeviceOnline" : "Status.DeviceOffline");
            PopulateDiagnostics(resolution);
        }
        catch (OperationCanceledException)
        {
            if (!_headerLifetime.IsCancellationRequested && !_busy && generation == _connectionGeneration && ReferenceEquals(profile, _activeProfile))
                SetDeviceHeader("Status.DeviceOffline");
        }
        catch (Exception)
        {
            if (!_headerLifetime.IsCancellationRequested && !_busy && generation == _connectionGeneration && ReferenceEquals(profile, _activeProfile))
                SetDeviceHeader("Status.NeedsAttention");
        }
        finally { _headerProbeRunning = false; }
    }

    private static SolidColorBrush BrushFrom(string hex) =>
        new((Color)ColorConverter.ConvertFromString(hex));

    private void SetBusy(bool busy, string? statusKey = null)
    {
        _busy = busy;
        if (busy) _connectionGeneration++;
        _busyStatusKey = busy ? statusKey : null;
        if (!busy) { RefreshLocalizedRuntimeText(); return; }
        if (!string.IsNullOrWhiteSpace(statusKey))
            SetHeader(_localizer[statusKey], "#174D8C", "#EEF6FF", "#A8C4E6");
    }

    private static void OpenUri(Uri? uri)
    {
        if (uri is null)
            return;
        Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
    }

    private void HandlePrivilegedProtocolRequest(ManagerProtocolRequest request)
    {
        var action = _localizer[request.Action == ManagerProtocolAction.Update ? "Protocol.Update" : "Protocol.Repair"];
        var answer = MessageBox.Show(
            _localizer.Format("Protocol.Confirm", action),
            _localizer["Protocol.ConfirmTitle"],
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (answer == MessageBoxResult.Yes)
        {
            _protocolRequest = null;
            OpenRepairWorkflow();
        }
        else
        {
            _protocolRequest = null;
        }
    }

    private void OpenControlPanel_Click(object sender, RoutedEventArgs e) => OpenUri(_controlPanelUri);

    private async void RetryConnection_Click(object sender, RoutedEventArgs e) =>
        await LoadAndConnectAsync(openBrowserWhenReady: false);

    private void ShowDiagnostics_Click(object sender, RoutedEventArgs e) => ShowDiagnostics();

    private void DashboardNav_Click(object sender, RoutedEventArgs e) => ReturnToDashboard();

    private void DeviceSettingsNav_Click(object sender, RoutedEventArgs e) => EditDevice_Click(sender, e);

    private void DiagnosticsNav_Click(object sender, RoutedEventArgs e) => ShowDiagnostics();

    private void RepairNav_Click(object sender, RoutedEventArgs e) => Repair_Click(sender, e);

    private void NoticesNav_Click(object sender, RoutedEventArgs e) => ShowNotices();

    private void PrivacyNav_Click(object sender, RoutedEventArgs e) => ShowPrivacy();

    private void BackFromDiagnostics_Click(object sender, RoutedEventArgs e)
    {
        if (_resolution?.IsConnected == true)
            ShowConnected();
        else
            ShowOffline();
    }

    private void CopyDiagnostics_Click(object sender, RoutedEventArgs e)
    {
        var lines = _diagnostics.Select(row => $"{row.Label}\t{row.Address}\t{row.Result}\t{row.Duration}");
        Clipboard.SetText(string.Join(Environment.NewLine, lines));
    }

    private void EditDevice_Click(object sender, RoutedEventArgs e)
    {
        FillWizardFromProfile();
        _workflowMode = WorkflowMode.DeviceSettings;
        ShowWizard(2);
    }

    private void Repair_Click(object sender, RoutedEventArgs e) => OpenRepairWorkflow();

    private void OpenRepairWorkflow()
    {
        FillWizardFromProfile();
        _workflowMode = WorkflowMode.Repair;
        ResetDeploymentAction();
        ShowWizard(2);
    }

    private void ResetDeploymentAction()
    {
        _deploymentCompleted = false;
        _deploymentNeedsAttention = false;
        DeployButton.Click -= FinishAndOpen_Click;
        DeployButton.Click -= Deploy_Click;
        DeployButton.Click += Deploy_Click;
        DeployButton.IsEnabled = true;
    }

    private void FillWizardFromProfile()
    {
        if (_activeProfile is null)
            return;
        DisplayNameBox.Text = _activeProfile.DisplayName;
        HostBox.Text = _activeProfile.HostName;
        UserBox.Text = _activeProfile.SshUserName;
        TouchDisplayCheck.IsChecked = _activeProfile.TouchDisplayEnabled;
        TailscaleAddressBox.Text = _activeProfile.TailscaleAddress ?? string.Empty;
        TailscaleCheck.IsChecked = !string.IsNullOrWhiteSpace(_activeProfile.TailscaleAddress);
        AuthModeBox.SelectedIndex = _activeProfile.AuthenticationMode == SshAuthenticationMode.Password ? 0 : 1;
        PrivateKeyBox.Text = _activeProfile.PrivateKeyPath ?? string.Empty;
    }

    private async void WizardNext_Click(object sender, RoutedEventArgs e)
    {
        if (_wizardStep == 1 && new[] { PrereqOs, PrereqAccount, PrereqNetwork, PrereqSsh, PrereqBoot }
                .Any(check => check.IsChecked != true))
        {
            MessageBox.Show(_localizer["Prepare.Incomplete"], _localizer["Prepare.IncompleteTitle"],
                MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        if (_wizardStep == 2)
        {
            if (!ValidateConnectionFields(requireSessionCredentials: _workflowMode != WorkflowMode.DeviceSettings))
                return;
            if (_workflowMode == WorkflowMode.DeviceSettings)
            {
                var profile = BuildProfile();
                var validation = profile.Validate().ToArray();
                if (validation.Length > 0)
                {
                    MessageBox.Show(string.Join(Environment.NewLine, validation.Select(LocalizeRuntimeMessage)),
                        _localizer["Validation.ConfigurationTitle"], MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                _activeProfile = profile;
                _profiles = _profiles.Select(item => item.Id == profile.Id ? profile : item).ToArray();
                await _profileStore.SaveAsync(_profiles);
                _protocolRequest = null;
                await LoadAndConnectAsync(openBrowserWhenReady: false);
                return;
            }
        }
        ShowWizard(_wizardStep + 1);
    }

    private void WizardBack_Click(object sender, RoutedEventArgs e)
    {
        if ((_workflowMode == WorkflowMode.DeviceSettings || _workflowMode == WorkflowMode.Repair) && _wizardStep <= 2)
            ReturnToDashboard();
        else if (_wizardStep <= 1 && _activeProfile is not null)
            ReturnToDashboard();
        else
            ShowWizard(_wizardStep - 1);
    }

    private void ReturnToDashboard()
    {
        if (_resolution?.IsConnected == true)
            ShowConnected();
        else
            ShowOffline();
    }

    private bool ValidateConnectionFields(bool requireSessionCredentials = true)
    {
        var errors = new List<string>();
        if (string.IsNullOrWhiteSpace(DisplayNameBox.Text)) errors.Add("Validation.DeviceName");
        if (string.IsNullOrWhiteSpace(HostBox.Text)) errors.Add("Validation.Host");
        if (string.IsNullOrWhiteSpace(UserBox.Text)) errors.Add("Validation.SshUser");
        if (requireSessionCredentials && SelectedAuthenticationMode() == SshAuthenticationMode.Password && string.IsNullOrEmpty(PasswordInput.Password))
            errors.Add("Validation.Password");
        if (SelectedAuthenticationMode() == SshAuthenticationMode.PrivateKey && !File.Exists(PrivateKeyBox.Text.Trim()))
            errors.Add("Validation.PrivateKey");
        _connectionValidationKeys = errors.ToArray();
        _connectionRuntimeMessage = null;
        _connectionRuntimeSucceeded = false;
        ConnectionValidationText.Foreground = FindResource("DangerBrush") as Brush;
        ConnectionValidationText.Text = string.Join(Environment.NewLine, errors.Select(key => _localizer[key]));
        ConnectionValidationText.Visibility = errors.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
        return errors.Count == 0;
    }

    private SshAuthenticationMode SelectedAuthenticationMode() =>
        AuthModeBox.SelectedIndex == 1 ? SshAuthenticationMode.PrivateKey : SshAuthenticationMode.Password;

    private DeviceProfile BuildProfile() => new()
    {
        Id = _activeProfile?.Id ?? Guid.NewGuid().ToString("N"),
        DisplayName = DisplayNameBox.Text.Trim(),
        HostName = HostBox.Text.Trim().TrimEnd('.'),
        SshUserName = UserBox.Text.Trim(),
        AuthenticationMode = SelectedAuthenticationMode(),
        PrivateKeyPath = SelectedAuthenticationMode() == SshAuthenticationMode.PrivateKey
            ? PrivateKeyBox.Text.Trim()
            : null,
        TouchDisplayEnabled = TouchDisplayCheck.IsChecked == true,
        LocalAddress = _activeProfile?.LocalAddress,
        TailscaleAddress = TailscaleCheck.IsChecked != true
            ? null
            : string.IsNullOrWhiteSpace(TailscaleAddressBox.Text)
                ? _activeProfile?.TailscaleAddress
                : TailscaleAddressBox.Text.Trim(),
        PreferredConnection = _activeProfile?.PreferredConnection ?? PreferredConnection.Automatic,
        TrustedSshHostKeyAlgorithm = string.Equals(
            _activeProfile?.HostName, HostBox.Text.Trim().TrimEnd('.'), StringComparison.OrdinalIgnoreCase)
            ? _activeProfile?.TrustedSshHostKeyAlgorithm
            : null,
        TrustedSshHostKeySha256 = string.Equals(
            _activeProfile?.HostName, HostBox.Text.Trim().TrimEnd('.'), StringComparison.OrdinalIgnoreCase)
            ? _activeProfile?.TrustedSshHostKeySha256
            : null,
        LastConnectedAt = _activeProfile?.LastConnectedAt,
        LastSuccessfulBaseUrl = _activeProfile?.LastSuccessfulBaseUrl,
    };

    private async void TestSsh_Click(object sender, RoutedEventArgs e)
    {
        if (!ValidateConnectionFields() || _busy)
            return;
        SetBusy(true, "Status.TestingSsh");
        TestSshButton.IsEnabled = false;
        try
        {
            var profile = BuildProfile();
            using var backend = CreateBackend();
            var request = new DeploymentRequest(profile, PayloadLocator.FindSourceRoot(), profile.TouchDisplayEnabled, false);
            await backend.ConnectAsync(request, CancellationToken.None);
            profile = await PersistAcceptedHostKeyAsync(profile, backend);
            await backend.CheckPrerequisitesAsync(request, CancellationToken.None);
            _connectionValidationKeys = ["Ssh.Success"];
            _connectionRuntimeMessage = null;
            _connectionRuntimeSucceeded = true;
            ConnectionValidationText.Foreground = new SolidColorBrush(Color.FromRgb(6, 118, 71));
            ConnectionValidationText.Text = _localizer["Ssh.Success"];
            ConnectionValidationText.Visibility = Visibility.Visible;
        }
        catch (Exception exception)
        {
            _connectionValidationKeys = [];
            _connectionRuntimeMessage = exception.Message;
            _connectionRuntimeSucceeded = false;
            ConnectionValidationText.Foreground = FindResource("DangerBrush") as Brush;
            ConnectionValidationText.Text = LocalizeRuntimeMessage(exception.Message);
            ConnectionValidationText.Visibility = Visibility.Visible;
        }
        finally
        {
            TestSshButton.IsEnabled = true;
            SetBusy(false);
            ApplyWorkflowPresentation();
        }
    }

    private async void Deploy_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || !ValidateConnectionFields())
            return;
        var profile = BuildProfile();
        var validation = profile.Validate().ToArray();
        if (validation.Length > 0)
        {
            MessageBox.Show(string.Join(Environment.NewLine, validation.Select(LocalizeRuntimeMessage)), _localizer["Validation.ConfigurationTitle"],
                MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        SetBusy(true, "Status.Deploying");
        DeployButton.IsEnabled = false;
        DeployBackButton.IsEnabled = false;
        DeployLog.Clear();
        _tailscaleLoginUri = null;
        _deploymentCompleted = false;
        _deploymentNeedsAttention = false;
        OpenTailscaleLoginButton.Visibility = Visibility.Collapsed;
        DeployProgress.Value = 0;
        try
        {
            _activeProfile = profile;
            _profiles = _profiles.Where(item => item.Id != profile.Id).Append(profile).ToArray();
            await _profileStore.SaveAsync(_profiles);

            using var backend = CreateBackend();
            backend.Log += (_, message) => Dispatcher.Invoke(() => AppendDeployLog(LocalizeRuntimeMessage(message)));
            var stateMachine = new DeploymentStateMachine(configured: true);
            stateMachine.Changed += (_, state) => Dispatcher.Invoke(() =>
            {
                DeployProgress.Value = (state.Progress ?? 0) * 100;
                AppendDeployLog(TranslateDeploymentState(state));
            });
            var coordinator = new DeploymentCoordinator(backend, stateMachine);
            var request = new DeploymentRequest(
                profile,
                PayloadLocator.FindPayload(),
                TouchDisplayCheck.IsChecked == true,
                TailscaleCheck.IsChecked == true);
            var finalState = await coordinator.RunAsync(request);
            profile = await PersistAcceptedHostKeyAsync(profile, backend);
            if (finalState.Stage != DeploymentStage.Completed)
                throw new InvalidOperationException(finalState.Message);

            _deploymentCompleted = true;
            _deploymentNeedsAttention = false;
            DeployButton.Content = _localizer["Action.OpenConsole"];
            DeployButton.IsEnabled = true;
            DeployButton.Click -= Deploy_Click;
            DeployButton.Click += FinishAndOpen_Click;
            SetHeader(_localizer["Status.DeploymentCompleted"], "#067647", "#ECFDF3", "#ABEFC6");
            await ResolveActiveProfileAsync();
        }
        catch (Exception exception)
        {
            _deploymentNeedsAttention = true;
            AppendDeployLog(_localizer.Format("Deploy.NotCompleted", LocalizeRuntimeMessage(exception.Message)));
            DeployButton.IsEnabled = true;
            DeployBackButton.IsEnabled = true;
            SetHeader(_localizer["Status.DeploymentAttention"], "#B42318", "#FEF3F2", "#FECDCA");
        }
        finally
        {
            _busy = false;
        }
    }

    private SshDeploymentBackend CreateBackend()
    {
        var sshPassword = SelectedAuthenticationMode() == SshAuthenticationMode.Password
            ? PasswordInput.Password
            : null;
        var sudoPassword = string.IsNullOrEmpty(SudoPasswordInput.Password)
            ? sshPassword
            : SudoPasswordInput.Password;
        var backend = new SshDeploymentBackend(
            sshPassword,
            sudoPassword,
            fingerprint =>
            {
                bool ShowConfirmation() => MessageBox.Show(
                    _localizer.Format("Ssh.FingerprintPrompt", fingerprint),
                    _localizer["Ssh.FingerprintTitle"],
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Question) == MessageBoxResult.Yes;
                return Dispatcher.CheckAccess() ? ShowConfirmation() : Dispatcher.Invoke(ShowConfirmation);
            });
        return backend;
    }

    private async Task<DeviceProfile> PersistAcceptedHostKeyAsync(
        DeviceProfile profile,
        SshDeploymentBackend backend)
    {
        if (string.IsNullOrWhiteSpace(backend.AcceptedHostKeyAlgorithm) ||
            string.IsNullOrWhiteSpace(backend.AcceptedHostKeySha256) ||
            (string.Equals(profile.TrustedSshHostKeyAlgorithm, backend.AcceptedHostKeyAlgorithm, StringComparison.Ordinal) &&
             string.Equals(profile.TrustedSshHostKeySha256, backend.AcceptedHostKeySha256, StringComparison.Ordinal)))
            return profile;

        var updated = profile with
        {
            TrustedSshHostKeyAlgorithm = backend.AcceptedHostKeyAlgorithm,
            TrustedSshHostKeySha256 = backend.AcceptedHostKeySha256,
        };
        _profiles = _profiles.Where(item => item.Id != updated.Id).Append(updated).ToArray();
        _activeProfile = updated;
        await _profileStore.SaveAsync(_profiles);
        return updated;
    }

    private void AppendDeployLog(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
            return;
        var authorization = Regex.Match(
            message,
            @"PICAMERA_TAILSCALE_AUTH_URL\s+(https://[^\s]+)",
            RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
        if (authorization.Success && Uri.TryCreate(authorization.Groups[1].Value, UriKind.Absolute, out var loginUri) &&
            loginUri.Scheme == Uri.UriSchemeHttps)
        {
            _tailscaleLoginUri = loginUri;
            OpenTailscaleLoginButton.Visibility = Visibility.Visible;
        }
        DeployLog.AppendText($"[{DateTime.Now:HH:mm:ss}] {message.Trim()}{Environment.NewLine}");
        DeployLog.ScrollToEnd();
    }

    private void OpenTailscaleLogin_Click(object sender, RoutedEventArgs e) =>
        OpenUri(_tailscaleLoginUri);

    private string TranslateDeploymentState(DeploymentState state) => state.Stage switch
    {
        DeploymentStage.Connecting => _localizer["Deploy.Stage.Connecting"],
        DeploymentStage.CheckingPrerequisites => _localizer["Deploy.Stage.CheckingPrerequisites"],
        DeploymentStage.Uploading => _localizer["Deploy.Stage.Uploading"],
        DeploymentStage.Installing => _localizer["Deploy.Stage.Installing"],
        DeploymentStage.ConfiguringServices => _localizer["Deploy.Stage.ConfiguringServices"],
        DeploymentStage.Verifying => _localizer["Deploy.Stage.Verifying"],
        DeploymentStage.Completed => _localizer["Deploy.Stage.Completed"],
        DeploymentStage.Offline => _localizer.Format("Deploy.Stage.Offline", LocalizeRuntimeMessage(state.Message)),
        DeploymentStage.Failed => _localizer.Format("Deploy.Stage.Failed", LocalizeRuntimeMessage(state.Message)),
        DeploymentStage.Cancelled => _localizer["Deploy.Stage.Cancelled"],
        _ => LocalizeRuntimeMessage(state.Message),
    };

    private async void FinishAndOpen_Click(object sender, RoutedEventArgs e)
    {
        await LoadAndConnectAsync(openBrowserWhenReady: true);
    }

    private void AuthModeBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (PasswordFields is null || PrivateKeyFields is null)
            return;
        var privateKey = SelectedAuthenticationMode() == SshAuthenticationMode.PrivateKey;
        PasswordFields.Visibility = privateKey ? Visibility.Collapsed : Visibility.Visible;
        PrivateKeyFields.Visibility = privateKey ? Visibility.Visible : Visibility.Collapsed;
    }

    private void BrowsePrivateKey_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = _localizer["FileDialog.PrivateKeyTitle"],
            Filter = _localizer["FileDialog.PrivateKeyFilter"],
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) == true)
            PrivateKeyBox.Text = dialog.FileName;
    }

    private void OpenImagerHelp_Click(object sender, RoutedEventArgs e)
    {
        MessageBox.Show(
            _localizer["Imager.Help"],
            _localizer["Imager.HelpTitle"],
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private void TailscaleCheck_Changed(object sender, RoutedEventArgs e)
    {
        if (TailscaleOptionsPanel is null)
            return;
        TailscaleOptionsPanel.Visibility = TailscaleCheck.IsChecked == true
            ? Visibility.Visible
            : Visibility.Collapsed;
        if (TailscaleCheck.IsChecked == true)
            RefreshWindowsTailscaleStatus();
    }

    private void CheckWindowsTailscale_Click(object sender, RoutedEventArgs e) =>
        RefreshWindowsTailscaleStatus();

    private void RefreshWindowsTailscaleStatus()
    {
        var executable = FindWindowsTailscaleExecutable();
        if (executable is null)
        {
            TailscaleWindowsStatus.Text = _localizer["Tailscale.NotFound"];
            TailscaleWindowsStatus.Foreground = FindResource("MutedTextBrush") as Brush;
            return;
        }

        TailscaleWindowsStatus.Text = _localizer.Format("Tailscale.Found", executable);
        TailscaleWindowsStatus.Foreground = new SolidColorBrush(Color.FromRgb(6, 118, 71));
    }

    private static string? FindWindowsTailscaleExecutable()
    {
        var candidates = new List<string>();
        foreach (var root in new[]
                 {
                     Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                     Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                     Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                 })
        {
            if (!string.IsNullOrWhiteSpace(root))
                candidates.Add(Path.Combine(root, "Tailscale", "tailscale.exe"));
        }

        var path = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        candidates.AddRange(path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries)
            .Select(folder => Path.Combine(folder.Trim().Trim('"'), "tailscale.exe")));
        return candidates.FirstOrDefault(File.Exists);
    }

    private void OpenTailscaleDownload_Click(object sender, RoutedEventArgs e) =>
        OpenUri(new Uri("https://tailscale.com/download/windows"));

    private void NoticeSelect_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (NoticeReader is not null && NoticeSelect.SelectedItem is ComboBoxItem { Tag: string document }) LoadNotice(document);
    }

    private void LoadNotice(string name)
    {
        using var stream = typeof(MainWindow).Assembly.GetManifestResourceStream("Notices." + name);
        var text = stream is null ? _localizer["Notices.Missing"] : new StreamReader(stream).ReadToEnd();
        var document = new FlowDocument { FontFamily = new FontFamily("Segoe UI"), FontSize = 14,
            PagePadding = new Thickness(0, 0, 16, 0), TextAlignment = TextAlignment.Left, Foreground = (Brush)FindResource("TextBrush") };
        if (name != "Overview")
        {
            foreach (var block in Regex.Split(text.Trim(), @"\r?\n\s*\r?\n"))
                document.Blocks.Add(new Paragraph(new Run(Regex.Replace(block.Trim(), @"\r?\n", " ")))
                    { Margin = new Thickness(0, 0, 0, 14), LineHeight = 22 });
            NoticeReader.Document = document;
            return;
        }
        Table? table = null;
        foreach (var raw in text.Split('\n'))
        {
            var line = raw.Trim();
            if (line.StartsWith('|'))
            {
                var cells = line.Trim('|').Split('|').Select(value => value.Trim()).ToArray();
                if (cells.All(value => Regex.IsMatch(value, @"^[-: ]+$"))) continue;
                if (table is null)
                {
                    table = new Table { CellSpacing = 0, Margin = new Thickness(0, 8, 0, 16) };
                    foreach (var cell in cells) table.Columns.Add(new TableColumn { Width = new GridLength(1, GridUnitType.Star) });
                    table.RowGroups.Add(new TableRowGroup()); document.Blocks.Add(table);
                }
                var row = new TableRow();
                foreach (var cell in cells) row.Cells.Add(new TableCell(new Paragraph(new Run(cell.Replace("`", ""))))
                { Padding = new Thickness(8), BorderBrush = (Brush)FindResource("BorderBrush"), BorderThickness = new Thickness(0, 0, 0, 1) });
                if (table.RowGroups[0].Rows.Count == 0) { row.FontWeight = FontWeights.SemiBold; row.Background = (Brush)FindResource("CanvasBrush"); }
                table.RowGroups[0].Rows.Add(row); continue;
            }
            table = null;
            if (line.Length == 0) continue;
            var level = line.TakeWhile(c => c == '#').Count();
            var paragraph = new Paragraph(new Run(line.TrimStart('#', ' ').Replace("**", "").Replace("`", "")))
                { Margin = new Thickness(0, level > 0 ? 12 : 0, 0, 10) };
            if (level > 0) { paragraph.FontSize = level == 1 ? 21 : 17; paragraph.FontWeight = FontWeights.SemiBold; }
            document.Blocks.Add(paragraph);
        }
        NoticeReader.Document = document;
    }

    private void LanguageSelect_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_languageSelectorReady || LanguageSelect.SelectedValue is not string languageCode)
            return;

        var updateDefaultDeviceName = string.Equals(
            DisplayNameBox.Text,
            _localizer["Device.DefaultName"],
            StringComparison.CurrentCulture);
        try
        {
            _localizer.SetLanguage(languageCode);
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                _localizer.Format("Language.SaveFailed", exception.Message),
                _localizer["Language.SaveFailedTitle"],
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
        }

        if (updateDefaultDeviceName)
            DisplayNameBox.Text = _localizer["Device.DefaultName"];

        RefreshLocalizedRuntimeText();
    }

    private void RefreshLocalizedRuntimeText()
    {
        SetDeviceHeader(_deviceStatusKey);
        if (_resolution is not null)
            PopulateDiagnostics(_resolution);

        if (_connectionValidationKeys.Length > 0)
            ConnectionValidationText.Text = string.Join(
                Environment.NewLine,
                _connectionValidationKeys.Select(key => _localizer[key]));
        else if (!string.IsNullOrWhiteSpace(_connectionRuntimeMessage))
            ConnectionValidationText.Text = LocalizeRuntimeMessage(_connectionRuntimeMessage);

        ConnectionValidationText.Foreground = _connectionRuntimeSucceeded
            ? new SolidColorBrush(Color.FromRgb(6, 118, 71))
            : FindResource("DangerBrush") as Brush;

        if (_deploymentCompleted)
            DeployButton.Content = _localizer["Action.OpenConsole"];

        if (TailscaleOptionsPanel.Visibility == Visibility.Visible)
            RefreshWindowsTailscaleStatus();

        if (HomePanel.Visibility == Visibility.Visible)
            ShowConnected();
        else if (OfflinePanel.Visibility == Visibility.Visible)
            ShowOffline();
        else if (WizardPanel.Visibility == Visibility.Visible)
            ShowWizard(_wizardStep);
        else if (DiagnosticsPanel.Visibility == Visibility.Visible)
            ShowDiagnostics();
        else if (NoticesPanel.Visibility == Visibility.Visible)
            ShowNotices();
        else if (PrivacyPanel.Visibility == Visibility.Visible)
            ShowPrivacy();
        else if (!_busy)
            SetHeader(_localizer[_busyStatusKey ?? "Status.Initializing"],
                "#174D8C", "#EEF6FF", "#A8C4E6");

        if (_busy && !string.IsNullOrWhiteSpace(_busyStatusKey))
            SetHeader(_localizer[_busyStatusKey], "#174D8C", "#EEF6FF", "#A8C4E6");
    }

    private string LocalizeRuntimeMessage(string? message) =>
        RuntimeMessageLocalizer.Translate(_localizer, message);

    private void MinimizeWindow_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void MaximizeWindow_Click(object sender, RoutedEventArgs e)
    {
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
    }
    private void CloseWindow_Click(object sender, RoutedEventArgs e) => Close();
    private void Window_StateChanged(object? sender, EventArgs e)
    {
        if (WindowLayout is null) return;
        WindowLayout.Margin = WindowState == WindowState.Maximized ? new Thickness(8) : new Thickness(0);
        MaximizeButton.Content = WindowState == WindowState.Maximized ? "\uE923" : "\uE922";
    }

    protected override void OnClosed(EventArgs e)
    {
        _httpClient.Dispose();
        base.OnClosed(e);
    }

    private sealed record DiagnosticRow(string Label, string Address, string Result, string Duration);

    private enum WorkflowMode
    {
        FirstDeployment,
        DeviceSettings,
        Repair,
    }

    private enum NavigationSection
    {
        Dashboard,
        DeviceSettings,
        Diagnostics,
        Repair,
        Notices,
        Privacy,
    }
}
