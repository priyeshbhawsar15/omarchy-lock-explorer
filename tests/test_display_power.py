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
