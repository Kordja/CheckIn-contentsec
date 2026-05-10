"""
数据库建表 SQL。
使用 SQLite，统一由一个文件管理，避免散落各处的 CREATE TABLE。
"""

TABLES = {}

TABLES["student"] = """
CREATE TABLE IF NOT EXISTS student (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    student_id  TEXT    NOT NULL UNIQUE
);
"""

TABLES["face"] = """
CREATE TABLE IF NOT EXISTS face (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT    NOT NULL,
    encoding    BLOB,                       -- pickle 序列化的 128d 向量
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);
"""

TABLES["attendance"] = """
CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT    NOT NULL,
    time        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    status      TEXT    DEFAULT 'present',   -- present / late / leave
    liveness    INTEGER DEFAULT 0,           -- 0:failed 1:passed 2:suspicious_screen
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);
"""

TABLES["emotion"] = """
CREATE TABLE IF NOT EXISTS emotion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT    NOT NULL,
    time        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    emotion     TEXT    NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);
"""

TABLES["activity"] = """
CREATE TABLE IF NOT EXISTS activity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    time        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

TABLES["activity_record"] = """
CREATE TABLE IF NOT EXISTS activity_record (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT    NOT NULL,
    activity_id INTEGER NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(student_id),
    FOREIGN KEY (activity_id) REFERENCES activity(id)
);
"""


def get_all_sql():
    """返回所有建表语句列表（按依赖顺序）。"""
    return [
        TABLES["student"],
        TABLES["face"],
        TABLES["attendance"],
        TABLES["emotion"],
        TABLES["activity"],
        TABLES["activity_record"],
    ]
