import unittest
from unittest.mock import Mock
from deploy.wifi_recovery import Recovery


class FakeNetwork:
    def __init__(self):
        self.state = 30
        self.reason = '0 (none)'
        self.radio = 'enabled'
        self.visible = 'home'
        self.fail = True
        self.calls = []
        self.auto = 'yes'
        self.permissions = ''

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        if args == ('radio', 'wifi'): return self.radio
        if args == ('-t', '-f', 'DEVICE,TYPE', 'device', 'status'): return 'eth0:ethernet\nwlan0:wifi'
        if 'GENERAL.STATE' in args: return str(self.state) + ' (state)'
        if 'GENERAL.REASON' in args: return self.reason
        if 'SSID' in args: return self.visible
        if 'UUID,TYPE' in args: return 'fixture:802-11-wireless'
        fields = {'connection.autoconnect': self.auto, 'connection.permissions': self.permissions,
                  '802-11-wireless.ssid': 'home', 'connection.interface-name': '',
                  'connection.autoconnect-priority': '100'}
        if args[0] == '-g': return fields[args[1]]
        if args[:3] == ('--wait', '25', 'connection'):
            if self.fail: raise RuntimeError('authentication failed')
            self.state = 100
            return 'connected'
        raise AssertionError(args)

    @property
    def activations(self):
        return [c for c in self.calls if c[0] == '--wait']


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.network = FakeNetwork()
        self.now = 0
        self.worker = Recovery(self.network, lambda: self.now, Mock())

    def tick(self, now):
        self.now = now
        self.worker.tick()

    def test_authentication_failure_retries_saved_uuid_with_backoff(self):
        self.tick(0)
        self.tick(89)
        self.assertEqual(self.network.activations, [])
        self.tick(90)
        self.tick(149)
        self.assertEqual(len(self.network.activations), 1)
        self.tick(150)
        self.assertEqual(self.worker.retries['wlan0'].due, 270)
        self.network.fail = False
        self.tick(270)
        self.assertEqual(len(self.network.activations), 3)
        self.assertEqual(self.worker.retries, {})
        self.tick(999)
        self.assertEqual(len(self.network.activations), 3)
        self.assertEqual(self.network.activations[-1], ('--wait','25','connection','up','uuid','fixture','ifname','wlan0'))

    def test_repeated_failures_cap_at_fifteen_minutes(self):
        self.tick(0)
        for i in range(12):
            self.tick(self.worker.retries['wlan0'].due)
        self.assertEqual(self.worker.retries['wlan0'].due - self.now, 900)

    def test_connected_activating_unmanaged_and_disabled_are_untouched(self):
        for state in (10,20,40,50,60,70,80,90,100,110):
            self.network.state = state
            self.tick(0)
            self.tick(200)
        self.network.state = 30
        self.network.radio = 'disabled'
        self.tick(0)
        self.tick(200)
        self.assertEqual(self.network.activations, [])

    def test_manual_disconnect_is_respected(self):
        self.network.reason = '39 (user-requested)'
        self.tick(0)
        self.tick(200)
        self.assertEqual(self.network.activations, [])

    def test_absent_network_does_not_prompt_or_activate(self):
        self.network.visible = 'other'
        self.tick(0)
        self.tick(90)
        self.assertEqual(self.network.activations, [])
        self.network.visible = 'home'
        self.tick(150)
        self.assertEqual(len(self.network.activations), 1)

    def test_opted_out_and_session_only_profiles_are_skipped(self):
        self.network.auto = 'no'
        self.assertIsNone(self.worker.candidate('wlan0'))
        self.network.auto = 'yes'
        self.network.permissions = 'user:someone'
        self.assertIsNone(self.worker.candidate('wlan0'))


if __name__ == '__main__':
    unittest.main()
