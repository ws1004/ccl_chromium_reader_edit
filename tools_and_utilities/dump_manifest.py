import sys
import struct
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ccl_chromium_reader.storage_formats import ccl_leveldb

ENCODING = "utf-8"
FALLBACK_ENCODING = "iso-8859-1"


def decode_internal_key(raw_key: bytes) -> dict:
    """Internal Key (user_key + 8바이트 메타데이터) 를 파싱한다."""
    if len(raw_key) < 8:
        return {
            "user_key_hex": raw_key.hex(" ", 1) if raw_key else "",
            "user_key_text": try_decode(raw_key),
            "seq": None,
            "state": "Unknown",
        }

    user_key = raw_key[:-8]
    metadata = struct.unpack("<Q", raw_key[-8:])[0]
    seq = metadata >> 8
    state = "Deleted" if raw_key[-8] == 0 else "Live"

    return {
        "user_key_hex": user_key.hex(" ", 1) if user_key else "",
        "user_key_text": try_decode(user_key),
        "seq": seq,
        "state": state,
    }


def try_decode(data: bytes) -> str:
    """바이너리 데이터를 읽을 수 있는 텍스트로 디코딩 시도."""
    if not data:
        return ""
    try:
        text = data.decode(ENCODING, errors="replace")
    except Exception:
        text = data.decode(FALLBACK_ENCODING, errors="replace")
    return text


def print_separator(char="─", length=70):
    print(char * length)


def print_version_edit(index: int, edit: ccl_leveldb.VersionEdit):
    """하나의 VersionEdit를 보기 좋게 출력한다."""
    print(f"\n  VersionEdit #{index}")
    print_separator("─", 50)

    if edit.comparator is not None:
        print(f"  Comparator       : {edit.comparator}")
    if edit.log_number is not None:
        print(f"  LogNumber        : {edit.log_number}")
    if edit.prev_log_number is not None:
        print(f"  PrevLogNumber    : {edit.prev_log_number}")
    if edit.next_file_number is not None:
        print(f"  NextFileNumber   : {edit.next_file_number}")
    if edit.last_sequence is not None:
        print(f"  LastSequence     : {edit.last_sequence}")

    # CompactPointer
    if edit.compaction_pointers:
        print(f"\n  CompactionPointers ({len(edit.compaction_pointers)}):")
        for cp in edit.compaction_pointers:
            print(f"    Level {cp.level} → {cp.pointer.hex(' ', 1)}")

    # DeletedFile
    if edit.deleted_files:
        print(f"\n  DeletedFiles ({len(edit.deleted_files)}):")
        for df in edit.deleted_files:
            print(f"    Level {df.level} : file #{df.file_no:06d} ({df.file_no:06X}.ldb)")

    # NewFile
    if edit.new_files:
        print(f"\n  NewFiles ({len(edit.new_files)}):")
        for nf in edit.new_files:
            smallest = decode_internal_key(nf.smallest_key)
            largest = decode_internal_key(nf.largest_key)

            print(f"    ┌ Level {nf.level} : file #{nf.file_no:06d} ({nf.file_no:06X}.ldb)")
            print(f"    │ FileSize     : {nf.file_size:,} bytes")
            print(f"    │ SmallestKey  : \"{smallest['user_key_text']}\"")
            print(f"    │   hex        : {smallest['user_key_hex']}")
            print(f"    │   seq={smallest['seq']}, state={smallest['state']}")
            print(f"    │ LargestKey   : \"{largest['user_key_text']}\"")
            print(f"    │   hex        : {largest['user_key_hex']}")
            print(f"    │   seq={largest['seq']}, state={largest['state']}")
            print(f"    └{'─' * 45}")


def main(manifest_path: str):
    path = pathlib.Path(manifest_path)

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    # ManifestFile 생성
    try:
        manifest = ccl_leveldb.ManifestFile(path)
    except ValueError as e:
        print(f"Error: {e}")
        print(f"  파일명이 MANIFEST-XXXXXX 형식이어야 합니다.")
        sys.exit(1)

    print()
    print("=" * 70)
    print(f"  MANIFEST File Parser")
    print(f"  File: {path.name}")
    print(f"  Path: {path}")
    print("=" * 70)

    # VersionEdit 순회 및 출력
    # ManifestFile.__init__에서 이미 이터레이션하므로 다시 열어서 파싱
    manifest._f.seek(0)
    edit_count = 0

    for idx, edit in enumerate(manifest, start=1):
        print_version_edit(idx, edit)
        edit_count = idx

    print()
    print_separator("=", 70)
    print(f"  Summary")
    print_separator("=", 70)
    print(f"  Total VersionEdits : {edit_count}")

    # file_to_level 매핑 출력
    if manifest.file_to_level:
        print(f"\n  file_to_level mapping ({len(manifest.file_to_level)} files):")
        print(f"  {'File':>20s}  {'Level':>5s}")
        print(f"  {'─' * 20}  {'─' * 5}")
        for file_no, level in sorted(manifest.file_to_level.items()):
            print(f"  {file_no:06d} ({file_no:06X}.ldb)  Level {level}")
    else:
        print("\n  file_to_level mapping: (empty)")

    print()
    manifest.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {pathlib.Path(sys.argv[0]).name} <MANIFEST file path>")
        print(f"  Example: {pathlib.Path(sys.argv[0]).name} ./leveldb/MANIFEST-000004")
        sys.exit(1)
    main(sys.argv[1])
