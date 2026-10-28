import sys
import io
import struct
import pathlib

# Windows 콘솔 UTF-8 출력 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ccl_chromium_reader.storage_formats.ccl_leveldb import (
    LogFile, LogEntryType, KeyState, read_le_varint
)

ENCODING = "utf-8"
FALLBACK_ENCODING = "iso-8859-1"

# Value 출력 시 최대 바이트 수
MAX_VALUE_DISPLAY = 256


def try_decode(data: bytes) -> str:
    if not data:
        return ""
    try:
        text = data.decode(ENCODING, errors="replace")
    except Exception:
        text = data.decode(FALLBACK_ENCODING, errors="replace")
    return text


def format_hex(data: bytes, max_bytes: int = 64) -> str:
    if len(data) <= max_bytes:
        return data.hex(" ", 1) if data else ""
    return data[:max_bytes].hex(" ", 1) + f" ... ({len(data)} bytes total)"


def format_value_preview(value: bytes, max_bytes: int = MAX_VALUE_DISPLAY) -> str:
    """Value 데이터의 미리보기를 생성한다."""
    if not value:
        return "(empty)"

    # 첫 바이트가 0x01이면 버전 바이트 + 텍스트 데이터일 가능성
    if len(value) >= 2 and value[0] == 0x01:
        text_part = value[1:]
        # UTF-8 텍스트 시도
        try:
            decoded = text_part.decode("utf-8", errors="strict")
            if decoded.isprintable() or any(c in decoded for c in ['{', '[', '"']):
                preview = decoded[:max_bytes]
                suffix = f" ... ({len(text_part)} chars)" if len(decoded) > max_bytes else ""
                return f"\\x01 + \"{preview}{suffix}\""
        except UnicodeDecodeError:
            pass

        # UTF-16LE 텍스트 시도
        if len(text_part) >= 2 and len(text_part) % 2 == 0:
            try:
                decoded = text_part.decode("utf-16-le", errors="strict")
                if any(c.isprintable() for c in decoded[:20]):
                    preview = decoded[:max_bytes]
                    suffix = f" ... ({len(decoded)} chars)" if len(decoded) > max_bytes else ""
                    return f"\\x01 + UTF16LE \"{preview}{suffix}\""
            except (UnicodeDecodeError, ValueError):
                pass

    # 일반 UTF-8 텍스트 시도
    try:
        decoded = value.decode("utf-8", errors="strict")
        if decoded.isprintable() or any(c in decoded for c in ['{', '[', '"']):
            preview = decoded[:max_bytes]
            suffix = f" ... ({len(decoded)} chars)" if len(decoded) > max_bytes else ""
            return f"\"{preview}{suffix}\""
    except UnicodeDecodeError:
        pass

    # 바이너리 데이터
    return f"<binary {len(value)} bytes> {format_hex(value, 32)}"


def print_separator(char="─", length=80):
    print(char * length)


def format_key_display(key: bytes) -> str:
    """Key를 사람이 읽기 쉬운 형태로 표시한다."""
    try:
        text = key.decode("utf-8", errors="replace")
        # 제어 문자를 이스케이프 처리
        display = ""
        for ch in text:
            if ch == '\x00':
                display += "\\x00"
            elif ch == '\x01':
                display += "\\x01"
            elif ord(ch) < 0x20:
                display += f"\\x{ord(ch):02x}"
            else:
                display += ch
        return display
    except Exception:
        return key.hex(" ", 1)


def parse_and_print_log(log_path: str):
    path = pathlib.Path(log_path)

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    file_size = path.stat().st_size

    print()
    print("=" * 80)
    print(f"  WAL .log File Parser")
    print(f"  File: {path.name}")
    print(f"  Path: {path}")
    print(f"  Size: {file_size:,} bytes (0x{file_size:X})")
    print("=" * 80)

    # ── 물리적 계층: Log Entry 정보 수집 ──
    log_entries = []
    with path.open("rb") as f:
        block_idx = 0
        while True:
            chunk = f.read(LogFile.LOG_BLOCK_SIZE)
            if not chunk:
                break

            with io.BytesIO(chunk) as buff:
                while buff.tell() < len(chunk) - 6:
                    entry_offset_in_block = buff.tell()
                    header = buff.read(7)
                    if len(header) < 7:
                        break

                    crc, length, block_type = struct.unpack("<IHB", header)

                    if block_type == LogEntryType.Zero:
                        break

                    abs_offset = block_idx * LogFile.LOG_BLOCK_SIZE + entry_offset_in_block

                    log_entries.append({
                        "offset": abs_offset,
                        "crc": crc,
                        "length": length,
                        "type": LogEntryType(block_type),
                        "block_idx": block_idx,
                    })

                    # 데이터 영역 건너뛰기
                    buff.read(length)

            block_idx += 1

    # ── 논리적 계층: LogFile 클래스를 사용하여 Batch/Record 파싱 ──
    log_file = LogFile(path)

    batches = []
    for batch_offset, batch_data in log_file._get_batches():
        with io.BytesIO(batch_data) as buff:
            header = buff.read(12)
            seq, count = struct.unpack("<QI", header)

            records = []
            for i in range(count):
                rec_offset = buff.tell()
                state = KeyState(buff.read(1)[0])
                key_length = read_le_varint(buff, is_google_32bit=True)
                key = buff.read(key_length)

                if state != KeyState.Deleted:
                    value_length = read_le_varint(buff, is_google_32bit=True)
                    value = buff.read(value_length)
                else:
                    value_length = 0
                    value = b""

                records.append({
                    "index": i,
                    "seq": seq + i,
                    "state": state,
                    "key": key,
                    "key_length": key_length,
                    "value": value,
                    "value_length": value_length if state != KeyState.Deleted else None,
                    "offset_in_batch": rec_offset,
                })

            batches.append({
                "offset": batch_offset,
                "seq": seq,
                "count": count,
                "data_size": len(batch_data),
                "records": records,
            })

    # ── 물리적 계층 출력 ──
    print(f"\n{'─' * 80}")
    print(f"  Physical Layer — Log Entries ({len(log_entries)} entries)")
    print(f"{'─' * 80}")

    for i, entry in enumerate(log_entries):
        type_name = entry['type'].name
        print(f"  Entry {i:>3d} │ offset=0x{entry['offset']:06X} │ "
              f"CRC=0x{entry['crc']:08X} │ "
              f"Length={entry['length']:>5d} │ "
              f"Type={type_name:<6s} │ "
              f"Block={entry['block_idx']}")

    # ── 논리적 계층 출력 ──
    print(f"\n{'=' * 80}")
    print(f"  Logical Layer — Batches ({len(batches)} batches)")
    print(f"{'=' * 80}")

    total_records = 0
    total_live = 0
    total_deleted = 0

    for b_idx, batch in enumerate(batches):
        count = batch["count"]
        seq = batch["seq"]
        records = batch["records"]

        live_count = sum(1 for r in records if r["state"] == KeyState.Live)
        del_count = sum(1 for r in records if r["state"] == KeyState.Deleted)
        total_records += count
        total_live += live_count
        total_deleted += del_count

        # Batch 헤더
        print(f"\n  Batch #{b_idx}")
        print(f"  {'─' * 60}")
        print(f"  Offset         : 0x{batch['offset']:06X}")
        print(f"  Data Size      : {batch['data_size']:,} bytes")
        print(f"  Sequence Number: {seq}")
        print(f"  Record Count   : {count}", end="")

        if count == 0:
            print("  (Empty Batch)")
            continue

        # Record 구성 요약
        parts = []
        if live_count > 0:
            parts.append(f"Live ×{live_count}")
        if del_count > 0:
            parts.append(f"Deleted ×{del_count}")
        print(f"  [{', '.join(parts)}]")

        # 각 Record 출력
        for rec in records:
            state_str = rec["state"].name
            state_marker = "★" if rec["state"] == KeyState.Deleted else " "

            print(f"\n    {state_marker} Record {rec['index']} (seq={rec['seq']}, {state_str})")
            print(f"    {'┄' * 50}")
            print(f"      Key ({rec['key_length']} bytes):")
            print(f"        text : \"{format_key_display(rec['key'])}\"")
            if rec['key_length'] <= 64:
                print(f"        hex  : {rec['key'].hex(' ', 1) if rec['key'] else ''}")

            if rec["state"] == KeyState.Deleted:
                print(f"      Value  : (N/A — Deleted record, no value field)")
            else:
                print(f"      Value ({rec['value_length']} bytes):")
                print(f"        preview: {format_value_preview(rec['value'])}")

    # ── Summary ──
    print(f"\n{'=' * 80}")
    print(f"  Summary")
    print(f"{'=' * 80}")
    print(f"  File             : {path.name}")
    print(f"  File Size        : {file_size:,} bytes")
    print(f"  Log Entries      : {len(log_entries)}")
    print(f"  Batches          : {len(batches)}")
    print(f"  Total Records    : {total_records}")
    print(f"    Live Records   : {total_live}")
    print(f"    Deleted Records: {total_deleted}")

    # Sequence Number 범위
    if batches:
        min_seq = min(b["seq"] for b in batches)
        max_seq = max(
            b["seq"] + b["count"] - 1 for b in batches if b["count"] > 0
        ) if any(b["count"] > 0 for b in batches) else min_seq
        print(f"  Seq Range        : {min_seq} ~ {max_seq}")

    # 삭제된 키 목록
    deleted_keys = []
    for batch in batches:
        for rec in batch["records"]:
            if rec["state"] == KeyState.Deleted:
                deleted_keys.append((rec["seq"], format_key_display(rec["key"])))

    if deleted_keys:
        print(f"\n  Deleted Keys ({len(deleted_keys)}):")
        for seq, key_text in deleted_keys:
            # 긴 키는 축약
            if len(key_text) > 70:
                key_display = key_text[:35] + "..." + key_text[-32:]
            else:
                key_display = key_text
            print(f"    seq={seq:>5d} │ \"{key_display}\"")

    print()
    log_file.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {pathlib.Path(sys.argv[0]).name} <.log file path>")
        print(f"  Example: {pathlib.Path(sys.argv[0]).name} ./leveldb/000010.log")
        sys.exit(1)
    parse_and_print_log(sys.argv[1])
