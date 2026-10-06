import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('power', Path(__file__).parents[1] / 'display-power.py')
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)


class PowerTests(unittest.TestCase):
    def test_connector_mapping_skips_invalid(self):
        text = 'Display 1\n I2C bus: /dev/i2c-14\n DRM connector: card2-DP-4\n\nInvalid display\n I2C bus: /dev/i2c-18\n DRM connector: card2-DP-4\n'
        with patch.object(power, 'run', return_value=text):
            self.assertEqual(power.buses(), {'DP-4': '14'})

    def test_off_only_main(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'run') as run:
            power.apply('off', 'DP-5', ['DP-4', 'DP-6'], Path(directory) / 'state')
            run.assert_called_once_with('hyprctl', 'dispatch', 'hl.dsp.dpms({ action = "disable", monitor = "DP-5" })')

    def test_dim_restore_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={'DP-4': '14'}), patch.object(power, 'run', return_value='VCP 10 C 73 100') as run:
            state = Path(directory) / 'state'
            power.apply('dim', 'DP-5', ['DP-4'], state)
            self.assertEqual(state.read_text(), '{"DP-4": 73}')
            power.apply('dim', 'DP-5', ['DP-4'], state)
            self.assertEqual(sum(call.args[3] == 'getvcp' for call in run.call_args_list), 1)
            power.apply('wake', 'DP-5', ['DP-4'], state)
            self.assertFalse(state.exists())
            self.assertIn(unittest.mock.call('ddcutil', '--bus', '14', 'setvcp', '10', '73'), run.call_args_list)

    def test_missing_output_retains_restore_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(power, 'buses', return_value={}), patch.object(power, 'run'):
            state = Path(directory) / 'state'
            state.write_text('{"DP-4": 73}')
            power.apply('wake', 'DP-5', ['DP-4'], state)
            self.assertTrue(state.exists())


if __name__ == '__main__':
    unittest.main()
