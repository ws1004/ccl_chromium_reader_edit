# CCL Chromium Reader - Tools & Utilities (Modified)

> **본 프로젝트는 [CCL Group Ltd.](https://github.com/cclgroupltd)의 [ccl_chromium_reader](https://github.com/cclgroupltd/ccl_chromium_reader) (v0.3.14, Author: Alex Caithness)를 기반으로 수정한 버전입니다.**
>
> 원본 프로젝트: https://github.com/cclgroupltd/ccl_chromium_reader
>
> 본 저장소에서는 원본 라이브러리의 `tools_and_utilities` 도구들을 활용하여 Chromium 브라우저 아티팩트를 분석하는 데 초점을 두고 있으며, 사용법 문서화 및 일부 기능을 추가/수정하였습니다.

Chromium 브라우저 아티팩트(Local Storage, Session Storage, IndexedDB, LevelDB 등)를 파싱하고 분석하기 위한 도구 모음입니다.

## 목차

- [사전 요구사항](#사전-요구사항)
- [도구 목록](#도구-목록)
  - [Chromium_dump_local_storage.py](#1-chromium_dump_local_storagepy)
  - [Chromium_dump_session_storage.py](#2-chromium_dump_session_storagepy)
  - [dump_indexeddb_details.py](#3-dump_indexeddb_detailspy)
  - [dump_indexeddb_db.py](#4-dump_indexeddb_dbpy)
  - [dump_leveldb.py](#5-dump_leveldbpy)
  - [dump_leveldb_v2_db.py](#6-dump_leveldb_v2_dbpy)
  - [ccl_chrome_audit.py](#7-ccl_chrome_auditpy)
  - [benchmark.py](#8-benchmarkpy)
  - [extras/](#9-extras)
- [에러 유형 및 대처 방법](#에러-유형-및-대처-방법)

---

## 사전 요구사항

### 패키지 설치

**방법 1: pip를 통한 일반 설치**
```bash
pip install ccl_chromium_reader
```

**방법 2: 개발 모드(editable mode)로 설치**

프로젝트 소스 코드를 직접 수정하면서 사용하려면, 프로젝트 루트 경로에서 개발 모드로 설치할 수 있습니다:
```bash
python -m pip install -e .
```

> **개발 모드(`-e`)란?**
> - 일반 설치(`pip install .`)는 패키지를 Python의 `site-packages` 폴더로 **복사**하므로, 소스를 수정해도 반영되지 않습니다 (재설치 필요).
> - 개발 모드(`pip install -e .`)는 현재 디렉토리를 **링크**로 등록하므로, 소스 코드를 수정하면 **즉시 반영**됩니다.
> - 본 프로젝트처럼 코드를 수정하며 사용하는 경우 개발 모드를 권장합니다.

### 추가 패키지

`ccl_chrome_audit.py`를 Windows에서 쿠키 복호화와 함께 사용하려면 추가 패키지가 필요합니다:
```bash
pip install pywin32 pycryptodome
```

---

## 도구 목록

### 1. Chromium_dump_local_storage.py

Chromium Local Storage LevelDB 데이터를 SQLite 데이터베이스로 덤프합니다.

#### 사용법

```bash
python tools_and_utilities/Chromium_dump_local_storage.py <leveldb_dir> [output.db]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | Chromium Local Storage LevelDB 디렉토리 경로 (예: `User Data/Default/Local Storage/leveldb`) |
| `output.db` | X | 출력할 SQLite 파일 경로 (기본값: `local_storage_dump.db`) |

#### 사용 예시

```bash
# 기본 출력 파일명 사용
python tools_and_utilities/Chromium_dump_local_storage.py "C:\Artifacts\Local Storage\leveldb"

# 출력 파일 지정
python tools_and_utilities/Chromium_dump_local_storage.py "C:\Artifacts\Local Storage\leveldb" output_local_storage.db
```

#### 출력 SQLite 스키마

- **storage_keys** 테이블: storage key 목록
- **batches** 테이블: LevelDB 배치 정보 (start_ldbseq, end_ldbseq, storage_key, timestamp)
- **records** 테이블: 실제 key-value 레코드 (storage_key, key, value, batch, ldbseq)
- **records_view** 뷰: storage_key, key, value, batch_timestamp(UTC 변환), ldbseq를 조인하여 ldbseq 순 정렬

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | 출력 DB 파일이 이미 존재할 때 | `output database already exists` |
| `IOError` | 입력 경로가 디렉토리가 아닐 때 | `Input directory is not a directory` |
| `ValueError` | LevelDB 데이터 파싱 중 예상치 못한 프리픽스 | `Unexpected prefix, please contact developer` |
| `UnicodeDecodeError` | 레코드 값의 인코딩이 깨졌을 때 | (경고 출력 후 계속 진행) |
| 인자 오류 | 인자가 1개 미만이거나 3개 초과일 때 | `Chromium_dump_local_storage.py <leveldb dir> [local_storage_dump.db]` |

---

### 2. Chromium_dump_session_storage.py

Chromium Session Storage LevelDB 데이터를 SQLite 데이터베이스로 덤프합니다. 호스트와 연결되지 않은 고아(orphan) 레코드도 host=NULL로 저장됩니다.

#### 사용법

```bash
python tools_and_utilities/Chromium_dump_session_storage.py <leveldb_dir> [output.db]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | Chromium Session Storage 디렉토리 경로 (예: `User Data/Default/Session Storage`) |
| `output.db` | X | 출력할 SQLite 파일 경로 (기본값: `session_storage_dump.db`) |

#### 사용 예시

```bash
# 기본 출력 파일명 사용
python tools_and_utilities/Chromium_dump_session_storage.py "C:\Artifacts\Session Storage"

# 출력 파일 지정
python tools_and_utilities/Chromium_dump_session_storage.py "C:\Artifacts\Session Storage" output_session_storage.db
```

#### 출력 SQLite 스키마

- **hosts** 테이블: 호스트(도메인) 목록
- **guids** 테이블: GUID 목록 (현재 미사용, NULL로 저장)
- **items** 테이블: 세션 스토리지 레코드 (host, guid, ldbseq, key, value) — 고아 레코드는 host=NULL
- **items_view** 뷰: ldbseq, host, key, value, guid를 조인하여 ldbseq 순 정렬

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | 출력 DB 파일이 이미 존재할 때 | `output database already exists` |
| `IOError` | 입력 경로가 디렉토리가 아닐 때 | `Input directory is not a directory` |
| `ValueError` | map_id 충돌 발생 시 (데이터 손상) | `map_id collision` |
| `UnicodeDecodeError` | UTF-8/UTF-16-LE 디코딩 실패 시 | (경고 출력 후 계속 진행) |
| 인자 오류 | 인자가 1개 미만이거나 3개 초과일 때 | `Chromium_dump_session_storage.py <leveldb dir> [session_storage_dump.db]` |

---

### 3. dump\_indexeddb\_details.py

Chromium IndexedDB LevelDB 데이터베이스의 구조와 **전체 레코드**를 터미널에 출력합니다. 오브젝트 스토어별로 모든 key/value를 순서대로 출력하며, None이나 유효하지 않은 스토어 이름은 자동으로 건너뜁니다.

#### 사용법

```bash
python tools_and_utilities/dump_indexeddb_details.py <leveldb_dir> <blob_dir>
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | IndexedDB LevelDB 디렉토리 경로 (예: `IndexedDB/origin_name.indexeddb.leveldb`) |
| `blob_dir` | O | IndexedDB blob 파일 디렉토리 경로 (예: `IndexedDB/origin_name.indexeddb.blob`) |

> **참고:** 코드 내부적으로는 `blob_dir`을 생략할 수 있지만, 현재 인자 검사(`len < 3`) 로직으로 인해 실행 시 2개 인자가 모두 필요합니다.

#### 사용 예시

```bash
python tools_and_utilities/dump_indexeddb_details.py "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.leveldb" "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.blob"
```

#### 출력 형식

```
------Database------
db_number=1; name=myDatabase; origin=https://example.com

    ---Object Stores---
    object_store_id=1; name=myStore
    Key : 1
        value: {'field': 'data'}

    Key : 2
        value: {'field': 'data2'}
```

각 데이터베이스의 모든 오브젝트 스토어와 그 안의 **전체 레코드**(key + value)를 출력합니다. 레코드가 없으면 `No records`를 출력하고, 역직렬화 오류가 발생한 키는 오류 메시지와 함께 출력 후 계속 진행합니다.

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | LevelDB 매직 넘버가 유효하지 않을 때 | `invalid magic number in {file}` |
| `ValueError` | Blink 직렬화 데이터가 손상되었을 때 | `Blink type tag not present` |
| `ValueError` | 프리픽스 데이터를 충분히 읽지 못했을 때 | `Couldn't get enough data when reading prefix length` |
| `NotImplementedError` | 지원하지 않는 키 타입을 만났을 때 | (MinKey 등 미구현 타입) |
| `FileNotFoundError` | blob 파일이 존재하지 않을 때 | (누락된 blob 파일 경로) |
| `TypeError` / `KeyError` | 오브젝트 스토어 접근 실패 시 | `[Error accessing object store '...': ...]` 출력 후 건너뜀 |
| 인자 부족 | 인자가 2개 미만일 때 | `USAGE: dump_indexeddb_details.py <ldb dir path> [blob dir path]` |

---

### 4. dump\_indexeddb\_db.py

Chromium IndexedDB LevelDB 데이터를 SQLite 데이터베이스로 덤프합니다. `dump_indexeddb_details.py`가 터미널 출력 전용인 것과 달리, 이 도구는 **모든 레코드(live + deleted)**를 SQLite에 저장하여 SQL로 쿼리할 수 있습니다.

#### 사용법

```bash
python tools_and_utilities/dump_indexeddb_db.py <leveldb_dir> [blob_dir] [out.db]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | IndexedDB LevelDB 디렉토리 경로 (예: `IndexedDB/origin_name.indexeddb.leveldb`) |
| `blob_dir` | X | IndexedDB blob 파일 디렉토리 경로 (예: `IndexedDB/origin_name.indexeddb.blob`) |
| `out.db` | X | 출력할 SQLite 파일 경로 (기본값: `indexeddb_dump.db`) |

#### 사용 예시

```bash
# blob 디렉토리 없이 기본 출력
python tools_and_utilities/dump_indexeddb_db.py "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.leveldb"

# blob 디렉토리와 출력 파일 지정
python tools_and_utilities/dump_indexeddb_db.py "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.leveldb" "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.blob" output.db
```

#### 출력 SQLite 스키마

- **databases** 테이블: 데이터베이스 목록 (db_number, name, origin)
- **object_stores** 테이블: 오브젝트 스토어 목록 (database_id, object_store_id, name)
- **records** 테이블: 전체 레코드 (key, value, is_live, ldb_seq_no, origin_file, error_msg)
- **records_view** 뷰: origin, db_name, store_name, key, value를 조인하여 ldb_seq_no 순으로 정렬

> **`dump_indexeddb_details.py`와의 차이점:** `details` 도구는 각 스토어의 첫 번째 레코드만 터미널에 출력하는 구조 확인용입니다. 이 도구는 **모든 레코드를 SQLite에 저장**하며, 역직렬화 오류가 발생한 레코드도 `error_msg` 컬럼에 기록하여 누락 없이 보존합니다.

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | LevelDB 매직 넘버가 유효하지 않을 때 | `invalid magic number in {file}` |
| `ValueError` | Blink 직렬화 데이터가 손상되었을 때 | `Blink type tag not present` |
| `TypeError` / `KeyError` | 오브젝트 스토어 접근 실패 시 | error_msg 컬럼에 기록 후 계속 진행 |
| 역직렬화 오류 | 레코드 값을 파싱할 수 없을 때 | error_msg 컬럼에 스택 트레이스 기록 |
| 인자 부족 | 인자가 1개 미만일 때 | `USAGE: dump_indexeddb_db.py <ldb dir path> [blob dir path] [out.db]` |

---

### 5. dump_leveldb.py

LevelDB 데이터베이스의 원시(raw) 레코드를 CSV 파일로 덤프합니다.

> **참고:** LevelDB의 key와 value는 바이너리 데이터이므로, 출력된 텍스트가 데이터의 전체 의미를 나타내지 않을 수 있습니다. 이 스크립트의 출력은 데이터의 미리보기로만 간주해야 합니다.

#### 사용법

```bash
python tools_and_utilities/dump_leveldb.py <leveldb_dir> [output.csv]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | LevelDB 디렉토리 경로 |
| `output.csv` | X | 출력 CSV 파일 경로 (기본값: `leveldb_dump.csv`) |

#### 사용 예시

```bash
# 기본 출력 파일명 사용
python tools_and_utilities/dump_leveldb.py "C:\Artifacts\Local Storage\leveldb"

# 출력 파일 지정
python tools_and_utilities/dump_leveldb.py "C:\Artifacts\Local Storage\leveldb" output.csv
```

#### 출력 CSV 컬럼

| 컬럼 | 설명 |
|------|------|
| `key-hex` | 키의 16진수 표현 |
| `key-text` | 키의 텍스트 표현 (iso-8859-1 디코딩) |
| `value-hex` | 값의 16진수 표현 |
| `value-text` | 값의 텍스트 표현 (iso-8859-1 디코딩) |
| `origin_file` | 원본 LevelDB 파일 경로 |
| `file_type` | 파일 유형 (ldb, log 등) |
| `offset` | 파일 내 오프셋 |
| `seq` | LevelDB 시퀀스 번호 |
| `state` | 레코드 상태 |
| `was_compressed` | 압축 여부 |

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | 입력 경로가 디렉토리가 아닐 때 | `in_dir is not a directory` |
| `ValueError` | LevelDB 파일의 매직 넘버가 유효하지 않을 때 | `invalid magic number in {file}` |
| `ValueError` | 블록 데이터를 완전히 읽을 수 없을 때 | `Could not read all of the block at offset {offset}` |
| `FileNotFoundError` | .ldb 또는 .log 파일이 누락되었을 때 | (파일 경로) |
| 인자 부족 | 인자가 1개 미만일 때 | `Usage: dump_leveldb.py <indir path> [outpath.csv]` |

---

### 6. dump\_leveldb\_v2\_db.py

LevelDB 데이터베이스의 원시(raw) 레코드를 **SQLite 데이터베이스**로 덤프합니다. `dump_leveldb.py`의 CSV 출력 방식을 보완한 버전으로, value를 ASCII·UTF-16-LE로 동시에 디코딩하여 저장합니다.

> **참고:** LevelDB의 key와 value는 바이너리 데이터이므로, 출력된 텍스트가 데이터의 전체 의미를 나타내지 않을 수 있습니다. 이 스크립트의 출력은 데이터의 미리보기로만 간주해야 합니다.

#### 사용법

```bash
python tools_and_utilities/dump_leveldb_v2_db.py <leveldb_dir> [output.db]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `leveldb_dir` | O | LevelDB 디렉토리 경로 |
| `output.db` | X | 출력 SQLite 파일 경로 (기본값: `leveldb_dump.db`) |

#### 사용 예시

```bash
# 기본 출력 파일명 사용
python tools_and_utilities/dump_leveldb_v2_db.py "C:\Artifacts\Local Storage\leveldb"

# 출력 파일 지정
python tools_and_utilities/dump_leveldb_v2_db.py "C:\Artifacts\Local Storage\leveldb" output.db
```

#### 출력 SQLite 스키마 (`records` 테이블)

| 컬럼 | 설명 |
|------|------|
| `key_hex` | 키의 16진수 표현 |
| `key_ascii` | 키의 ASCII 표현 (비출력 문자는 `.`으로 대체) |
| `value_hex` | 값의 16진수 표현 |
| `value_ascii` | 값의 ASCII 표현 (디코딩 성공 시), 실패 시 BLOB |
| `value_utf16le` | 값의 UTF-16-LE 표현 (ASCII 실패 시에만 시도) |
| `origin_file` | 원본 LevelDB 파일 경로 |
| `file_type` | 파일 유형 (ldb, log 등) |
| `offset` | 파일 내 오프셋 |
| `seq` | LevelDB 시퀀스 번호 |
| `state` | 레코드 상태 |
| `was_compressed` | 압축 여부 |

> **`dump_leveldb.py`와의 차이점:** `dump_leveldb.py`는 CSV로 출력하며 iso-8859-1 단일 인코딩을 사용합니다. 이 도구는 SQLite로 출력하고 ASCII와 UTF-16-LE를 모두 시도하며, ASCII 디코딩 실패 시 원본 바이너리(BLOB)를 그대로 보존합니다.

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | 입력 경로가 디렉토리가 아닐 때 | `in_dir is not a directory` |
| `ValueError` | LevelDB 파일의 매직 넘버가 유효하지 않을 때 | `invalid magic number in {file}` |
| `ValueError` | 블록 데이터를 완전히 읽을 수 없을 때 | `Could not read all of the block at offset {offset}` |
| `FileNotFoundError` | .ldb 또는 .log 파일이 누락되었을 때 | (파일 경로) |
| 인자 부족 | 인자가 1개 미만일 때 | `Usage: dump_leveldb_v2_db.py <indir path> [outpath.db]` |

---

### 7. ccl_chrome_audit.py

Chromium 프로필 폴더 전체를 감사(audit)하여 특정 도메인과 관련된 모든 아티팩트를 검색합니다. 여러 데이터 소스를 한 번에 분석합니다.

> **참고:** 현재 코드에서 `WINDOWS = False`로 하드코딩되어 있어 **쿠키 복호화 기능은 비활성화** 상태입니다. 그러나 `win32crypt` 및 `pycryptodome` 패키지는 파일 상단에서 임포트되므로, Windows 환경에서는 해당 패키지가 설치되어 있어야 합니다.

#### 사용법

```bash
python tools_and_utilities/ccl_chrome_audit.py <profile_folder> <url_pattern> [cache_folder]
```

#### 인자 설명

| 인자 | 필수 | 설명 |
|------|------|------|
| `profile_folder` | O | Chromium 프로필 폴더 경로 (예: `User Data/Default`) |
| `url_pattern` | O | URL 매칭을 위한 정규표현식 패턴 (예: `example\.com`) |
| `cache_folder` | X | 별도의 캐시 폴더 경로 (모바일 환경용) |

#### 사용 예시

```bash
# 특정 도메인 관련 전체 감사
python tools_and_utilities/ccl_chrome_audit.py "C:\Users\user\AppData\Local\Google\Chrome\User Data\Default" "example\.com"

# 별도 캐시 폴더 지정 (모바일)
python tools_and_utilities/ccl_chrome_audit.py "/path/to/profile" "target\.site" "/path/to/cache"
```

#### 감사 대상 (14개 Auditor)

| Auditor | 대상 경로 | 출력 컬럼 |
|---------|-----------|-----------|
| **Bookmarks** | `Bookmarks` | id, guid, path, url, added time |
| **History** | `History` | id, url, title, timestamp |
| **Downloads (History)** | `History` | id, guid, tab url, tab referrer url, target path, total bytes, mime-type, original mime-type, start time |
| **Downloads (Shared Proto DB)** | `shared_proto_db/` | id, guid, tab url, tab referrer url, target path, total bytes, mime-type, original mime-type, start time |
| **Favicons** | `Favicons` | id, page_url, favicon url |
| **Cache** | `Cache/Cache_Data/` | key, request time, response time, data stream 정보 |
| **Cookies** | `Cookies` 또는 `Network/Cookies` | ID, Host, Name, Value, Creation Time (복호화 비활성) |
| **Local Storage** | `Local Storage/leveldb/` | id, storage key, script key, value |
| **Session Storage** | `Session Storage/` | id, host, key, value |
| **IndexedDb** | `IndexedDB/` | id, origin, database, object store, key, value |
| **FileSystem** | `File System/` | Folder ID, Sequence Number, Name, Data Path, Storage Type |
| **Notifications** | `Platform Notifications/` | ID, Origin, Title, Body, Data, Timestamp |
| **Logins** | `Login Data`, `Login Data For Account` | ID, database, origin url, action url, username_value |
| **Snss** | `Sessions/` | file, offset, index, timestamp, title, url, original_request_url, referrer_url |

#### 출력 형식

각 Auditor별로 구분선과 함께 탭으로 구분된 결과가 출력됩니다:

```
------------------------------------------------------------------------
History
------------------------------------------------------------------------
id    url    title    timestamp
1     https://example.com    Example    2024-01-15 10:30:00
```

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ModuleNotFoundError` | `win32crypt` 또는 `pycryptodome` 미설치 시 | `No module named 'win32crypt'` |
| `IOError` | Local/Session Storage 경로가 디렉토리가 아닐 때 | `Input directory is not a directory` |
| `ValueError` | LevelDB 데이터 손상 시 | `invalid magic number in {file}` |
| `sqlite3.OperationalError` | SQLite DB 파일이 손상되었거나 접근 불가 시 | `database is locked` / `no such table` |
| `json.JSONDecodeError` | Bookmarks JSON 파싱 실패 시 | (JSON 파싱 에러 메시지) |
| `FileNotFoundError` | 아티팩트 파일이 존재하지 않을 때 | (해당 Auditor를 건너뜀) |
| 인자 오류 | 인자가 1개 미만일 때 (profile_folder만 입력해도 url_pattern 누락 시 오류) | `ccl_chrome_audit.py <chrome profile folder> <pattern for url matching> [cache folder]` |

---

### 8. benchmark.py

IndexedDB 파싱 성능을 측정하는 벤치마크 도구입니다.

#### 사용법

```bash
python tools_and_utilities/benchmark.py <leveldb_dir>
```

#### 인자 설명

| 인자 | 설명 |
|------|------|
| `leveldb_dir` | IndexedDB LevelDB 디렉토리 경로 |

#### 사용 예시

```bash
python tools_and_utilities/benchmark.py "C:\Artifacts\IndexedDB\https_example.com_0.indexeddb.leveldb"
```

#### 출력 형식

`dump_indexeddb_details.py`와 유사하게 데이터베이스 구조를 출력하며, 마지막에 소요 시간을 표시합니다:

```
------Database------
db_number=1; name=myDatabase; origin=https://example.com

    ---Object Stores---
    object_store_id=1; name=myStore
Elapsed time: 3 seconds.
```

#### 발생 가능한 에러

| 에러 | 발생 조건 | 메시지 예시 |
|------|-----------|-------------|
| `ValueError` | LevelDB 데이터 파일이 손상되었을 때 | `invalid magic number in {file}` |
| 인자 부족 | 인자가 1개 미만일 때 | `USAGE: benchmark.py <ldb dir path>` |

---

### 9. extras/

테스트 데이터 생성을 위한 HTML 파일 모음입니다. 브라우저에서 직접 열어 실행하면 IndexedDB / Web Storage 테스트 데이터를 생성할 수 있습니다. 도구 개발 및 파싱 검증 목적으로 사용합니다.

| 파일 | 설명 |
|------|------|
| `make_test_indexeddb.html` | 단일 IndexedDB 데이터베이스와 오브젝트 스토어를 생성하는 테스트 페이지 |
| `make_many_indexeddb_databases.html` | 여러 개의 IndexedDB 데이터베이스를 한 번에 생성하는 테스트 페이지 |
| `make_webstorage.html` | localStorage / sessionStorage 테스트 데이터를 생성하는 페이지 |

#### 사용 방법

1. Chrome/Chromium 브라우저에서 HTML 파일을 열거나 로컬 웹 서버를 통해 접근합니다.
2. 페이지의 버튼을 클릭하여 테스트 데이터를 생성합니다.
3. 브라우저를 닫고 해당 프로필의 IndexedDB 또는 Local Storage 경로에서 파싱 도구를 실행합니다.

---

## 에러 유형 및 대처 방법

### 공통 에러

#### 1. 입력 경로 관련 에러

```
IOError: Input directory is not a directory
```
- **원인:** 제공한 경로가 디렉토리가 아니거나 존재하지 않음
- **대처:** 경로가 올바른 LevelDB 디렉토리를 가리키는지 확인

```
ValueError: in_dir is not a directory
```
- **원인:** LevelDB 원시 읽기 시 디렉토리가 아닌 경로 전달
- **대처:** 입력 경로 재확인

#### 2. 출력 파일 관련 에러

```
ValueError: output database already exists
```
- **원인:** 지정한 출력 DB 파일이 이미 존재
- **대처:** 기존 파일을 삭제하거나 다른 출력 경로 지정

#### 3. LevelDB 파일 손상 에러

```
ValueError: invalid magic number in {file}
```
- **원인:** LevelDB 파일(.ldb/.log)의 매직 넘버가 유효하지 않음 (파일 손상)
- **대처:** 원본 아티팩트가 손상되지 않았는지 확인. 부분적으로 덮어쓰여진 파일일 수 있음

```
ValueError: Could not read all of the block at offset {offset}
```
- **원인:** LevelDB 블록 데이터가 잘려 있음
- **대처:** 파일이 완전하게 수집되었는지 확인

```
FileNotFoundError: {file_path}
```
- **원인:** LevelDB의 .ldb 또는 .log 파일이 누락됨
- **대처:** 아티팩트 수집 시 모든 파일이 포함되었는지 확인

#### 4. 데이터 디코딩 에러

```
UnicodeDecodeError
```
- **원인:** 레코드 값의 UTF-8/UTF-16 디코딩 실패
- **동작:** 대부분의 도구에서 경고 메시지를 출력하고 해당 레코드를 건너뛴 후 계속 진행
- **대처:** 일반적으로 무시해도 무방. 바이너리 데이터가 텍스트로 해석될 수 없는 경우 발생

#### 5. IndexedDB 관련 에러

```
ValueError: Blink type tag not present
```
- **원인:** Blink 직렬화 형식이 예상과 다름
- **대처:** 지원되지 않는 Chromium 버전의 데이터일 수 있음

```
NotImplementedError
```
- **원인:** 아직 구현되지 않은 키 타입이나 기능을 만남
- **대처:** 해당 레코드는 건너뛰어짐. 대부분의 경우 분석에 큰 영향 없음

#### 6. Session Storage 데이터 무결성 에러

```
ValueError: map_id collision
```
- **원인:** 동일한 map_id가 서로 다른 호스트에 매핑됨 (데이터 손상)
- **대처:** 아티팩트의 무결성 확인 필요

### 에러 발생 시 일반적인 확인 사항

1. **경로 확인:** 입력 경로가 올바른 Chromium 아티팩트 디렉토리를 가리키는지 확인
2. **파일 무결성:** 포렌식 수집 과정에서 파일이 손상되거나 누락되지 않았는지 확인
3. **권한 확인:** 읽기 권한이 있는지 확인
4. **Python 버전:** Python 3.9 이상 권장
5. **패키지 버전:** `ccl_chromium_reader` 패키지가 최신 버전인지 확인
