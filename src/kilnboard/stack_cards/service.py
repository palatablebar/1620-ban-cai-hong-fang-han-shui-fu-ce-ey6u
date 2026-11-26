from collections import Counter
from csv import Error as CSVError, DictReader
from hashlib import sha256
from io import StringIO
from pathlib import Path

from ..settings import FIELDS, MODE
from .contracts import Field, FormatError, ImportReport, Rejection, Ticket
from .parsing import METADATA, read_row

MAX_BYTES = 3_200_000
MAX_LINES = 14_000


def decode_feed(content: bytes) -> str:
    if not content or len(content) > MAX_BYTES:
        raise FormatError('feed_size', '文件为空或超过 3.2 MB')
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise FormatError('feed_encoding', '请提交 UTF-8 表格') from error


def inspect_feed(content: bytes, fields: tuple[Field, ...] = FIELDS) -> ImportReport:
    text = decode_feed(content)
    clean: list[Ticket] = []
    rejected: list[Rejection] = []
    counts = 0
    reader = DictReader(StringIO(text, newline=''), strict=True)
    headers = (*METADATA, *(field.key for field in fields))
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise FormatError('header_identity', '表头为空或列名重复')
    if reader.fieldnames and set(headers) != set(reader.fieldnames):
        missing = sorted(set(headers) - set(reader.fieldnames))
        extra = sorted(set(reader.fieldnames) - set(headers))
        raise FormatError('header_mismatch', f'缺列 {missing}；额外列 {extra}')
    try:
        for row in reader:
            counts += 1
            if counts > MAX_LINES:
                raise FormatError('feed_row_limit', '单次最多接收 14000 条记录')
            key = str(row.get('key') or '')[:48]
            if None in row or any(value is None for value in row.values()):
                rejected.append(Rejection(reader.line_num, key, 'column_count', '单据列数与表头不同'))
                continue
            try:
                clean.append(read_row(row,fields,MODE))
            except FormatError as error:
                rejected.append(Rejection(reader.line_num, key, error.code, str(error)))
    except CSVError as error:
        raise FormatError('csv_structure', f'第 {reader.line_num} 行引号或分隔符损坏') from error
    if counts == 0:
        raise FormatError('no_rows', '表格只有表头')
    return ImportReport(tuple(clean), tuple(rejected), counts, sha256(content).hexdigest())


def inspect_path(path: Path) -> ImportReport:
    with path.open('rb') as feed:
        return inspect_feed(feed.read(MAX_BYTES + 1))


def isolation_counts(report: ImportReport) -> dict[str, int]:
    return dict(sorted(Counter(row.code for row in report.rejected).items()))
