import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
XAML = ROOT / "desktop" / "PiCameraControl.Manager" / "MainWindow.xaml"
CODE_BEHIND = ROOT / "desktop" / "PiCameraControl.Manager" / "MainWindow.xaml.cs"
CATALOG = (
    ROOT
    / "desktop"
    / "PiCameraControl.Manager.Core"
    / "Localization"
    / "LocalizationCatalog.cs"
)


class WindowsManagerLocalizationTests(unittest.TestCase):
    def test_xaml_is_well_formed_and_every_binding_key_exists(self):
        source = XAML.read_text(encoding="utf-8")
        ET.fromstring(source)

        binding_keys = set(re.findall(r"\[([A-Za-z0-9.]+)\]", source))
        catalog_keys = set(
            re.findall(r'^\s*\["([A-Za-z0-9.]+)"\]\s*=', CATALOG.read_text(encoding="utf-8"), re.MULTILINE)
        )
        self.assertGreater(len(binding_keys), 90)
        self.assertFalse(binding_keys - catalog_keys)

    def test_only_native_language_name_is_a_literal_chinese_xaml_label(self):
        source = XAML.read_text(encoding="utf-8")
        chinese_literals = re.findall(r'="([^"{]*[\u3400-\u9fff][^"]*)"', source)
        self.assertEqual(["简体中文"], chinese_literals)

    def test_code_behind_does_not_embed_user_facing_chinese(self):
        source = CODE_BEHIND.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", source))
        self.assertNotIn('MessageBox.Show("', source)

    def test_accessibility_text_uses_localized_bindings(self):
        source = XAML.read_text(encoding="utf-8")
        properties = re.findall(r'AutomationProperties\.(?:Name|HelpText)="([^"]+)"', source)
        self.assertGreaterEqual(len(properties), 5)
        self.assertTrue(all(value.startswith("{Binding [") for value in properties))

    def test_configured_manager_uses_sidebar_and_has_no_global_footer(self):
        xaml = XAML.read_text(encoding="utf-8")
        code = CODE_BEHIND.read_text(encoding="utf-8")
        self.assertIn('x:Name="NavigationPane"', xaml)
        for name in (
            "DashboardNavButton",
            "DeviceSettingsNavButton",
            "DiagnosticsNavButton",
            "RepairNavButton",
            "NoticesNavButton",
            "PrivacyNavButton",
        ):
            self.assertIn(f'x:Name="{name}"', xaml)
        self.assertNotIn("Footer.Privacy", xaml)
        self.assertIn('Text="{Binding [Home.CloseDoesNotStop]}"', xaml)
        self.assertIn("SetNavigation(NavigationSection.Dashboard)", code)
        self.assertIn("showPane: !isFirstDeployment", code)

    def test_removed_explanations_are_not_present_in_the_catalog(self):
        catalog = CATALOG.read_text(encoding="utf-8")
        self.assertNotIn("Home.CoreHealthy", catalog)
        self.assertNotIn("Home.HealthChecked", catalog)
        self.assertNotIn("Home.MaintenanceDetail", catalog)
        self.assertNotIn("Footer.Privacy", catalog)


if __name__ == "__main__":
    unittest.main()
