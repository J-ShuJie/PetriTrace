from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_XAML = ROOT / "desktop" / "PiCameraControl.Manager" / "App.xaml"
APP_CODE = ROOT / "desktop" / "PiCameraControl.Manager" / "App.xaml.cs"
WINDOW_CODE = ROOT / "desktop" / "PiCameraControl.Manager" / "MainWindow.xaml.cs"


class WindowsManagerActivationTests(unittest.TestCase):
    def test_application_owns_startup_and_forwards_secondary_instances(self):
        xaml = APP_XAML.read_text(encoding="utf-8")
        code = APP_CODE.read_text(encoding="utf-8")
        self.assertNotIn("StartupUri=", xaml)
        self.assertIn("new Mutex(initiallyOwned: true", code)
        self.assertIn("NamedPipeServerStream", code)
        self.assertIn("ForwardActivationAsync", code)
        self.assertIn("Shutdown();", code)
        self.assertIn('StartsWith("picameracontrol:"', code)

    def test_manage_activation_never_opens_or_manipulates_the_browser(self):
        code = WINDOW_CODE.read_text(encoding="utf-8")
        start = code.index("public async Task HandleProtocolActivationAsync")
        end = code.index("private async Task LoadAndConnectAsync", start)
        activation_handler = code[start:end]
        self.assertIn("ManagerProtocolAction.Open", activation_handler)
        self.assertIn("return;", activation_handler)
        self.assertNotIn("OpenUri", activation_handler)
        self.assertNotIn("Process.Start", activation_handler)
        self.assertIn("openBrowserWhenReady: _protocolRequest is null", code)
        self.assertIn("while (_busy)", activation_handler)

    def test_privileged_protocol_request_is_consumed_before_maintenance(self):
        code = WINDOW_CODE.read_text(encoding="utf-8")
        start = code.index("private void HandlePrivilegedProtocolRequest")
        end = code.index("private void OpenControlPanel_Click", start)
        handler = code[start:end]
        self.assertIn("_protocolRequest = null;", handler)
        self.assertIn("OpenRepairWorkflow();", handler)

    def test_settings_and_repair_have_distinct_entry_routes(self):
        code = WINDOW_CODE.read_text(encoding="utf-8")
        self.assertIn("WorkflowMode.DeviceSettings", code)
        self.assertIn("WorkflowMode.Repair", code)
        self.assertIn("ShowWizard(2);", code)
        self.assertNotIn("private void EditProfileAndOpenDeployment", code)


if __name__ == "__main__":
    unittest.main()
