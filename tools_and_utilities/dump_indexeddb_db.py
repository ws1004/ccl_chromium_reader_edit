"""
Copyright 2020-2024, CCL Forensics

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import pathlib
import sqlite3
import traceback

# 프로젝트 루트를 sys.path에 추가 (상위 디렉토리)
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ccl_chromium_reader import ccl_chromium_indexeddb

__version__ = "0.1"
__description__ = "Dumps a Chromium IndexedDB leveldb to sqlite for review"
__contact__ = "Alex Caithness"

DB_SCHEMA = """
CREATE TABLE "databases" (
    "_id"       INTEGER PRIMARY KEY AUTOINCREMENT,
    "db_number" INTEGER,
    "name"      TEXT,
    "origin"    TEXT
);

CREATE TABLE "object_stores" (
    "_id"             INTEGER PRIMARY KEY AUTOINCREMENT,
    "database_id"     INTEGER,
    "object_store_id" INTEGER,
    "name"            TEXT
);

CREATE TABLE "records" (
    "_id"             INTEGER PRIMARY KEY AUTOINCREMENT,
    "object_store_id" INTEGER,
    "key"             TEXT,
    "value"           TEXT,
    "is_live"         INTEGER,
    "ldb_seq_no"      INTEGER,
    "origin_file"     TEXT,
    "error_msg"       TEXT
);

CREATE INDEX "databases_origin"         ON "databases"     ("origin");
CREATE INDEX "records_object_store_id"  ON "records"       ("object_store_id");
CREATE INDEX "records_ldb_seq_no"       ON "records"       ("ldb_seq_no");

CREATE VIEW "records_view" AS
    SELECT
        d.origin,
        d.name          AS db_name,
        os.name         AS store_name,
        r.key,
        r.value,
        r.is_live,
        r.ldb_seq_no,
        r.origin_file,
        r.error_msg
    FROM records r
        LEFT JOIN object_stores os ON r.object_store_id = os._id
        LEFT JOIN databases     d  ON os.database_id    = d._id
    ORDER BY r.ldb_seq_no;
"""

INSERT_DB_SQL = """
    INSERT INTO "databases" ("db_number", "name", "origin")
    VALUES (?, ?, ?);
"""
INSERT_OBJSTORE_SQL = """
    INSERT INTO "object_stores" ("database_id", "object_store_id", "name")
    VALUES (?, ?, ?);
"""
INSERT_RECORD_SQL = """
    INSERT INTO "records" ("object_store_id", "key", "value", "is_live", "ldb_seq_no", "origin_file", "error_msg")
    VALUES (?, ?, ?, ?, ?, ?, ?);
"""


def main(args):
    ldb_path = pathlib.Path(args[0])
    blob_path = pathlib.Path(args[1]) if len(args) > 1 else None
    db_out_path = pathlib.Path(args[2]) if len(args) > 2 else pathlib.Path("indexeddb_dump.db")

    if db_out_path.exists():
        print(f"[!] Output database already exists, overwriting: {db_out_path}")
        db_out_path.unlink()

    wrapper = ccl_chromium_indexeddb.WrappedIndexDB(ldb_path, blob_path)
    out_db = sqlite3.connect(db_out_path)
    out_db.executescript(DB_SCHEMA)
    cur = out_db.cursor()

    for db_info in wrapper.database_ids:
        db = wrapper[db_info.dbid_no]

        cur.execute(INSERT_DB_SQL, (db.db_number, db.name, db.origin))
        cur.execute("SELECT last_insert_rowid();")
        db_row_id = cur.fetchone()[0]

        for obj_store_name in db.object_store_names:
            if obj_store_name is None:
                continue
            if not isinstance(obj_store_name, (str, int)):
                continue

            try:
                obj_store = db[obj_store_name]
            except (TypeError, KeyError) as e:
                # object store 접근 자체가 실패한 경우 records 없이 object_stores만 기록
                cur.execute(INSERT_OBJSTORE_SQL, (db_row_id, None, str(obj_store_name)))
                cur.execute("SELECT last_insert_rowid();")
                os_row_id = cur.fetchone()[0]
                cur.execute(INSERT_RECORD_SQL,
                            (os_row_id, None, None, None, None, None,
                             f"Error accessing object store: {type(e).__name__}: {e}"))
                continue

            cur.execute(INSERT_OBJSTORE_SQL,
                        (db_row_id, obj_store.object_store_id, str(obj_store.name)))
            cur.execute("SELECT last_insert_rowid();")
            os_row_id = cur.fetchone()[0]

            # 역직렬화 오류를 모아두기 위한 리스트 (클로저 공유)
            deser_errors = []

            def _on_bad_record(key, data, _errors=deser_errors):
                _errors.append((str(key), traceback.format_exc()))

            try:
                for record in obj_store.iterate_records(bad_deserializer_data_handler=_on_bad_record):
                    cur.execute(
                        INSERT_RECORD_SQL,
                        (
                            os_row_id,
                            str(record.key),
                            str(record.value),
                            1 if record.is_live else 0,
                            record.ldb_seq_no,
                            str(record.origin_file),
                            None,
                        )
                    )
            except Exception as e:
                cur.execute(INSERT_RECORD_SQL,
                            (os_row_id, None, None, None, None, None,
                             f"Error iterating records: {type(e).__name__}: {e}"))

            # 역직렬화 오류 레코드 저장
            for err_key, err_tb in deser_errors:
                cur.execute(INSERT_RECORD_SQL,
                            (os_row_id, err_key, None, None, None, None, err_tb))
            deser_errors.clear()

    cur.close()
    out_db.commit()
    out_db.close()
    print(f"Done. Output: {db_out_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"USAGE: {pathlib.Path(sys.argv[0]).name} <ldb dir path> [blob dir path] [out.db]")
        exit(1)
    main(sys.argv[1:])
