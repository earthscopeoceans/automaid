"""Scientific eligibility and serialization checks using independent read-back."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
from obspy import UTCDateTime, read

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cycles import Cycle
from events import Event
from geocsv import GeoCSV
import gps

EPOCH = UTCDateTime('2024-01-01')


def make_fix(seconds, longitude, drift=0, frequency=3686333):
    return gps.GPS(
        EPOCH + seconds, -10, longitude, clockdrift=drift,
        clockfreq=frequency, source='synthetic.MER',
        rawstr_dict={'latitude': '-1000.0000', 'longitude': '-15100.0000'})


def make_event(pressure=1500, trigger=2000):
    trigger_fields = '' if trigger is None else f' TRIG={trigger} PRESSURE={pressure}.00'
    header = (
        f' DATE=2024-01-01T00:08:20.000000 STAGES=5{trigger_fields}'
        ' TEMPERATURE=4 CRITERION=0.5 SNR=2.0'
    ).encode()
    with contextlib.redirect_stdout(io.StringIO()):
        event = Event('synthetic.MER', header, b'original payload')
    event.kstnm = 'P9999'
    event.kinst = '452.020'
    event.mer_environment_name = 'acquisition.MER'
    event.measured_fs = 40.014
    event.decimated_fs = 20.007
    event.kcmpnm = 'BDH'
    event.uncorrected_starttime = EPOCH + 400
    event.normalized = event.edges_correction = '1'
    event.processed_data = np.random.default_rng(0).integers(
        -100000, 100000, size=20000, dtype=np.int32)
    return event


def make_cycle(pressure=1500):
    cycle = Cycle()
    cycle.cycle_name = '0001_SYNTHETIC.CYCLE'
    cycle.directory_name = '0001_complete'
    cycle.kstnm = 'P9999'
    cycle.gps_before_dive = [make_fix(-600, -151.0015), make_fix(-100, -151.001)]
    cycle.gps_after_dive = [make_fix(1100, -151, -.8), make_fix(1700, -150.9995)]
    cycle.gps_sync_before_dive = cycle.gps_before_dive.copy()
    cycle.gps_sync_after_dive = cycle.gps_after_dive.copy()
    cycle.gps_list = cycle.gps_before_dive + cycle.gps_after_dive
    cycle.descent_leave_surface_date = EPOCH
    cycle.ascent_reach_surface_date = EPOCH + 1000
    cycle.pressure_mbar = [
        ('1000', EPOCH + 10), ('9000', EPOCH + 100),
        ('9000', EPOCH + 900), ('1000', EPOCH + 990)]
    cycle.emergency_triggers = []
    cycle.events = [make_event(pressure)]
    cycle.logs = [SimpleNamespace(events=cycle.events, log_name='synthetic.LOG')]
    return cycle


def calculate(cycle):
    with contextlib.redirect_stdout(io.StringIO()):
        cycle.validate_gps(2, 5400)
        cycle.correct_clockdrifts()
        cycle.set_processed_file_names()
        cycle.compute_station_locations(50)
        cycle.set_events_obspy_trace_stats()


class ScientificEligibilityTests(unittest.TestCase):
    def test_signed_clock_boundaries_on_both_anchors(self):
        for side in ('before', 'after'):
            for drift, eligible in ((-90, False), (-10, False), (-9.999999, True),
                                    (-5, True), (0, True), (5, True), (6.999970, True),
                                    (9.999999, True), (10, False), (90, False)):
                with self.subTest(side=side, drift=drift):
                    cycle = make_cycle()
                    anchor = (cycle.gps_sync_before_dive[-1] if side == 'before'
                              else cycle.gps_sync_after_dive[0])
                    anchor.clockdrift = drift
                    with contextlib.redirect_stdout(io.StringIO()):
                        cycle.validate_gps()
                    self.assertEqual(cycle.gps_valid4clockdrift_correction, eligible)

    def test_nonanchor_clock_metadata_does_not_filter_position_inputs(self):
        for frequency, drift in ((0, -90), (-1, 0), (None, None),
                                 (float('nan'), float('nan'))):
            with self.subTest(frequency=frequency, drift=drift):
                cycle = make_cycle()
                fix = make_fix(-700, -151.02, drift=drift, frequency=frequency)
                # Deliberately unsorted: interpolation must not reorder the source.
                cycle.gps_before_dive.insert(1, fix)
                cycle.gps_list.insert(1, fix)
                before = cycle.gps_before_dive.copy()
                state = fix.__dict__.copy()
                calculate(cycle)
                self.assertTrue(cycle.gps_valid4location_interp)
                self.assertEqual(cycle.gps_before_dive, before)
                self.assertEqual(fix.__dict__, state)
                self.assertEqual(cycle.rejected_gps, [])
                # The -700 s fix and -100 s anchor set this extrapolation.
                expected = -151.001 + (-151.001 - -151.02) * 100 / 600
                self.assertAlmostEqual(cycle.descent_leave_surface_loc.longitude, expected)

    def test_invalid_anchor_is_not_replaced_by_later_valid_sync(self):
        cycle = make_cycle()
        cycle.gps_after_dive[0].clockfreq = 0
        calculate(cycle)
        self.assertFalse(cycle.gps_valid4clockdrift_correction)
        self.assertIsNone(cycle.events[0].corrected_starttime)
        self.assertIsNone(cycle.events[0].obspy_trace_stats)

    def test_missing_clock_metadata_and_cycle_isolation(self):
        good = make_cycle()
        bad = make_cycle()
        for fix in bad.gps_before_dive:
            fix.clockfreq = None
        calculate(good)
        calculate(bad)
        self.assertTrue(good.gps_valid4location_interp)
        self.assertFalse(bad.gps_valid4location_interp)
        self.assertEqual(len(bad.gps_before_dive), 2)
        self.assertIsNone(bad.events[0].station_loc)

    def test_position_count_uses_original_synchronization_entries(self):
        cycle = make_cycle()
        cycle.gps_sync_before_dive = cycle.gps_sync_before_dive[-1:]
        # A second position lacking clock metadata does not add a sync entry.
        cycle.gps_before_dive[0].clockfreq = None
        calculate(cycle)
        self.assertTrue(cycle.gps_valid4clockdrift_correction)
        self.assertFalse(cycle.gps_valid4location_interp)
        self.assertEqual(cycle.gps_exclusion_reasons,
                         ['insufficient_pre_dive_position_fixes'])

    def test_revalidation_clears_stale_derived_values(self):
        cycle = make_cycle()
        calculate(cycle)
        event = cycle.events[0]
        data = event.processed_data
        uncorrected_start = event.uncorrected_starttime
        self.assertIsNotNone(event.obspy_trace_stats)
        cycle.gps_after_dive[0].clockdrift = -10
        calculate(cycle)
        self.assertIsNone(event.obspy_trace_stats)
        self.assertIsNone(event.station_loc)
        self.assertIsNone(cycle.descent_leave_surface_layer_loc)
        self.assertIs(event.processed_data, data)
        self.assertEqual(event.uncorrected_starttime, uncorrected_start)

    def test_clock_anchors_require_finite_clock_fields(self):
        valid = make_fix(0, -151)
        for field, value in (('clockfreq', 0), ('clockfreq', -1),
                             ('clockfreq', None), ('clockfreq', float('nan')),
                             ('clockdrift', None), ('clockdrift', float('inf'))):
            with self.subTest(field=field):
                fix = copy.deepcopy(valid)
                setattr(fix, field, value)
                self.assertTrue(gps.clock_anchor_rejection_reasons(fix))
        self.assertEqual(gps.clock_anchor_rejection_reasons(valid), [])

    def test_zero_pressure_withheld_from_files_and_all_geocsv_variants(self):
        cycle = make_cycle()
        calculate(cycle)
        event = cycle.events[0]
        event.pressure_dbar = event.pressure_mbar = event.depth = 0
        event.mer_binary_header = event.mer_binary_header.replace(b'PRESSURE=1500.00', b'PRESSURE=0.00')
        # Existing Stats intentionally remain present to check saved-input guards.
        with tempfile.TemporaryDirectory() as temporary:
            event.write_mseed(temporary + '/')
            event.write_sac(temporary + '/')
            self.assertFalse(list(Path(temporary).glob('*.mseed')))
            self.assertFalse(list(Path(temporary).glob('*.sac')))
            with contextlib.redirect_stdout(io.StringIO()):
                GeoCSV('452.020-P-9999', [cycle],
                       '2024-01-02T00:00:00.000000Z', 50).write(temporary + '/geo.csv')
            for path in Path(temporary).glob('geo_*.csv'):
                with path.open() as handle:
                    rows = list(csv.DictReader(line for line in handle if not line.startswith('#')))
                self.assertFalse(any(row['type'] == 'waveform' for row in rows))
            excluded = [json.loads(line) for line in
                        (Path(temporary) / 'excluded-waveforms.jsonl').read_text().splitlines()]
            self.assertEqual(len(excluded), 1)
            self.assertEqual(excluded[0]['reasons'], ['zero_receiver_depth_pending_review'])
            self.assertEqual(excluded[0]['source_pressure_dbar'], '0.00')
            self.assertEqual(excluded[0]['source_mer'], 'synthetic.MER')
            event.set_obspy_trace_stats()
            self.assertIsNone(event.obspy_trace_stats)

    def test_zero_trigger_uses_det_filename(self):
        event = make_event(trigger=0)
        event.corrected_starttime = EPOCH
        event.set_processed_file_name()
        self.assertFalse(event.is_requested)
        self.assertTrue(event.processed_file_name.endswith('.DET.WLT5'))

    def test_requested_waveform_without_pressure_remains_exportable(self):
        cycle = make_cycle()
        event = make_event(trigger=None)
        cycle.events = [event]
        cycle.logs[0].events = cycle.events
        calculate(cycle)
        self.assertTrue(event.is_requested)
        self.assertIsNone(event.pressure_mbar)
        self.assertIsNone(event.waveform_exclusion_reason())
        with tempfile.TemporaryDirectory() as temporary:
            event.write_sac(temporary + '/')
            event.write_mseed(temporary + '/')
            self.assertEqual(len(list(Path(temporary).glob('*.sac'))), 1)
            self.assertEqual(len(list(Path(temporary).glob('*.mseed'))), 1)
            with contextlib.redirect_stdout(io.StringIO()):
                GeoCSV('452.020-P-9999', [cycle],
                       '2024-01-02T00:00:00.000000Z', 50).write(temporary + '/geo.csv')
            with (Path(temporary) / 'geo_REQ.csv').open() as handle:
                rows = list(csv.DictReader(line for line in handle if not line.startswith('#')))
            waveforms = [row for row in rows if row['type'] == 'waveform']
            self.assertEqual(len(waveforms), 1)
            self.assertEqual(waveforms[0]['measured_pressure'], '')

    def test_gps_writer_preserves_missing_source_values(self):
        fix = make_fix(0, -151)
        fix.hdop = fix.vdop = fix.clockdrift = fix.clockfreq = fix.mseed_time_delay = None
        before = copy.deepcopy(fix.__dict__)
        cycle = SimpleNamespace(gps_list=[fix])
        with tempfile.TemporaryDirectory() as temporary:
            gps.write_gps([cycle], '2024-01-01T00:00:00Z', temporary, '')
            self.assertIn('nan,nan,nan,nan', (Path(temporary) / 'gps.csv').read_text())
        self.assertEqual(fix.__dict__, before)

    def test_antimeridian_and_retained_anchor_epoch(self):
        for first, last in ((179.8, -179.8), (-179.8, 179.8)):
            result = gps.linear_interpolation(
                [make_fix(0, first), make_fix(1000, last)], EPOCH + 500)
            self.assertEqual(abs(result.longitude), 180)
        result = gps.linear_interpolation(
            [make_fix(0, -151), make_fix(1000, -150.99999)], EPOCH + 500)
        self.assertEqual(result.date, EPOCH)
        self.assertEqual(result.longitude, -151)

    def test_valid_waveform_serialization_and_every_record_clock_history(self):
        cycle = make_cycle()
        calculate(cycle)
        event = cycle.events[0]
        before_stats = copy.deepcopy(event.obspy_trace_stats)
        with tempfile.TemporaryDirectory() as temporary:
            event.write_mseed(temporary + '/')
            event.write_sac(temporary + '/')
            mini_path = Path(temporary, event.processed_file_name + '.mseed')
            sac_path = mini_path.with_suffix('.sac')
            mini, = read(str(mini_path), format='MSEED', apply_calib=False)
            sac, = read(str(sac_path), format='SAC', apply_calib=False)
            np.testing.assert_array_equal(mini.data, event.processed_data)
            np.testing.assert_array_equal(sac.data, mini.data.astype(np.float32))
            self.assertLessEqual(abs(mini.stats.starttime.ns - sac.stats.starttime.ns), 1000)
            content = mini_path.read_bytes()
            link = struct.unpack_from('>H', content, 46)[0]
            while struct.unpack_from('>H', content, link)[0] != 1000:
                link = struct.unpack_from('>H', content, link + 2)[0]
            record_length = 1 << content[link + 6]
            self.assertGreater(len(content), record_length)
            for offset in range(0, len(content), record_length):
                self.assertTrue(content[offset + 36] & 2)
                self.assertEqual(struct.unpack_from('>i', content, offset + 40)[0], -3333)
        self.assertEqual(event.obspy_trace_stats, before_stats)


if __name__ == '__main__':
    unittest.main()
