import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager

_db_path: Path | None = None


def init_db(db_path: Path | str) -> None:
    global _db_path
    _db_path = Path(db_path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.executescript(_SCHEMA)


def get_db_path() -> Path:
    if _db_path is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_path


@contextmanager
def _get_conn():
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    text_content TEXT NOT NULL,
    annotation TEXT DEFAULT '',
    moderation_verdict TEXT DEFAULT 'pending',
    source_url TEXT DEFAULT '',
    file_type TEXT DEFAULT '',
    media_descriptions TEXT DEFAULT '[]',
    class_type TEXT DEFAULT '',
    is_generated INTEGER DEFAULT 0,
    has_previous INTEGER DEFAULT 0,
    has_next INTEGER DEFAULT 0,
    previous_material_id INTEGER DEFAULT NULL,
    next_material_id INTEGER DEFAULT NULL,
    cluster_parallel INTEGER DEFAULT NULL,
    cluster_sequential INTEGER DEFAULT NULL,
    complexity_level TEXT DEFAULT NULL,
    estimated_time_hours REAL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (previous_material_id) REFERENCES materials(id),
    FOREIGN KEY (next_material_id) REFERENCES materials(id)
);

CREATE TABLE IF NOT EXISTS methodological_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    requirement_text TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS material_compliance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    requirement_id INTEGER NOT NULL,
    is_compliant INTEGER DEFAULT 0,
    details TEXT DEFAULT '',
    FOREIGN KEY (material_id) REFERENCES materials(id),
    FOREIGN KEY (requirement_id) REFERENCES methodological_requirements(id),
    UNIQUE(material_id, requirement_id)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    metrics TEXT DEFAULT '{}',
    data_hash TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer'
);
"""


# ── materials CRUD ──

def insert_material(
    subject: str,
    topic: str,
    text_content: str,
    annotation: str = "",
    source_url: str = "",
    file_type: str = "",
    media_descriptions: list | None = None,
    class_type: str = "",
    is_generated: bool = False,
) -> int:
    media = json.dumps(media_descriptions or [], ensure_ascii=False)
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO materials
               (subject, topic, text_content, annotation, source_url, file_type,
                media_descriptions, class_type, is_generated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (subject, topic, text_content, annotation, source_url, file_type,
             media, class_type, int(is_generated)),
        )
        return cur.lastrowid


def get_material(material_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    if row is None:
        return None
    return _row_to_material(row)


def get_all_materials() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM materials ORDER BY id").fetchall()
    return [_row_to_material(r) for r in rows]


def update_material(material_id: int, **fields) -> None:
    if not fields:
        return
    if "media_descriptions" in fields and isinstance(fields["media_descriptions"], list):
        fields["media_descriptions"] = json.dumps(fields["media_descriptions"], ensure_ascii=False)
    if "is_generated" in fields:
        fields["is_generated"] = int(fields["is_generated"])
    if "has_previous" in fields:
        fields["has_previous"] = int(fields["has_previous"])
    if "has_next" in fields:
        fields["has_next"] = int(fields["has_next"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [material_id]
    with _get_conn() as conn:
        conn.execute(
            f"UPDATE materials SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )


def upsert_material(source_url: str, **fields) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM materials WHERE source_url = ?", (source_url,)
        ).fetchone()
    if row:
        update_material(row["id"], **fields)
        return row["id"]
    return insert_material(source_url=source_url, **fields)


def delete_material(material_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))


def _row_to_material(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["media_descriptions"] = json.loads(d.get("media_descriptions") or "[]")
    d["is_generated"] = bool(d.get("is_generated"))
    d["has_previous"] = bool(d.get("has_previous"))
    d["has_next"] = bool(d.get("has_next"))
    return d


# ── methodological_requirements CRUD ──

def insert_requirement(category: str, requirement_text: str) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO methodological_requirements"
            " (category, requirement_text) VALUES (?, ?)",
            (category, requirement_text),
        )
        if cur.lastrowid == 0:
            row = conn.execute(
                "SELECT id FROM methodological_requirements WHERE requirement_text = ?",
                (requirement_text,),
            ).fetchone()
            return row["id"]
        return cur.lastrowid


def get_all_requirements() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM methodological_requirements ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


# ── material_compliance CRUD ──

def set_compliance(
    material_id: int,
    requirement_id: int,
    is_compliant: bool,
    details: str = "",
) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO material_compliance (material_id, requirement_id, is_compliant, details)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(material_id, requirement_id)
               DO UPDATE SET is_compliant = excluded.is_compliant, details = excluded.details""",
            (material_id, requirement_id, int(is_compliant), details),
        )
        return cur.lastrowid


def get_compliance_for_material(material_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM material_compliance WHERE material_id = ? ORDER BY requirement_id",
            (material_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_compliance_matrix() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT mc.*, mr.category, mr.requirement_text, m.subject, m.topic
               FROM material_compliance mc
               JOIN methodological_requirements mr ON mc.requirement_id = mr.id
               JOIN materials m ON mc.material_id = m.id
               ORDER BY mc.material_id, mc.requirement_id""",
        ).fetchall()
    return [dict(r) for r in rows]


# ── model_versions CRUD ──

def insert_model_version(
    model_name: str, version: int, file_path: str,
    metrics: dict | None = None, data_hash: str = ""
) -> int:
    m = json.dumps(metrics or {}, ensure_ascii=False)
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO model_versions (model_name, version, file_path, metrics, data_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (model_name, version, file_path, m, data_hash),
        )
        return cur.lastrowid


def get_latest_model(model_name: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_versions WHERE model_name = ? ORDER BY version DESC LIMIT 1",
            (model_name,),
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["metrics"] = json.loads(d.get("metrics") or "{}")
    return d


def get_all_model_versions(model_name: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM model_versions WHERE model_name = ? ORDER BY version",
            (model_name,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d.get("metrics") or "{}")
        result.append(d)
    return result


# ── users CRUD ──

def insert_user(username: str, password_hash: str, role: str = "viewer") -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        return cur.lastrowid


def get_user(username: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]
