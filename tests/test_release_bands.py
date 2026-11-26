import pytest

from kilnboard.probe_windows.contracts import Disposition, Scenario
from kilnboard.probe_windows.domain import interpret
from kilnboard.probe_windows.service import draft
from kilnboard.settings import (BAND_MIN_REPLAY, DEFAULT_BUDGET, moisture_ceiling)
from kilnboard.stack_backcheck.bands import releases, release_bands
from kilnboard.stack_backcheck.contracts import ValidationPoint
from kilnboard.stack_disposition.briefing import summarize
from kilnboard.stack_disposition.service import manifest
from kilnboard.process import preview


THICK, THIN = 26.0, 20.0   # 26mm 起走 12.4，以下走 11.6


def sample(key, region, error, thickness=THIN, level=3, volume=10.5, confirmed=True):
    """构造一条回放/校准点：预测 volume，实测 volume+error。"""
    return ValidationPoint(key, region, 1, volume, volume + error, confirmed, thickness, level)


def calibration(region, error, count=12):
    return [sample(f'{region}-c{i}', region, error) for i in range(count)]


def fixture_bands():
    """A：本舱更紧且回放证实少排复测、不多放湿板 → 放宽。
    B：本舱更紧但回放出现额外湿板误放 → 退回全厂口径。
    D：本舱更紧但回放实测太少 → 退回全厂口径。
    """
    cal = (calibration('A', .4) + calibration('B', .6)
           + calibration('C', 3.0) + calibration('D', .5))
    replay = (tuple(sample(f'A-r{i}', 'A', .0) for i in range(12))
              + tuple(sample(f'B-r{i}', 'B', 1.4 if i == 0 else .0) for i in range(12))
              + tuple(sample(f'C-r{i}', 'C', .0) for i in range(12))
              + tuple(sample(f'D-r{i}', 'D', .0) for i in range(BAND_MIN_REPLAY - 5)))
    return release_bands(3.0, cal, replay)


def test_plant_radius_all_over_and_low_sample_is_untrusted():
    bands = release_bands(3.0, [], [])
    assert bands['plant'].trusted is False
    assert bands['plant'].radius == 3.0


def test_local_band_relaxes_only_with_replay_evidence():
    bands = fixture_bands()
    assert bands['plant'].radius == 3.0
    a = bands['A']
    assert a.relaxed and a.trusted and a.radius < bands['plant'].radius
    assert a.released > 0 and a.escapes == 0


def test_extra_wet_board_blocks_relaxation():
    bands = fixture_bands()
    b = bands['B']
    assert not b.relaxed and b.radius == bands['plant'].radius


def test_thin_replay_blocks_relaxation():
    bands = fixture_bands()
    d = bands['D']
    assert not d.relaxed and d.radius == bands['plant'].radius
    assert d.replay == BAND_MIN_REPLAY - 5


def test_band_uses_only_matured_labels():
    future = ValidationPoint('A-future', 'A', 1, 10.5, 999.0, False, THIN, 3)
    bands = release_bands(3.0, calibration('A', .4) + [future], [sample('A-r', 'A', .0)])
    assert bands['A'].calibration == 12          # 未到档的点不参与
    assert bands['A'].replay == 1                # 未来标签不进回放证据
    assert bands['A'].escapes == 0               # 巨大未来实测不制造湿板


def test_escape_counts_only_released_wet_boards():
    thin_wet = sample('z', 'A', 1.2)            # 预测 10.5，实测 11.7，越 11.6
    assert thin_wet.observed > moisture_ceiling(thin_wet.thickness)
    assert releases(thin_wet, 1.0)
    thick_ok = sample('y', 'A', 1.2, thickness=THICK)  # 11.7 未越 12.4
    assert not (thick_ok.observed > moisture_ceiling(thick_ok.thickness))


def test_untrusted_cabin_goes_manual(prepared):
    signal = next(candidate.draft.signal for candidate in prepared.candidates if candidate.draft.signal.can_score())
    plan = draft(signal, 10.0, 1.0, trusted=False)
    assert plan.state == Disposition.MANUAL
    assert '可信误差带' in plan.why


def _short_retest(signal, window):
    raw = (*signal.raw[:1], 8.0, *signal.raw[2:])
    from dataclasses import replace
    return replace(signal, raw=raw, record=replace(signal.record, raw=raw, window=window))


def test_needed_retest_that_misses_cooling_window_waits(prepared):
    signal = next(candidate.draft.signal for candidate in prepared.candidates if candidate.draft.signal.can_score())
    assert interpret(_short_retest(signal, 40), 20.0, .5).state == Disposition.WAIT
    assert interpret(_short_retest(signal, 200), 20.0, .5).state == Disposition.BOOKED


def test_release_needs_no_window_even_with_short_dry_time(prepared):
    signal = next(candidate.draft.signal for candidate in prepared.candidates if candidate.draft.signal.can_score())
    short = _short_retest(signal, 40)
    plan = interpret(short, moisture_ceiling(short.raw[0]) - 1.0, .2)
    assert plan.state == Disposition.NORMAL


def test_interval_uses_the_cabin_band(source_bytes):
    display = preview(source_bytes, Scenario(DEFAULT_BUDGET)).payload
    for row in display['decisions']:
        band = row['release_band']
        assert band and band['name']
        if row['interval']:
            low, high = row['interval']
            assert high - low == pytest.approx(2 * band['radius'], abs=1e-4)


def test_workbench_slip_carries_band_label(source_bytes):
    payload = preview(source_bytes, Scenario(DEFAULT_BUDGET)).payload
    rated = [row for row in payload['decisions'] if row['release_band']]
    assert rated and all(row['release_band']['radius'] >= 0 for row in rated)
    unknown = next(row for row in payload['decisions'] if '未建档' in row['region'])
    assert unknown['release_band']['trusted'] is False
    note = summarize(unknown)
    assert note['band']['name'].startswith('无本舱误差带')
    header = manifest(payload).splitlines()[0]
    assert 'release_band' in header and 'release_band_radius' in header


def test_replay_reports_bands_and_confirmations(prepared):
    report = prepared.replay.report()
    assert {'plant', '烘房东舱', '烘房西舱', '返工隔舱'} <= set(report['bands'])
    for band in report['bands'].values():
        assert band['released'] + band['retested'] == band['replay']
        assert 0 <= band['escapes'] <= band['released']


def test_plant_band_trusted_without_any_replay():
    bands = release_bands(3.0, calibration('A', .4), [])
    assert bands['plant'].trusted and bands['plant'].replay == 0
    # 本舱校准够但零回放，仍不得放宽
    assert bands['A'].radius == 3.0 and bands['A'].relaxed is False
