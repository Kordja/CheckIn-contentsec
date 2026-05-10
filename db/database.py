"""
数据库操作封装（SQLite）。
提供业务层所需所有 CRUD 接口，不涉及 CV 逻辑和 HTTP。
"""

from __future__ import annotations
import sqlite3
import os
from contextlib import contextmanager
from db.schema import get_all_sql

_db_path = None


def init_db(db_path: str = None):
    """
    初始化数据库连接路径并建表。每个进程启动时调用一次。
    如不传路径，默认使用项目 data/checkin.db。
    """
    global _db_path
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "checkin.db")
    _db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

    with _get_conn() as conn:
        for sql in get_all_sql():
            conn.execute(sql)
    return _db_path


def _get_conn():
    """获取数据库连接。启用外键和 WAL 模式以支持并发读。"""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def _transaction():
    """事务上下文管理器，自动 commit/rollback。"""
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---- 学生管理 ----

def add_student(name: str, student_id: str) -> bool:
    """新增学生，已存在返回 False。"""
    try:
        with _transaction() as conn:
            conn.execute(
                "INSERT INTO student (name, student_id) VALUES (?, ?)",
                (name, student_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_student(student_id: str) -> dict | None:
    """根据学号查学生，返回 dict 或 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, student_id FROM student WHERE student_id = ?",
            (student_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_students() -> list[dict]:
    """返回所有学生列表。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, student_id FROM student ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def update_student_name(student_id: str, new_name: str) -> bool:
    """更新学生姓名，返回是否成功。"""
    with _transaction() as conn:
        cursor = conn.execute(
            "UPDATE student SET name = ? WHERE student_id = ?",
            (new_name, student_id)
        )
        return cursor.rowcount > 0


def delete_student(student_id: str) -> bool:
    """删除学生及其关联的人脸编码和考勤记录。"""
    with _transaction() as conn:
        conn.execute("DELETE FROM face WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM emotion WHERE student_id = ?", (student_id,))
        conn.execute(
            "DELETE FROM activity_record WHERE student_id = ?", (student_id,)
        )
        cursor = conn.execute(
            "DELETE FROM student WHERE student_id = ?", (student_id,)
        )
        return cursor.rowcount > 0


# ---- 考勤记录 ----

def save_attendance(student_id: str, status="present", liveness=0) -> int:
    """保存一条考勤记录，返回记录 ID。"""
    with _transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO attendance (student_id, status, liveness) VALUES (?, ?, ?)",
            (student_id, status, liveness)
        )
        return cursor.lastrowid


def query_attendance(date: str = None, student_id: str = None) -> list[dict]:
    """
    查询考勤记录。
    date 格式: 'YYYY-MM-DD'，为空则查全部。
    student_id 为空则查所有学生。
    """
    sql = """
        SELECT a.id, a.student_id, s.name, a.time, a.status, a.liveness
        FROM attendance a
        LEFT JOIN student s ON a.student_id = s.student_id
        WHERE 1=1
    """
    params = []
    if date:
        sql += " AND date(a.time) = ?"
        params.append(date)
    if student_id:
        sql += " AND a.student_id = ?"
        params.append(student_id)
    sql += " ORDER BY a.time DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Python 端关联最近的 emotion 记录
    records = []
    for r in rows:
        rec = dict(r)
        emo_row = conn.execute("""
            SELECT emotion FROM emotion
            WHERE student_id = ?
            ORDER BY abs(julianday(time) - julianday(?)) ASC
            LIMIT 1
        """, (rec["student_id"], rec["time"])).fetchone()
        rec["emotion"] = emo_row["emotion"] if emo_row else None
        records.append(rec)

    return records


# ---- 情绪记录 ----

def save_emotion(student_id: str, emotion: str) -> int:
    """保存一条情绪记录，返回记录 ID。"""
    with _transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO emotion (student_id, emotion) VALUES (?, ?)",
            (student_id, emotion)
        )
        return cursor.lastrowid


def query_emotion(date: str = None, student_id: str = None) -> list[dict]:
    """
    查询情绪记录，支持日期和学号筛选。
    """
    sql = """
        SELECT e.id, e.student_id, s.name, e.time, e.emotion
        FROM emotion e
        LEFT JOIN student s ON e.student_id = s.student_id
        WHERE 1=1
    """
    params = []
    if date:
        sql += " AND date(e.time) = ?"
        params.append(date)
    if student_id:
        sql += " AND e.student_id = ?"
        params.append(student_id)
    sql += " ORDER BY e.time DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_emotion_stats(date: str = None, student_id: str = None) -> list[dict]:
    """按情绪类型统计数量，支持日期和学号筛选。"""
    sql = """
        SELECT emotion, COUNT(*) as count
        FROM emotion
        WHERE 1=1
    """
    params = []
    if date:
        sql += " AND date(time) = ?"
        params.append(date)
    if student_id:
        sql += " AND student_id = ?"
        params.append(student_id)
    sql += " GROUP BY emotion ORDER BY count DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---- 活动管理 ----

def create_activity(name: str) -> int:
    """创建活动，返回活动 ID。"""
    with _transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO activity (name) VALUES (?)", (name,)
        )
        return cursor.lastrowid


def add_activity_record(student_id: str, activity_id: int) -> bool:
    """添加一条活动参与记录。"""
    try:
        with _transaction() as conn:
            conn.execute(
                "INSERT INTO activity_record (student_id, activity_id) VALUES (?, ?)",
                (student_id, activity_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def query_activity(activity_id: int = None, date: str = None,
                   name: str = None, date_start: str = None,
                   date_end: str = None) -> list[dict]:
    """查询活动及参与人数，支持日期、名称模糊搜索和时间段。"""
    if activity_id:
        sql = """
            SELECT a.id as activity_id, a.name, a.time, ar.student_id, s.name as student_name
            FROM activity a
            LEFT JOIN activity_record ar ON a.id = ar.activity_id
            LEFT JOIN student s ON ar.student_id = s.student_id
            WHERE a.id = ?
            ORDER BY s.name
        """
        with _get_conn() as conn:
            rows = conn.execute(sql, (activity_id,)).fetchall()
        return [dict(r) for r in rows]
    # 活动列表（聚合统计 + 筛选）
    sql = """
        SELECT a.id, a.name, a.time,
               COUNT(ar.id) as participant_count
        FROM activity a
        LEFT JOIN activity_record ar ON a.id = ar.activity_id
        WHERE 1=1
    """
    params = []
    if date:
        sql += " AND date(a.time) = ?"
        params.append(date)
    if date_start:
        sql += " AND date(a.time) >= ?"
        params.append(date_start)
    if date_end:
        sql += " AND date(a.time) <= ?"
        params.append(date_end)
    if name:
        sql += " AND a.name LIKE ?"
        params.append(f"%{name}%")
    sql += " GROUP BY a.id ORDER BY a.time DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_activity_freq_stats(activity_ids: list = None) -> list[dict]:
    """统计学生在指定活动中的参与频次，按次数降序。空列表=全部活动。"""
    if activity_ids is not None and len(activity_ids) == 0:
        activity_ids = None
    if activity_ids:
        placeholders = ",".join("?" * len(activity_ids))
        sql = f"""
            SELECT ar.student_id, s.name, COUNT(*) as count
            FROM activity_record ar
            LEFT JOIN student s ON ar.student_id = s.student_id
            WHERE ar.activity_id IN ({placeholders})
            GROUP BY ar.student_id
            ORDER BY count DESC
        """
        with _get_conn() as conn:
            rows = conn.execute(sql, activity_ids).fetchall()
    else:
        sql = """
            SELECT ar.student_id, s.name, COUNT(*) as count
            FROM activity_record ar
            LEFT JOIN student s ON ar.student_id = s.student_id
            GROUP BY ar.student_id
            ORDER BY count DESC
        """
        with _get_conn() as conn:
            rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_merged_activity_participants(activity_ids: list) -> list[dict]:
    """获取指定活动的全部参与人员明细（用于合并导出）。"""
    if not activity_ids:
        return []
    placeholders = ",".join("?" * len(activity_ids))
    sql = f"""
        SELECT a.name as activity_name, a.time as activity_time,
               ar.student_id, s.name as student_name
        FROM activity_record ar
        JOIN activity a ON ar.activity_id = a.id
        LEFT JOIN student s ON ar.student_id = s.student_id
        WHERE ar.activity_id IN ({placeholders})
        ORDER BY a.time DESC, s.name
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, activity_ids).fetchall()
    return [dict(r) for r in rows]


def delete_activity(activity_id: int) -> bool:
    """删除活动及其关联的参与记录。"""
    with _transaction() as conn:
        conn.execute("DELETE FROM activity_record WHERE activity_id = ?",
                     (activity_id,))
        cursor = conn.execute("DELETE FROM activity WHERE id = ?", (activity_id,))
        return cursor.rowcount > 0


def get_activity_stats() -> dict:
    """返回活动统计概览。"""
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
        total_records = conn.execute(
            "SELECT COUNT(*) FROM activity_record"
        ).fetchone()[0]
    return {"total_activities": total, "total_participations": total_records}


# ---- 工具 ----

def export_attendance_raw(date: str = None, student_id: str = None) -> list[dict]:
    """
    与 query_attendance 共用同一 SQL 逻辑，
    区别是不限制返回条数，供导出使用。
    """
    return query_attendance(date=date, student_id=student_id)
