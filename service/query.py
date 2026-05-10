"""
查询服务：考勤查询、情绪统计、活动统计、导出 Excel
导出 = 查询 + 格式转换，共用一套 SQL 逻辑
"""

import pandas as pd
import os
from db.database import (
    query_attendance, query_emotion, get_emotion_stats,
    query_activity, get_activity_stats, get_all_students,
)


def get_attendance(date: str = None, student_id: str = None) -> dict:
    """查询考勤记录。"""
    rows = query_attendance(date=date, student_id=student_id)
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "total": len(rows),
            "records": rows,
        }
    }


def get_emotion(date: str = None, student_id: str = None) -> dict:
    """查询情绪记录 + 统计。"""
    rows = query_emotion(date=date, student_id=student_id)
    stats = get_emotion_stats(date=date, student_id=student_id)
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "total": len(rows),
            "records": rows,
            "stats": stats,
        }
    }


def get_activity(activity_id: int = None) -> dict:
    """查询活动及参与详情。"""
    rows = query_activity(activity_id=activity_id)
    stats = get_activity_stats()
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "activities": rows,
            "stats": stats,
        }
    }


def export_attendance(date: str = None, student_id: str = None,
                       fmt: str = "excel") -> str:
    """
    导出考勤记录为文件。
    fmt: "excel" → .xlsx, "csv" → .csv
    返回生成的文件路径。
    """
    rows = query_attendance(date=date, student_id=student_id)
    if not rows:
        return None

    df = pd.DataFrame(rows)
    col_map = {
        "id": "序号", "student_id": "学号", "name": "姓名",
        "time": "时间", "status": "状态", "liveness": "活体验证"
    }
    df.rename(columns=col_map, inplace=True)

    export_dir = os.path.join(
        os.path.dirname(__file__), "..", "data", "exports"
    )
    os.makedirs(export_dir, exist_ok=True)

    if fmt == "csv":
        filepath = os.path.join(export_dir, "attendance_export.csv")
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
    else:
        filepath = os.path.join(export_dir, "attendance_export.xlsx")
        df.to_excel(filepath, index=False, engine="openpyxl")

    return filepath


def get_student_list() -> dict:
    """返回所有已注册学生。"""
    rows = get_all_students()
    return {
        "code": 0,
        "msg": "ok",
        "data": {"total": len(rows), "students": rows},
    }
