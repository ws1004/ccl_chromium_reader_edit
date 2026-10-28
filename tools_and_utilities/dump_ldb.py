import sys
import io
import struct
import pathlib

# Windows 콘솔 UTF-8 출력 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ccl_chromium_reader.storage_formats.ccl_leveldb import (
    LdbFile, BlockHandle, KeyState, read_le_varint
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

    # 첫 바이트가 0x00이면 인코딩 마커 + UTF-16LE 데이터일 가능성
    # (Chromium Local Storage: 0x00 = UTF-16LE, 0x01 = UTF-8/Latin-1)
    if len(value) >= 3 and value[0] == 0x00:
        text_part = value[1:]
        decode_len = len(text_part) if len(text_part) % 2 == 0 else len(text_part) - 1
        if decode_len >= 2:
            try:
                decoded = text_part[:decode_len].decode("utf-16-le", errors="strict")
                if any(c.isprintable() for c in decoded[:20]):
                    preview = decoded[:max_bytes]
                    suffix = f" ... ({len(decoded)} chars)" if len(decoded) > max_bytes else ""
                    return f"\\x00 + UTF16LE \"{preview}{suffix}\""
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

    # UTF-16LE 텍스트 시도 (앞에 마커 없는 경우)
    # ASCII 문자가 포함되어 있어야 실제 텍스트로 판단 (바이너리 오탐 방지)
    if len(value) >= 4:
        decode_len = len(value) if len(value) % 2 == 0 else len(value) - 1
        try:
            decoded = value[:decode_len].decode("utf-16-le", errors="strict")
            sample = decoded[:50]
            ascii_printable = sum(1 for c in sample if c.isascii() and c.isprintable())
            if ascii_printable >= 3:
                preview = decoded[:max_bytes]
                suffix = f" ... ({len(decoded)} chars)" if len(decoded) > max_bytes else ""
                return f"UTF16LE \"{preview}{suffix}\""
        except (UnicodeDecodeError, ValueError):
            pass

    # 바이너리 데이터
    return f"<binary {len(value)} bytes> {format_hex(value, 32)}"


def format_key_display(key: bytes) -> str:
    """Key를 사람이 읽기 쉬운 형태로 표시한다."""
    try:
        text = key.decode("utf-8", errors="replace")
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


def decode_internal_key(raw_key: bytes) -> dict:
    """Internal Key (user_key + 8바이트 메타데이터) 를 파싱한다."""
    if len(raw_key) < 8:
        return {
            "user_key": raw_key,
            "user_key_hex": raw_key.hex(" ", 1) if raw_key else "",
            "user_key_text": format_key_display(raw_key),
            "seq": None,
            "state": "Unknown",
        }

    user_key = raw_key[:-8]
    metadata = struct.unpack("<Q", raw_key[-8:])[0]
    seq = metadata >> 8
    state = "Deleted" if raw_key[-8] == 0 else "Live"

    return {
        "user_key": user_key,
        "user_key_hex": user_key.hex(" ", 1) if user_key else "",
        "user_key_text": format_key_display(user_key),
        "seq": seq,
        "state": state,
    }


def parse_block_entries(raw: bytes, restart_array_offset: int):
    """Block 데이터를 수동 파싱하여 shared/non_shared/value_len 정보를 추출한다."""
    entries = []
    with io.BytesIO(raw) as buff:
        key = b""
        entry_idx = 0
        while buff.tell() < restart_array_offset:
            offset = buff.tell()
            shared = read_le_varint(buff, is_google_32bit=True)
            non_shared = read_le_varint(buff, is_google_32bit=True)
            value_len = read_le_varint(buff, is_google_32bit=True)

            if shared is None or non_shared is None or value_len is None:
                break

            key_delta = buff.read(non_shared)
            value = buff.read(value_len)
            key = key[:shared] + key_delta

            entries.append({
                "index": entry_idx,
                "offset_in_block": offset,
                "shared": shared,
                "non_shared": non_shared,
                "value_len": value_len,
                "key": key,
                "value": value,
            })
            entry_idx += 1

    return entries


def parse_and_print_ldb(ldb_path: str):
    path = pathlib.Path(ldb_path)

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    file_size = path.stat().st_size

    print()
    print("=" * 80)
    print(f"  .ldb (SSTable) File Parser")
    print(f"  File: {path.name}")
    print(f"  Path: {path}")
    print(f"  Size: {file_size:,} bytes (0x{file_size:X})")
    print("=" * 80)

    # LdbFile 열기
    ldb = LdbFile(path)

    # ── Footer ──
    print(f"\n{'─' * 80}")
    print(f"  Footer (last {LdbFile.FOOTER_SIZE} bytes)")
    print(f"{'─' * 80}")
    print(f"  Meta Index Handle : offset={ldb._meta_index_handle.offset:,}, "
          f"length={ldb._meta_index_handle.length:,}")
    print(f"  Index Handle      : offset={ldb._index_handle.offset:,}, "
          f"length={ldb._index_handle.length:,}")
    print(f"  Magic Number      : 0x{LdbFile.MAGIC:016X} (verified)")

    # ── Index Block ──
    print(f"\n{'─' * 80}")
    print(f"  Index Block")
    print(f"{'─' * 80}")

    # Trailer 읽기
    ldb._f.seek(ldb._index_handle.offset + ldb._index_handle.length)
    index_trailer = ldb._f.read(LdbFile.BLOCK_TRAILER_SIZE)
    index_compressed = index_trailer[0] != 0
    index_crc = struct.unpack("<I", index_trailer[1:5])[0]

    # Block 읽기 (압축 해제 포함)
    index_block = ldb._read_block(ldb._index_handle)

    print(f"  Offset             : {ldb._index_handle.offset:,} (0x{ldb._index_handle.offset:X})")
    print(f"  Raw Size           : {ldb._index_handle.length:,} bytes")
    print(f"  Compression        : {'Snappy' if index_compressed else 'None'}")
    if index_compressed:
        print(f"  Decompressed Size  : {len(index_block._raw):,} bytes")
    print(f"  CRC32              : 0x{index_crc:08X}")
    print(f"  Restart Count      : {index_block._restart_array_count}")
    print(f"  Entry Count        : {len(ldb._index)}")

    for i, (sep_key, handle) in enumerate(ldb._index):
        ik = decode_internal_key(sep_key)
        print(f"\n    Entry {i}:")
        print(f"      Separator Key : \"{ik['user_key_text']}\"")
        if ik['seq'] is not None:
            print(f"        seq={ik['seq']}, state={ik['state']}")
        print(f"      → Data Block  : offset={handle.offset:,}, length={handle.length:,}")

    # ── Data Blocks ──
    print(f"\n{'=' * 80}")
    print(f"  Data Blocks ({len(ldb._index)} blocks)")
    print(f"{'=' * 80}")

    total_records = 0
    total_live = 0
    total_deleted = 0
    all_records_info = []

    for b_idx, (sep_key, handle) in enumerate(ldb._index):
        # Trailer 읽기
        ldb._f.seek(handle.offset + handle.length)
        trailer = ldb._f.read(LdbFile.BLOCK_TRAILER_SIZE)
        is_compressed = trailer[0] != 0
        crc = struct.unpack("<I", trailer[1:5])[0]

        # Block 읽기
        block = ldb._read_block(handle)

        # 수동 파싱으로 shared/non_shared 정보 추출
        entries = parse_block_entries(block._raw, block._restart_array_offset)
        entry_count = len(entries)

        live_count = 0
        del_count = 0
        for e in entries:
            if len(e["key"]) >= 8 and e["key"][-8] == 0:
                del_count += 1
            else:
                live_count += 1

        # Block 헤더
        print(f"\n  Data Block #{b_idx}")
        print(f"  {'─' * 60}")
        print(f"  Offset             : {handle.offset:,} (0x{handle.offset:X})")
        print(f"  Raw Size           : {handle.length:,} bytes")
        print(f"  Compression        : {'Snappy' if is_compressed else 'None'}")
        if is_compressed:
            print(f"  Decompressed Size  : {len(block._raw):,} bytes")
            ratio = len(block._raw) / handle.length if handle.length > 0 else 0
            print(f"  Compression Ratio  : {ratio:.1f}x")
        print(f"  CRC32              : 0x{crc:08X}")
        print(f"  Restart Count      : {block._restart_array_count}")
        print(f"  Entry Count        : {entry_count}", end="")

        if entry_count == 0:
            print("  (Empty Block)")
            continue

        # Record 구성 요약
        parts = []
        if live_count > 0:
            parts.append(f"Live ×{live_count}")
        if del_count > 0:
            parts.append(f"Deleted ×{del_count}")
        print(f"  [{', '.join(parts)}]")

        # Restart Array 표시
        restart_offsets = []
        for ri in range(block._restart_array_count):
            restart_offsets.append(block.get_restart_offset(ri))
        print(f"  Restart Array      : "
              f"{[f'0x{o:04X}' for o in restart_offsets]}")

        # 각 Entry 출력
        for entry in entries:
            ik = decode_internal_key(entry["key"])
            state_str = ik["state"]
            state_marker = "★" if state_str == "Deleted" else " "
            seq = ik["seq"]
            user_key = ik["user_key"]
            user_key_len = len(user_key)

            print(f"\n    {state_marker} Record {entry['index']} "
                  f"(seq={seq}, {state_str})")
            print(f"    {'┄' * 50}")
            print(f"      @ offset 0x{entry['offset_in_block']:04X}, "
                  f"shared={entry['shared']}, "
                  f"non_shared={entry['non_shared']}, "
                  f"value_len={entry['value_len']:,}")
            print(f"      Key ({user_key_len} bytes):")
            print(f"        text : \"{ik['user_key_text']}\"")
            if user_key_len <= 64:
                print(f"        hex  : {ik['user_key_hex']}")

            print(f"      Value ({entry['value_len']:,} bytes):")
            print(f"        preview: {format_value_preview(entry['value'])}")

            all_records_info.append({
                "seq": seq,
                "state": state_str,
                "user_key_text": ik["user_key_text"],
                "value_len": entry["value_len"],
                "block_idx": b_idx,
            })

        total_records += entry_count
        total_live += live_count
        total_deleted += del_count

    # ── Summary ──
    print(f"\n{'=' * 80}")
    print(f"  Summary")
    print(f"{'=' * 80}")
    print(f"  File             : {path.name}")
    print(f"  File Size        : {file_size:,} bytes")
    print(f"  Data Blocks      : {len(ldb._index)}")
    print(f"  Total Records    : {total_records}")
    print(f"    Live Records   : {total_live}")
    print(f"    Deleted Records: {total_deleted}")

    # Sequence Number 범위
    seqs = [r["seq"] for r in all_records_info if r["seq"] is not None]
    if seqs:
        print(f"  Seq Range        : {min(seqs)} ~ {max(seqs)}")

    # 삭제된 키 목록
    deleted_keys = [(r["seq"], r["user_key_text"])
                    for r in all_records_info if r["state"] == "Deleted"]
    if deleted_keys:
        print(f"\n  Deleted Keys ({len(deleted_keys)}):")
        for seq, key_text in deleted_keys:
            if len(key_text) > 70:
                key_display = key_text[:35] + "..." + key_text[-32:]
            else:
                key_display = key_text
            print(f"    seq={seq:>5d} │ \"{key_display}\"")

    print()
    ldb.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {pathlib.Path(sys.argv[0]).name} <.ldb file path>")
        print(f"  Example: {pathlib.Path(sys.argv[0]).name} ./leveldb/000011.ldb")
        sys.exit(1)
    parse_and_print_ldb(sys.argv[1])
