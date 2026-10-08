from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

_DB_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


_PHOTO_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})")


def photo_timestamp_from_filename(filename: str, fallback: str | None = None) -> str | None:
    match = _PHOTO_TIMESTAMP.match(Path(filename).name)
    if not match:
        return fallback
    try:
        value = f"{match.group(1)}T{match.group(2)}:{match.group(3)}:{match.group(4)}"
        return datetime.fromisoformat(value).isoformat(timespec="seconds")
    except ValueError:
        return fallback


def history_db_path(config: dict[str, Any]) -> Path:
    path = Path(str(config.get("history_db_path") or "data/history.sqlite3")).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


@contextmanager
def _connect(config: dict[str, Any]) -> Iterator[sqlite3.Connection]:
    path = history_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(config: dict[str, Any]) -> None:
    with _DB_LOCK, _connect(config) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS deleted_captures (filename TEXT PRIMARY KEY)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                photo_filename TEXT,
                sensor_a_id TEXT,
                sensor_a_name TEXT,
                sensor_a_temp_c REAL,
                sensor_a_humidity_percent REAL,
                sensor_a_status TEXT,
                sensor_b_id TEXT,
                sensor_b_name TEXT,
                sensor_b_temp_c REAL,
                sensor_b_humidity_percent REAL,
                sensor_b_status TEXT,
                temp_delta_c REAL,
                humidity_delta_percent_points REAL,
                delta_warning INTEGER NOT NULL DEFAULT 0,
                light_mode TEXT,
                light_effective_on INTEGER,
                power_under_voltage INTEGER,
                cpu_temp_c REAL,
                ext5v_v REAL,
                raw_json TEXT NOT NULL
            )
            """
        )
        sensor_columns = {row[1] for row in conn.execute("PRAGMA table_info(sensor_samples)")}
        if "photo_filename" not in sensor_columns:
            conn.execute("ALTER TABLE sensor_samples ADD COLUMN photo_filename TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sensor_samples_timestamp ON sensor_samples(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sensor_samples_photo ON sensor_samples(photo_filename)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                filename TEXT,
                reason TEXT,
                ok INTEGER NOT NULL DEFAULT 1,
                message TEXT,
                raw_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS colony_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                photo_timestamp TEXT NOT NULL,
                backend TEXT NOT NULL,
                status TEXT NOT NULL,
                colony_count INTEGER,
                analyzed_at TEXT NOT NULL,
                duration_seconds REAL,
                details_json TEXT NOT NULL,
                UNIQUE(filename, backend)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_colony_photo_time ON colony_results(photo_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_colony_filename ON colony_results(filename)")
        conn.execute("DELETE FROM colony_results WHERE backend = 'blenny'")


def _sensor_at(sensors: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if index < len(sensors) and isinstance(sensors[index], dict):
        return sensors[index]
    return {}


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def record_sensor_sample(
    config: dict[str, Any], hardware: dict[str, Any], photo_filename: str | None = None
) -> dict[str, Any]:
    init_db(config)
    timestamp = photo_timestamp_from_filename(photo_filename or "", now_iso())
    sensor_block = hardware.get("sensors") if isinstance(hardware, dict) else {}
    if not isinstance(sensor_block, dict):
        sensor_block = {}
    sensors = sensor_block.get("sensors") if isinstance(sensor_block.get("sensors"), list) else []
    delta = sensor_block.get("delta") if isinstance(sensor_block.get("delta"), dict) else {}
    raw_light = sensor_block.get("raw_light") if isinstance(sensor_block.get("raw_light"), dict) else {}
    power = hardware.get("power") if isinstance(hardware.get("power"), dict) else {}
    a = _sensor_at(sensors, 0)
    b = _sensor_at(sensors, 1)
    row = {
        "timestamp": timestamp,
        "photo_filename": photo_filename,
        "sensor_a_id": a.get("id"),
        "sensor_a_name": a.get("name"),
        "sensor_a_temp_c": _num(a.get("temperature_c")),
        "sensor_a_humidity_percent": _num(a.get("humidity_percent")),
        "sensor_a_status": a.get("status"),
        "sensor_b_id": b.get("id"),
        "sensor_b_name": b.get("name"),
        "sensor_b_temp_c": _num(b.get("temperature_c")),
        "sensor_b_humidity_percent": _num(b.get("humidity_percent")),
        "sensor_b_status": b.get("status"),
        "temp_delta_c": _num(delta.get("temperature_delta_c")),
        "humidity_delta_percent_points": _num(delta.get("humidity_delta_percent_points")),
        "delta_warning": 1 if delta.get("warning") else 0,
        "light_mode": raw_light.get("mode"),
        "light_effective_on": 1 if raw_light.get("effective_on") else 0,
        "power_under_voltage": 1 if power.get("under_voltage") else 0,
        "cpu_temp_c": _num(power.get("cpu_temp_c")),
        "ext5v_v": _num(power.get("ext5v_v")),
        "raw_json": json.dumps(hardware, ensure_ascii=False, separators=(",", ":")),
    }
    with _DB_LOCK, _connect(config) as conn:
        if photo_filename and conn.execute("SELECT 1 FROM deleted_captures WHERE filename = ?", (photo_filename,)).fetchone():
            return row
        cursor = conn.execute(
            """
            INSERT INTO sensor_samples (
                timestamp, photo_filename, sensor_a_id, sensor_a_name, sensor_a_temp_c, sensor_a_humidity_percent, sensor_a_status,
                sensor_b_id, sensor_b_name, sensor_b_temp_c, sensor_b_humidity_percent, sensor_b_status,
                temp_delta_c, humidity_delta_percent_points, delta_warning, light_mode, light_effective_on,
                power_under_voltage, cpu_temp_c, ext5v_v, raw_json
            ) VALUES (
                :timestamp, :photo_filename, :sensor_a_id, :sensor_a_name, :sensor_a_temp_c, :sensor_a_humidity_percent, :sensor_a_status,
                :sensor_b_id, :sensor_b_name, :sensor_b_temp_c, :sensor_b_humidity_percent, :sensor_b_status,
                :temp_delta_c, :humidity_delta_percent_points, :delta_warning, :light_mode, :light_effective_on,
                :power_under_voltage, :cpu_temp_c, :ext5v_v, :raw_json
            )
            """,
            row,
        )
        row["id"] = cursor.lastrowid
    return row


def record_event(config: dict[str, Any], event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    init_db(config)
    payload = dict(payload or {})
    row = {
        "timestamp": str(payload.get("timestamp") or now_iso()),
        "event_type": event_type,
        "filename": payload.get("filename"),
        "reason": payload.get("reason"),
        "ok": 1 if payload.get("ok", True) else 0,
        "message": payload.get("message") or payload.get("error"),
        "raw_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }
    with _DB_LOCK, _connect(config) as conn:
        cursor = conn.execute(
            """
            INSERT INTO events (timestamp, event_type, filename, reason, ok, message, raw_json)
            VALUES (:timestamp, :event_type, :filename, :reason, :ok, :message, :raw_json)
            """,
            row,
        )
        row["id"] = cursor.lastrowid
    return row


def _range_clause(start: str | None, end: str | None) -> tuple[str, list[Any]]:
    clause = "1=1"
    args: list[Any] = []
    if start:
        clause += " AND timestamp >= ?"
        args.append(start)
    if end:
        clause += " AND timestamp <= ?"
        args.append(end)
    return clause, args


def query_sensor_samples(
    config: dict[str, Any],
    start: str | None = None,
    end: str | None = None,
    limit: int = 500,
    *,
    photo_only: bool = False,
) -> list[dict[str, Any]]:
    init_db(config)
    limit = min(5000, max(1, int(limit)))
    clause, args = _range_clause(start, end)
    if photo_only:
        clause += " AND photo_filename IS NOT NULL AND photo_filename != ''"
    with _DB_LOCK, _connect(config) as conn:
        rows = conn.execute(
            f"SELECT * FROM sensor_samples WHERE {clause} ORDER BY timestamp ASC LIMIT ?",
            [*args, limit],
        ).fetchall()
    return [dict(row) for row in rows]


def query_events(config: dict[str, Any], start: str | None = None, end: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    init_db(config)
    limit = min(1000, max(1, int(limit)))
    clause, args = _range_clause(start, end)
    with _DB_LOCK, _connect(config) as conn:
        rows = conn.execute(
            f"SELECT id, timestamp, event_type, filename, reason, ok, message FROM events WHERE {clause} ORDER BY timestamp DESC LIMIT ?",
            [*args, limit],
        ).fetchall()
    return [dict(row) for row in rows]


def record_colony_result(
    config: dict[str, Any],
    *,
    filename: str,
    photo_timestamp: str,
    backend: str,
    status: str,
    count: int | None,
    duration_seconds: float | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db(config)
    row = {
        "filename": filename,
        "photo_timestamp": photo_timestamp,
        "backend": backend,
        "status": status,
        "colony_count": None if count is None else int(count),
        "analyzed_at": now_iso(),
        "duration_seconds": _num(duration_seconds),
        "details_json": json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
    }
    with _DB_LOCK, _connect(config) as conn:
        if filename and conn.execute("SELECT 1 FROM deleted_captures WHERE filename = ?", (filename,)).fetchone():
            return row
        conn.execute(
            """
            INSERT INTO colony_results (
                filename, photo_timestamp, backend, status, colony_count,
                analyzed_at, duration_seconds, details_json
            ) VALUES (
                :filename, :photo_timestamp, :backend, :status, :colony_count,
                :analyzed_at, :duration_seconds, :details_json
            )
            ON CONFLICT(filename, backend) DO UPDATE SET
                photo_timestamp=excluded.photo_timestamp,
                status=excluded.status,
                colony_count=excluded.colony_count,
                analyzed_at=excluded.analyzed_at,
                duration_seconds=excluded.duration_seconds,
                details_json=excluded.details_json
            """,
            row,
        )
    row["count"] = row.pop("colony_count")
    row["details"] = json.loads(row.pop("details_json"))
    return row


def colony_result_exists(config: dict[str, Any], filename: str, backend: str) -> bool:
    init_db(config)
    with _DB_LOCK, _connect(config) as conn:
        row = conn.execute(
            "SELECT 1 FROM colony_results WHERE filename = ? AND backend = ? AND status != 'error' LIMIT 1",
            (filename, backend),
        ).fetchone()
    return row is not None


def query_colony_results(
    config: dict[str, Any], start: str | None = None, end: str | None = None, limit: int = 5000
) -> list[dict[str, Any]]:
    init_db(config)
    limit = min(10000, max(1, int(limit)))
    clause = "1=1"
    args: list[Any] = []
    if start:
        clause += " AND photo_timestamp >= ?"
        args.append(start)
    if end:
        clause += " AND photo_timestamp <= ?"
        args.append(end)
    with _DB_LOCK, _connect(config) as conn:
        rows = conn.execute(
            f"""
            SELECT filename, photo_timestamp, backend, status, colony_count AS count,
                   analyzed_at, duration_seconds, details_json
            FROM colony_results WHERE {clause}
            ORDER BY photo_timestamp ASC, backend ASC LIMIT ?
            """,
            [*args, limit],
        ).fetchall()
    result = []
    for raw in rows:
        item = dict(raw)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        result.append(item)
    return result


def colony_results_by_filename(
    config: dict[str, Any], filenames: list[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    names = [str(name) for name in filenames if str(name)]
    if not names:
        return {}
    init_db(config)
    placeholders = ",".join("?" for _ in names)
    with _DB_LOCK, _connect(config) as conn:
        rows = conn.execute(
            f"""
            SELECT filename, backend, status, colony_count AS count, analyzed_at,
                   duration_seconds, details_json
            FROM colony_results WHERE filename IN ({placeholders})
            """,
            names,
        ).fetchall()
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for raw in rows:
        item = dict(raw)
        filename = str(item.pop("filename"))
        backend = str(item.pop("backend"))
        item["details"] = json.loads(item.pop("details_json") or "{}")
        result.setdefault(filename, {})[backend] = item
    return result


def photo_history_by_filename(
    config: dict[str, Any], filenames: list[str]
) -> dict[str, dict[str, Any]]:
    """Return capture-time sensor and colony metadata for specific photos."""
    names = list(dict.fromkeys(str(name) for name in filenames if str(name)))
    if not names:
        return {}

    init_db(config)
    records: dict[str, dict[str, Any]] = {
        name: {
            "filename": name,
            "timestamp": photo_timestamp_from_filename(name),
            "counts": {},
        }
        for name in names
    }

    # Keep each query comfortably below SQLite's parameter limit. If an old
    # database contains duplicate linked samples, the newest row wins.
    with _DB_LOCK, _connect(config) as conn:
        for offset in range(0, len(names), 500):
            batch = names[offset : offset + 500]
            placeholders = ",".join("?" for _ in batch)
            rows = conn.execute(
                f"""
                SELECT id, timestamp, photo_filename,
                       sensor_a_temp_c, sensor_a_humidity_percent,
                       sensor_b_temp_c, sensor_b_humidity_percent,
                       temp_delta_c, humidity_delta_percent_points, delta_warning
                FROM sensor_samples
                WHERE photo_filename IN ({placeholders})
                ORDER BY id ASC
                """,
                batch,
            ).fetchall()
            for raw in rows:
                sample = dict(raw)
                filename = str(sample.get("photo_filename") or "")
                record = records[filename]
                record.update(
                    {
                        "timestamp": photo_timestamp_from_filename(
                            filename, str(sample.get("timestamp") or "")
                        ),
                        "sensor_a_temp_c": sample.get("sensor_a_temp_c"),
                        "sensor_a_humidity_percent": sample.get("sensor_a_humidity_percent"),
                        "sensor_b_temp_c": sample.get("sensor_b_temp_c"),
                        "sensor_b_humidity_percent": sample.get("sensor_b_humidity_percent"),
                        "temp_delta_c": sample.get("temp_delta_c"),
                        "humidity_delta_percent_points": sample.get("humidity_delta_percent_points"),
                        "delta_warning": sample.get("delta_warning"),
                    }
                )

    colony_rows = colony_results_by_filename(config, names)
    for filename, backends in colony_rows.items():
        records[filename]["counts"] = backends
    return records


def _average_token(values: list[Any]) -> str:
    numbers = [number for value in values if (number := _num(value)) is not None]
    if not numbers:
        return "NA"
    return f"{sum(numbers) / len(numbers):.1f}"


def _count_token(result: dict[str, Any] | None) -> str:
    if not result:
        return "NA"
    count = result.get("count")
    if count is not None:
        try:
            return str(int(count))
        except (TypeError, ValueError):
            pass
    if str(result.get("status") or "").lower() == "error":
        return "ERR"
    return "NA"


def informative_photo_filename(filename: str, metadata: dict[str, Any] | None = None) -> str:
    """Build a short export name without changing the stored photo name."""
    metadata = metadata or {}
    source = Path(filename).name
    match = _PHOTO_TIMESTAMP.match(source)
    timestamp = photo_timestamp_from_filename(source, str(metadata.get("timestamp") or ""))
    try:
        prefix = datetime.fromisoformat(str(timestamp)).strftime("%Y%m%d-%H%M%S")
    except (TypeError, ValueError):
        prefix = re.sub(r"[^A-Za-z0-9-]+", "-", Path(source).stem).strip("-") or "photo"

    # Preserve an optional camera-side sequence suffix so two captures from the
    # same second do not receive the same download name.
    if match:
        remainder = Path(source).stem[match.end() :].strip("_-. ")
        remainder = re.sub(r"[^A-Za-z0-9-]+", "-", remainder).strip("-")
        if remainder:
            prefix = f"{prefix}-{remainder}"

    counts = metadata.get("counts") if isinstance(metadata.get("counts"), dict) else {}
    opencfu = _count_token(counts.get("opencfu"))
    mcount = _count_token(counts.get("mcount"))
    temperature = _average_token(
        [metadata.get("sensor_a_temp_c"), metadata.get("sensor_b_temp_c")]
    )
    humidity = _average_token(
        [metadata.get("sensor_a_humidity_percent"), metadata.get("sensor_b_humidity_percent")]
    )
    suffix = Path(source).suffix.lower() or ".jpg"
    return f"{prefix}_O{opencfu}_M{mcount}_T{temperature}_H{humidity}{suffix}"


def delete_colony_results(config: dict[str, Any], filenames: list[str]) -> None:
    names = [str(name) for name in filenames if str(name)]
    if not names:
        return
    init_db(config)
    placeholders = ",".join("?" for _ in names)
    with _DB_LOCK, _connect(config) as conn:
        conn.execute(f"DELETE FROM colony_results WHERE filename IN ({placeholders})", names)


def _photo_index_sql(start: str | None, end: str | None) -> tuple[str, list[Any]]:
    clause, args = _range_clause(start, end)
    return (
        f"""
        WITH candidates AS (
            SELECT photo_filename AS filename, timestamp
            FROM sensor_samples
            WHERE photo_filename IS NOT NULL AND photo_filename != ''
            UNION ALL
            SELECT filename, photo_timestamp AS timestamp
            FROM colony_results
            WHERE filename IS NOT NULL AND filename != ''
        ), photos AS (
            SELECT filename, MIN(timestamp) AS timestamp
            FROM candidates
            GROUP BY filename
        )
        SELECT filename, timestamp FROM photos WHERE {clause}
        """,
        args,
    )


def photo_history_summary(
    config: dict[str, Any], start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    """Return exact photo-record bounds without transferring every record."""
    init_db(config)
    index_sql, args = _photo_index_sql(start, end)
    with _DB_LOCK, _connect(config) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS total, MIN(timestamp) AS start, MAX(timestamp) AS end FROM ({index_sql})",
            args,
        ).fetchone()
    return {"total": int(row["total"] or 0), "start": row["start"], "end": row["end"]}


def query_photo_history(
    config: dict[str, Any], start: str | None = None, end: str | None = None,
    limit: int = 5000, *, newest: bool = False,
) -> list[dict[str, Any]]:
    """Return joined capture metadata; ``limit <= 0`` means no row limit."""
    init_db(config)
    index_sql, args = _photo_index_sql(start, end)
    order = "DESC" if newest else "ASC"
    limit_sql = ""
    if int(limit) > 0:
        limit_sql = " LIMIT ?"
        args.append(min(100000, max(1, int(limit))))
    with _DB_LOCK, _connect(config) as conn:
        rows = conn.execute(f"{index_sql} ORDER BY timestamp {order}, filename {order}{limit_sql}", args).fetchall()

    index = [dict(row) for row in rows]
    records = photo_history_by_filename(config, [str(row["filename"]) for row in index])
    for row in index:
        records[str(row["filename"])]["timestamp"] = photo_timestamp_from_filename(
            str(row["filename"]), str(row["timestamp"] or "")
        )
    return sorted(records.values(), key=lambda item: (str(item.get("timestamp") or ""), item["filename"]))


def export_photo_history_csv(
    config: dict[str, Any], start: str | None = None, end: str | None = None, limit: int = 5000
) -> str:
    records = query_photo_history(config, start=start, end=end, limit=limit)
    rows = []
    for record in records:
        opencfu = record.get("counts", {}).get("opencfu", {})
        mcount = record.get("counts", {}).get("mcount", {})
        rows.append(
            {
                "timestamp": record.get("timestamp"),
                "filename": record.get("filename"),
                "sensor_a_temp_c": record.get("sensor_a_temp_c"),
                "sensor_a_humidity_percent": record.get("sensor_a_humidity_percent"),
                "sensor_b_temp_c": record.get("sensor_b_temp_c"),
                "sensor_b_humidity_percent": record.get("sensor_b_humidity_percent"),
                "opencfu_count": opencfu.get("count"),
                "opencfu_status": opencfu.get("status"),
                "mcount_count": mcount.get("count"),
                "mcount_status": mcount.get("status"),
            }
        )
    output = io.StringIO()
    fieldnames = [
        "timestamp",
        "filename",
        "sensor_a_temp_c",
        "sensor_a_humidity_percent",
        "sensor_b_temp_c",
        "sensor_b_humidity_percent",
        "opencfu_count",
        "opencfu_status",
        "mcount_count",
        "mcount_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def delete_capture_records(config: dict[str, Any], filenames: list[str]) -> None:
    """Delete capture-linked data atomically and reject late analysis writes."""
    names = list(dict.fromkeys(str(name) for name in filenames if str(name)))
    if not names:
        return
    init_db(config)
    with _DB_LOCK, _connect(config) as conn:
        for name in names:
            conn.execute("INSERT OR IGNORE INTO deleted_captures(filename) VALUES (?)", (name,))
            conn.execute("DELETE FROM colony_results WHERE filename = ?", (name,))
            conn.execute("DELETE FROM sensor_samples WHERE photo_filename = ?", (name,))
