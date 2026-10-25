import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, call

spec = importlib.util.spec_from_file_location('power', Path(__file__).parents[1] / 'display-power.py')
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)


class PowerTests(unittest.TestCase):
    def test_hardware_off_persists_wake_addresses_before_cutting_ddc(self):
        config = {'main': 'DP-6', 'sides': ['DP-5', 'DP-4'], 'mainTint': 100, 'sideTint': 100,
                  'ddcPowerOffMonitors': ['DP-5', 'DP-4']}
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'power.json'
            off = []
            def fake_run(*args):
                if args[0] == 'ddcutil':
                    self.assertEqual(args[3:], ('--skip-ddc-checks', '--noverify', 'setvcp', 'D6', '5'))
                    saved = json.loads(state.read_text())
                    self.assertIn(args[2], saved.values())
                    off.append(args[2])
                return ''
            with patch.object(power, 'buses', return_value={'DP-4': '14', 'DP-5': '15'}), patch.object(power, 'run', side_effect=fake_run):
                power.apply_policy(config, 'sides', state)
            self.assertEqual(off, ['15', '14'])
            self.assertEqual(json.loads(state.read_text()), {'DP-5': '15', 'DP-4': '14'})

    def test_hardware_wake_uses_saved_buses_without_probing_off_monitors(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'brightness.json'
            hardware = Path(directory) / 'power.json'
            hardware.write_text('{"DP-5":"15","DP-4":"14"}')
            modes = {'15': 5, '14': 5}
            def fake_run(*args):
                if args[0] == 'hyprctl':
                    return ''
                bus = args[2]
                if 'setvcp' in args:
                    self.assertEqual(args[3:], ('--skip-ddc-checks', '--noverify', 'setvcp', 'D6', '1'))
                    modes[bus] = 1
                    return ''
                return 'VCP D6 SNC x%02x' % modes[bus]
            with patch.object(power, 'buses', side_effect=AssertionError('must not probe powered-off displays')), patch.object(power, 'run', side_effect=fake_run):
                power.apply('wake', 'DP-6', ['DP-5', 'DP-4'], state)
            self.assertEqual(modes, {'15': 1, '14': 1})
            self.assertFalse(hardware.exists())

    def test_failed_hardware_wake_retains_only_failed_output_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'brightness.json'
            hardware = Path(directory) / 'power.json'
            hardware.write_text('{"DP-5":"15","DP-4":"14"}')
            def fake_run(*args):
                if args[0] == 'ddcutil' and args[2] == '15':
                    raise subprocess.CalledProcessError(1, args)
                return 'VCP D6 SNC x01' if 'getvcp' in args else ''
            with patch.object(power, 'run', side_effect=fake_run), patch('sys.stderr'):
                power.apply('wake', 'DP-6', ['DP-5', 'DP-4'], state)
                # Failed legacy DDC recovery must not keep Service.qml's wake
                # barrier pending and prevent the next main/side deadline.
                power.apply_policy({'main': 'DP-6', 'sides': [], 'mainTint': 100, 'sideTint': 100}, 'main')
            self.assertEqual(json.loads(hardware.read_text()), {'DP-5': '15'})

    def test_hardware_off_failure_still_blanks_and_attempts_other_output(self):
        config = {'main': 'DP-6', 'sides': ['DP-5', 'DP-4'], 'mainTint': 100, 'sideTint': 100,
                  'ddcPowerOffMonitors': ['DP-5', 'DP-4']}
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'power.json'
            attempted = []
            def fake_run(*args):
                attempted.append(args)
                if args[0] == 'ddcutil' and args[2] == '15':
                    raise subprocess.CalledProcessError(1, args)
                return ''
            with patch.object(power, 'buses', return_value={'DP-5': '15', 'DP-4': '14'}), patch.object(power, 'run', side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, 'DP-5'):
                    power.apply_policy(config, 'sides', state)
            self.assertEqual(sum(a[0] == 'hyprctl' for a in attempted), 2)
            self.assertIn(('ddcutil', '--bus', '14', '--skip-ddc-checks', '--noverify', 'setvcp', 'D6', '5'), attempted)
            self.assertEqual(json.loads(state.read_text()), {'DP-5': '15', 'DP-4': '14'})
            # Persist-before-write must not suppress retries after an uncertain
            # failure; powered-off buses cannot be rediscovered by probing.
            with patch.object(power, 'buses', side_effect=AssertionError('must reuse saved buses')), patch.object(power, 'run') as retry:
                power.apply_policy(config, 'sides', state)
            self.assertEqual([c.args[2] for c in retry.call_args_list if c.args[0] == 'ddcutil'], ['15', '14'])

    def test_policy_powers_off_only_expired_groups_at_100_percent(self):
        config = {'main': 'DP-6', 'sides': ['DP-5', 'DP-4'], 'mainTint': 40, 'sideTint': 100}
        with patch.object(power, 'run') as run:
            power.apply_policy(config, 'main')
            run.assert_not_called()
            power.apply_policy(config, 'sides')
            self.assertEqual(run.call_args_list, [
                call('hyprctl', 'dispatch', 'hl.dsp.dpms({ action = "disable", monitor = "DP-5" })'),
                call('hyprctl', 'dispatch', 'hl.dsp.dpms({ action = "disable", monitor = "DP-4" })')])

    def test_policy_partial_tint_does_not_change_hardware_brightness(self):
        with patch.object(power, 'run') as run:
            power.apply_policy({'main': 'DP-6', 'sides': ['DP-5'], 'mainTint': 0, 'sideTint': 90}, 'both')
            run.assert_not_called()

    def test_failed_dpms_still_attempts_other_side(self):
        with patch.object(power, 'run', side_effect=[subprocess.TimeoutExpired('hyprctl', 20), '']) as run:
            with self.assertRaisesRegex(RuntimeError, 'DP-5'):
                power.apply_policy({'main': 'DP-6', 'sides': ['DP-5', 'DP-4'], 'mainTint': 100, 'sideTint': 100}, 'sides')
            self.assertEqual(len(run.call_args_list), 2)

    def test_dpms_only_main_deadline_does_not_depend_on_side_hardware(self):
        config = {'main': 'DP-6', 'sides': ['DP-5', 'DP-4'],
                  'mainTint': 100, 'sideTint': 100, 'ddcPowerOffMonitors': []}
        with patch.object(power, 'buses', side_effect=AssertionError('DDC must not run')), patch.object(power, 'run') as run:
            power.apply_policy(config, 'main')
        run.assert_called_once_with('hyprctl', 'dispatch', 'hl.dsp.dpms({ action = "disable", monitor = "DP-6" })')

    def test_reconcile_only_reasserts_expired_awake_enabled_outputs(self):
        config = {'main': 'DP-6', 'sides': ['DP-5', 'DP-4'],
                  'mainTint': 100, 'sideTint': 100, 'ddcPowerOffMonitors': []}
        scenarios = [
            ('both', [{'name': 'DP-6', 'dpmsStatus': False}, {'name': 'DP-5', 'dpmsStatus': True}], ['DP-5']),
            ('main', [{'name': 'DP-6', 'dpmsStatus': True}, {'name': 'DP-5', 'dpmsStatus': True}], ['DP-6']),
            ('both', [{'name': 'DP-6', 'dpmsStatus': True}, {'name': 'DP-5', 'disabled': True, 'dpmsStatus': True}], ['DP-6']),
            ('sides', [{'name': 'DP-6', 'dpmsStatus': True}, {'name': 'DP-4', 'dpmsStatus': False}], []),
        ]
        for phase, monitors, expected in scenarios:
            with self.subTest(phase=phase, monitors=monitors):
                def fake_run(*args):
                    return json.dumps(monitors) if args[1] == '-j' else 'ok'
                with patch.object(power, 'run', side_effect=fake_run) as run:
                    power.reconcile_policy(config, phase)
                commands = [c.args[2] for c in run.call_args_list if c.args[1] == 'dispatch']
                self.assertEqual(commands, ['hl.dsp.dpms({ action = "disable", monitor = ' + json.dumps(name) + ' })' for name in expected])
        self.assertEqual(config['sides'], ['DP-5', 'DP-4'])

    def test_main_and_sides_can_both_power_off(self):
        with patch.object(power, 'run') as run:
            power.apply_policy({'main': 'DP-6', 'sides': ['DP-5', 'DP-4'], 'mainTint': 100, 'sideTint': 100}, 'both')
            self.assertEqual(len(run.call_args_list), 3)

    def test_connector_mapping_skips_invalid(self):
        text = 'Display 1\n I2C bus: /dev/i2c-14\n DRM connector: card2-DP-4\n\nInvalid display\n I2C bus: /dev/i2c-18\n DRM connector: card2-DP-4\n\nDisplay 2\n I2C bus: /dev/i2c-16\n DRM connector: card2-DP-6\n'
        with patch.object(power, 'run', return_value=text):
            self.assertEqual(power.buses(), {'DP-4': '14', 'DP-6': '16'})

    def test_invalid_detection_falls_back_to_working_brightness_bus(self):
        text = 'Invalid display\n I2C bus: /dev/i2c-18\n DRM connector: card2-DP-4\n\nInvalid display\n I2C bus: /dev/i2c-14\n DRM connector: card2-DP-4\n\nInvalid display\n I2C bus: /dev/i2c-16\n DRM connector: card2-DP-6\n'
        with patch.object(power, 'run', return_value=text), patch.object(power, 'brightness', side_effect=[ValueError('bad bus'), 100, 100]):
            self.assertEqual(power.buses(), {'DP-4': '14', 'DP-6': '16'})

    def test_off_only_main(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'run') as run:
            power.apply('off', 'DP-5', ['DP-4', 'DP-6'], Path(directory) / 'state')
            run.assert_called_once_with('hyprctl', 'dispatch', 'hl.dsp.dpms({ action = "disable", monitor = "DP-5" })')

    def test_both_dim_to_zero_and_restore_independent_values(self):
        values = {'14': 73, '16': 91}

        def fake_run(*args):
            if args[0] == 'hyprctl':
                return ''
            bus = args[2]
            if args[3] == 'getvcp':
                return f'VCP 10 C {values[bus]} 100'
            values[bus] = int(args[5])
            return ''

        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={'DP-4': '14', 'DP-6': '16'}), patch.object(power, 'run', side_effect=fake_run) as run:
            state = Path(directory) / 'state'
            power.apply('dim', 'DP-5', ['DP-4', 'DP-6'], state)
            self.assertEqual(values, {'14': 0, '16': 0})
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 73, 'DP-6': 91})
            power.apply('dim', 'DP-5', ['DP-4', 'DP-6'], state)
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 73, 'DP-6': 91})
            power.apply('wake', 'DP-5', ['DP-4', 'DP-6'], state)
            self.assertEqual(values, {'14': 73, '16': 91})
            self.assertFalse(state.exists())
            self.assertIn(call('ddcutil', '--bus', '14', 'setvcp', '10', '0'), run.call_args_list)
            self.assertIn(call('ddcutil', '--bus', '16', 'setvcp', '10', '0'), run.call_args_list)

    def test_missing_output_retains_restore_state_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={}), patch.object(power, 'run'):
            state = Path(directory) / 'state'
            state.write_text('{"DP-4": 73}')
            with self.assertRaisesRegex(RuntimeError, 'DP-4'):
                power.apply('wake', 'DP-5', ['DP-4'], state)
            self.assertTrue(state.exists())

    def test_first_monitor_failure_still_attempts_second(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={'DP-4': '14', 'DP-6': '16'}), patch.object(power, 'brightness', return_value=100), patch.object(power, 'set_brightness', side_effect=[subprocess.TimeoutExpired('ddcutil', 20), None]) as set_value:
            state = Path(directory) / 'state'
            with self.assertRaisesRegex(RuntimeError, 'DP-4'):
                power.apply('dim', 'DP-5', ['DP-4', 'DP-6'], state)
            self.assertEqual(set_value.call_args_list, [call('14', 0), call('16', 0)])
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 100, 'DP-6': 100})

    def test_readback_mismatch_is_not_success(self):
        with patch.object(power, 'run'), patch.object(power, 'brightness', return_value=10):
            with self.assertRaisesRegex(ValueError, 'expected 0'):
                power.set_brightness('14', 0)

    def test_persistent_restore_after_fresh_process(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'brightness.json'
            with patch.object(power, 'buses', return_value={'DP-4': '14', 'DP-6': '16'}), patch.object(power, 'brightness', side_effect=[73, 91]), patch.object(power, 'set_brightness'):
                power.apply('dim', 'DP-5', ['DP-4', 'DP-6'], state)
            fresh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fresh)
            with patch.object(fresh, 'buses', return_value={'DP-4': '14', 'DP-6': '16'}), patch.object(fresh, 'run'), patch.object(fresh, 'set_brightness') as restore:
                fresh.apply('wake', 'DP-5', ['DP-4', 'DP-6'], state)
                self.assertEqual(restore.call_args_list, [call('14', 73), call('16', 91)])
                self.assertFalse(state.exists())

    def test_runtime_state_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'persistent.json'
            legacy = Path(directory) / 'legacy.json'
            legacy.write_text('{"DP-4": 73}')
            power.migrate_state(state, legacy)
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 73})
            self.assertFalse(legacy.exists())
            self.assertFalse(state.with_suffix('.tmp').exists())

    def test_migration_never_overwrites_existing_restore_values(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'persistent.json'
            legacy = Path(directory) / 'legacy.json'
            state.write_text('{"DP-4": 73}')
            legacy.write_text('{"DP-4": 0}')
            power.migrate_state(state, legacy)
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 73})

    def test_failed_restore_preserves_values_for_next_attempt(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={'DP-4': '14'}), patch.object(power, 'run'), patch.object(power, 'set_brightness', side_effect=ValueError('readback failed')):
            state = Path(directory) / 'persistent.json'
            state.write_text('{"DP-4": 73}')
            with self.assertRaises(RuntimeError):
                power.apply('wake', 'DP-5', ['DP-4'], state)
            self.assertEqual(json.loads(state.read_text()), {'DP-4': 73})

    def test_malformed_brightness_is_not_success(self):
        with patch.object(power, 'run', return_value='invalid'):
            with self.assertRaises(ValueError):
                power.brightness('14')


if __name__ == '__main__':
    unittest.main()
