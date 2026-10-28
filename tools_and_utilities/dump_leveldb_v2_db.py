import io, sys, sqlite3, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from ccl_chromium_reader.storage_formats import ccl_leveldb

def safe_decode(data, encoding):
    try:
        return data.decode(encoding, errors="replace")
    except Exception:
        return ""

def safe_decode_strict(data, encoding):
    try:
        return data.decode(encoding, errors="strict")
    except Exception:
        return None

def main(args):
    input_path = args[0]
    output_path = "leveldb_dump.db"
    if len(args) > 1:
        output_path = args[1]

    leveldb_records = ccl_leveldb.RawLevelDb(input_path)

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS records")
    cursor.execute("""
        CREATE TABLE records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hex TEXT,
            key_ascii TEXT,
            value_hex TEXT,
            value_ascii TEXT,
            value_utf16le TEXT,
            origin_file TEXT,
            file_type TEXT,
            offset INTEGER,
            seq INTEGER,
            state TEXT,
            was_compressed INTEGER
        )
    """)

    for record in leveldb_records.iterate_records_raw():
        # print(safe_decode(record.value[1:], "ascii"), len(record.value))
        value_data = record.value[1:] if len(record.value) > 1 else record.value
        value_ascii = safe_decode_strict(value_data, "ascii")
        if value_ascii is None:
            value_ascii = sqlite3.Binary(value_data)
            value_utf16le = safe_decode_strict(value_data, "utf-16-le")
        else:
            value_utf16le = None
        cursor.execute(
            "INSERT INTO records (key_hex, key_ascii, value_hex, value_ascii, value_utf16le, origin_file, file_type, offset, seq, state, was_compressed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.user_key.hex(" ", 1),                                                    # key_hex
                ''.join(c if c.isprintable() else '.' for c in safe_decode(record.user_key, "ascii")),  # key_ascii
                record.value.hex(" ", 1),                                                       # value_hex
                value_ascii,                                                                    # value_ascii
                value_utf16le,                                                                  # value_utf16le
                str(record.origin_file),                                                        # origin_file
                record.file_type.name,                                                          # file_type
                record.offset,                                                                  # offset
                record.seq,                                                                     # seq
                record.state.name,                                                              # state
                record.was_compressed                                                           # was_compressed
            )
        )

    conn.commit()
    conn.close()
    print(f"Export complete: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {pathlib.Path(sys.argv[0]).name} <indir path> [outpath.db]")
        exit(1)
    print()
    print("+--------------------------------------------------------+")
    print("|Please note: keys and values in leveldb are binary blobs|")
    print("|so any text seen in the output of this script might not |")
    print("|represent the entire meaning of the data. The output of |")
    print("|this script should be considered as a preview of the    |")
    print("|data only.                                              |")
    print("+--------------------------------------------------------+")
    print()
    main(sys.argv[1:])
