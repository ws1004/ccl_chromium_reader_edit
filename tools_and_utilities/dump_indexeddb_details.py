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

# 프로젝트 루트를 sys.path에 추가 (상위 디렉토리)
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ccl_chromium_reader import ccl_chromium_indexeddb


def main(args):
    ldb_path = pathlib.Path(args[0])
    blob_path = pathlib.Path(args[1]) if len(args) > 1 else None
    wrapper = ccl_chromium_indexeddb.WrappedIndexDB(ldb_path, blob_path)

    for db_info in wrapper.database_ids:
        db = wrapper[db_info.dbid_no]
        print("------Database------")
        print(f"db_number={db.db_number}; name={db.name}; origin={db.origin}")
        print()
        print("\t---Object Stores---")
        for obj_store_name in db.object_store_names:
            # Skip if name is None or not a valid string/int
            if obj_store_name is None:
                print(f"\t[Skipping object store with None name]")
                continue
            if not isinstance(obj_store_name, (str, int)):
                print(f"\t[Skipping object store with invalid name type: {type(obj_store_name)}]")
                continue

            try:
                obj_store = db[obj_store_name]
            except (TypeError, KeyError) as e:
                print(f"\t[Error accessing object store '{obj_store_name}': {e}]")
                continue

            print(f"\tobject_store_id={obj_store.object_store_id}; name={obj_store.name}")
            def _print_error_with_traceback(key, data):
                import traceback
                print(f"\tERROR decoding key: {key}")
                traceback.print_exc()

            record_count = 0
            try:
                for record in obj_store.iterate_records(bad_deserializer_data_handler=_print_error_with_traceback):
                    record_count += 1
                    print(f"\tKey : {record.key}")
                    print(f"\t\tvalue: {record.value}")
                    print()
            except (ValueError, Exception) as e:
                print(f"\tError reading records: {type(e).__name__}: {e}")
            if record_count == 0:
                print("\tNo records")
            print()
        print()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"USAGE: {pathlib.Path(sys.argv[0]).name} <ldb dir path> [blob dir path]")
        exit(1)
    main(sys.argv[1:])
