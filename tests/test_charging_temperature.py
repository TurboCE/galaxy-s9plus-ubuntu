# SPDX-License-Identifier: GPL-2.0-only
"""Calibration units and fault rejection; C integer division is the oracle."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('temperature', ROOT/'experiments/charging/temperature.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class TemperatureTests(unittest.TestCase):
    def test_all_interpolated_values_against_c_division(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        # Samsung sec_adc.c interpolation expression, including signed division.
        program = '''#include <stdio.h>
int main(void) { int a[]={%s};
for(int i=0;i<22;i++)for(int raw=a[i];raw<a[i+1];raw++) {
int upper=900-i*50, lower=upper-50;
printf("%%d %%d\\n",raw,upper+((lower-upper)*(raw-a[i]))/(a[i+1]-a[i]));
} return 0;}''' % ','.join(map(str,t.ADC))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'oracle.c'; binary=Path(directory)/'oracle'
            source.write_text(program)
            subprocess.run([cc, '-Wall', '-Werror', str(source), '-o', str(binary)], check=True)
            for line in subprocess.check_output([str(binary)],text=True).splitlines():
                raw, expected=map(int,line.split())
                self.assertEqual(t.convert(raw), expected)
        self.assertEqual(t.convert(3678), -200)

    def test_invalid_sensor_never_clamped(self):
        for raw in (0, 274, 3679, 4095, -1, None, True, 1474.0):
            with self.assertRaises(ValueError):
                t.convert(raw)

    def rows(self):
        return [{'monotonic_ns': 1000000000+i*200000000,
                 '1': value, '3': value, '4': value}
                for i,value in enumerate((275,1474,1475,1476,3678))]

    def test_trimmed_mean_and_invalid_outlier(self):
        rows=self.rows()
        self.assertEqual(t.summarize(rows)['battery']['trimmed_adc'],1475)
        rows[0]['4']=0
        with self.assertRaises(ValueError): t.summarize(rows)

    def test_capture_freshness_and_completeness(self):
        with self.assertRaises(ValueError): t.summarize(self.rows()[:4])
        for value in (0,1000000000,10000000000):
            rows=self.rows();rows[-1]['monotonic_ns']=value
            with self.assertRaises(ValueError): t.summarize(rows)


if __name__ == '__main__': unittest.main()
