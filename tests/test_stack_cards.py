from csv import DictReader, DictWriter
from io import StringIO
import pytest

from kilnboard.stack_cards.contracts import FormatError, Hold
from kilnboard.stack_cards.parsing import METADATA
from kilnboard.stack_cards.service import inspect_feed, isolation_counts
from kilnboard.settings import FIELDS


def row_bytes(source_bytes, transform):
    source = DictReader(StringIO(source_bytes.decode()))
    first = dict(next(source))
    transform(first)
    buffer = StringIO()
    writer = DictWriter(buffer,source.fieldnames)
    writer.writeheader()
    writer.writerow(first)
    return buffer.getvalue().encode()


def test_field_contract(source):
    row = source.tickets[0]
    assert row.key and row.day >= 2
    assert len(row.raw) == len(FIELDS)
    assert row.received >= row.day
    assert row.hold in Hold
    assert row.fingerprint() == row.fingerprint()


def test_invalid_reading_is_isolated(source):
    reasons = isolation_counts(source)
    assert reasons['nonfinite_reading'] == 1
    assert reasons['live_outcome'] == 1
    assert all(item.key not in {row.key for row in source.tickets} for item in source.rejected)
    assert source.counts()['parsed'] + source.counts()['isolated'] == source.counts()['rows']


def test_invalid_positive_range(source_bytes):
    report = inspect_feed(row_bytes(source_bytes,lambda row: row.update({FIELDS[-1].key:'1e15'})))
    assert report.tickets == ()
    assert report.rejected[0].code == 'reading_range'
    assert FIELDS[-1].title in report.rejected[0].detail


def test_header_rejects_duplicate_names(source_bytes):
    text = source_bytes.splitlines()[0].replace(b',region',b',key')
    with pytest.raises(FormatError) as captured:
        inspect_feed(text+b'\n')
    assert captured.value.code == 'header_identity'


def test_upload_cannot_invent_column(source_bytes):
    prefix = source_bytes.splitlines()[0]
    with pytest.raises(FormatError) as captured:
        inspect_feed(prefix+b',future_prediction\n')
    assert captured.value.code == 'header_mismatch'


def test_result_needs_timestamp(source_bytes):
    payload = row_bytes(source_bytes,lambda row: row.update(outcome_day=''))
    report = inspect_feed(payload)
    assert report.rejected[0].code == 'missing_outcome_day'
    assert report.counts()['rows'] == 1


def test_blank_input_distinguished_from_blank_table():
    with pytest.raises(FormatError) as empty:
        inspect_feed(b'')
    assert empty.value.code == 'feed_size'
    header = ','.join((*METADATA,*(field.key for field in FIELDS))) + '\n'
    with pytest.raises(FormatError) as blank:
        inspect_feed(header.encode())
    assert blank.value.code == 'no_rows'


def test_missing_is_preserved(source_bytes):
    payload = row_bytes(source_bytes,lambda row: row.update({FIELDS[-1].key:'N/A'}))
    report = inspect_feed(payload)
    assert not report.rejected
    assert report.tickets[0].raw[-1] is None


def test_reject_impossible_window(source_bytes):
    payload = row_bytes(source_bytes,lambda row: row.update(window='0'))
    report = inspect_feed(payload)
    assert report.rejected[0].code == 'integer_range'
