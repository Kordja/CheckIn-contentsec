"""
Flask API 路由定义。
统一返回格式: {"code": 0, "msg": "ok", "data": {...}}
"""

from __future__ import annotations
import os
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from service.attendance import process_attendance
from service.group import process_group
from service.query import (
    get_attendance, get_emotion, get_activity,
    export_attendance, get_student_list,
)
from cv_core.recognizer import register_face, save_encodings, load_encodings
from cv_core.face_detection import detect_faces
from db.database import add_student, delete_student, get_student, query_activity as db_query_activity

api = Blueprint("api", __name__, url_prefix="/api")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_image_from_request() -> np.ndarray | None:
    """从 multipart/form-data 的 'image' 字段读取 OpenCV 图像。"""
    if "image" not in request.files:
        return None
    file = request.files["image"]
    if file.filename == "" or not _allowed_file(file.filename):
        return None
    data = file.read()
    nparr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


def _read_images_from_request() -> list:
    """从 multipart/form-data 的 'frames' 字段读取多帧图像列表。"""
    files = request.files.getlist("frames")
    images = []
    for file in files:
        if file.filename == "" or not _allowed_file(file.filename):
            continue
        data = file.read()
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            images.append(img)
    return images

@api.route("/attendance", methods=["POST"])
def attendance():
    """
    POST /api/attendance
    multipart/form-data: frames=<file1>&frames=<file2>...（多帧连续图像）
    """
    images = _read_images_from_request()
    # 兼容单帧旧接口
    if not images:
        img = _read_image_from_request()
        if img is not None:
            images = [img]

    if not images:
        return jsonify({"code": 1, "msg": "无效图片或文件类型不支持", "data": None}), 400

    result = process_attendance(images)
    status_code = 200 if result["code"] == 0 else 400
    return jsonify(result), status_code


# ---- 合照 ----

@api.route("/group", methods=["POST"])
def group():
    """
    POST /api/group
    multipart/form-data: image=<file>, activity_name=<str>（可选，默认当天日期）
    """
    img = _read_image_from_request()
    if img is None:
        return jsonify({"code": 1, "msg": "无效图片或文件类型不支持", "data": None}), 400

    activity_name = request.form.get("activity_name", "").strip()

    result = process_group(img, activity_name)
    status_code = 200 if result["code"] == 0 else 400
    return jsonify(result), status_code


# ---- 查询 ----

@api.route("/attendance", methods=["GET"])
def query_attendance():
    """
    GET /api/attendance?date=YYYY-MM-DD&student_id=xxx
    """
    date = request.args.get("date")
    student_id = request.args.get("student_id")
    result = get_attendance(date=date, student_id=student_id)
    return jsonify(result)


@api.route("/emotion", methods=["GET"])
def query_emotion():
    """
    GET /api/emotion?date=YYYY-MM-DD&student_id=xxx
    """
    date = request.args.get("date")
    student_id = request.args.get("student_id")
    result = get_emotion(date=date, student_id=student_id)
    return jsonify(result)


@api.route("/activity", methods=["GET"])
def query_activity():
    """
    GET /api/activity?date_start=YYYY-MM-DD&date_end=YYYY-MM-DD&name=xxx
    """
    date = request.args.get("date")
    date_start = request.args.get("date_start")
    date_end = request.args.get("date_end")
    name = request.args.get("name")
    activity_id = request.args.get("activity_id", type=int)
    result = get_activity(activity_id=activity_id, date=date, name=name,
                          date_start=date_start, date_end=date_end)
    return jsonify(result)


@api.route("/activity/freq-stats", methods=["POST"])
def activity_freq_stats():
    """
    POST /api/activity/freq-stats
    JSON body: {"activity_ids": []}  — 空数组=全部活动
    """
    data = request.get_json(silent=True) or {}
    activity_ids = data.get("activity_ids", [])
    from db.database import get_activity_freq_stats
    stats = get_activity_freq_stats(activity_ids if activity_ids else None)
    return jsonify({"code": 0, "msg": "ok", "data": {"stats": stats}})


@api.route("/activity/merged-export", methods=["POST"])
def activity_merged_export():
    """
    POST /api/activity/merged-export
    JSON body: {"activity_ids": [...], "format": "excel"|"csv"}
    合并导出多个活动的参与人员明细。
    """
    data = request.get_json(silent=True) or {}
    activity_ids = data.get("activity_ids", [])
    fmt = data.get("format", "excel")

    from db.database import get_merged_activity_participants
    rows = get_merged_activity_participants(activity_ids)
    if not rows:
        return jsonify({"code": 0, "msg": "无数据可导出", "data": None})

    import pandas as pd
    import os
    df = pd.DataFrame(rows)
    col_map = {
        "activity_name": "活动名称", "activity_time": "活动时间",
        "student_id": "学号", "student_name": "姓名"
    }
    df.rename(columns=col_map, inplace=True)

    export_dir = os.path.join(os.path.dirname(__file__), "..", "data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    if fmt == "csv":
        filepath = os.path.join(export_dir, "activity_merged.csv")
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return send_file(filepath, as_attachment=True, mimetype="text/csv",
                         download_name="activity_merged.csv")
    else:
        filepath = os.path.join(export_dir, "activity_merged.xlsx")
        df.to_excel(filepath, index=False, engine="openpyxl")
        return send_file(filepath, as_attachment=True,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name="activity_merged.xlsx")


@api.route("/activity/<int:activity_id>", methods=["DELETE"])
def delete_activity(activity_id):
    """DELETE /api/activity/<id>"""
    from db.database import delete_activity as db_delete_activity
    ok = db_delete_activity(activity_id)
    if ok:
        return jsonify({"code": 0, "msg": "删除成功", "data": None})
    return jsonify({"code": 7, "msg": "活动不存在", "data": None}), 404


@api.route("/activity/<int:activity_id>/participants", methods=["GET"])
def activity_participants(activity_id):
    """GET /api/activity/<id>/participants"""
    from db.database import query_emotion
    rows = db_query_activity(activity_id=activity_id)
    participants = []
    for r in rows:
        if r.get("student_id"):
            # 查该学生在本次活动时间附近的情绪
            emotion_records = query_emotion(student_id=r["student_id"])
            emotion = emotion_records[0]["emotion"] if emotion_records else "neutral"
            participants.append({
                "student_id": r["student_id"],
                "name": r.get("student_name", ""),
                "emotion": emotion,
            })
    return jsonify({
        "code": 0,
        "msg": "ok",
        "data": {
            "activity_id": activity_id,
            "participants": participants,
        }
    })


@api.route("/students", methods=["GET"])
def students():
    """GET /api/students"""
    result = get_student_list()
    return jsonify(result)


# ---- 导出 ----

@api.route("/export", methods=["GET"])
def export():
    """
    GET /api/export?type=attendance|activity&date=xxx&student_id=xxx&format=excel|csv
    """
    export_type = request.args.get("type", "attendance")
    date = request.args.get("date")
    student_id = request.args.get("student_id")
    name = request.args.get("name")
    fmt = request.args.get("format", "excel")

    if export_type == "activity":
        from service.query import export_activity
        filepath = export_activity(date=date, name=name, fmt=fmt)
    else:
        filepath = export_attendance(date=date, student_id=student_id, fmt=fmt)

    if filepath is None:
        return jsonify({"code": 0, "msg": "无数据可导出", "data": None})

    if fmt == "csv":
        return send_file(
            filepath, as_attachment=True,
            mimetype="text/csv",
            download_name="attendance_export.csv"
        )
    else:
        return send_file(
            filepath, as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            download_name="attendance_export.xlsx"
        )


# ---- 人脸库管理 ----

@api.route("/register", methods=["POST"])
def register():
    """
    POST /api/register
    multipart/form-data: image=<file>, student_id=<str>, name=<str>
    """
    student_id = request.form.get("student_id", "").strip()
    name = request.form.get("name", "").strip()
    if not student_id:
        return jsonify({"code": 1, "msg": "学号不能为空", "data": None}), 400

    # 检查是否已注册（在读取图片前，节省资源）
    existing = get_student(student_id)
    if existing:
        return jsonify({
            "code": 6,
            "msg": f"学号 {student_id} 已注册（{existing['name']}），请勿重复注册",
            "data": None
        }), 400

    img = _read_image_from_request()
    if img is None:
        return jsonify({"code": 1, "msg": "无效图片", "data": None}), 400

    faces = detect_faces(img)
    if not faces:
        return jsonify({"code": 2, "msg": "未检测到人脸", "data": None}), 400

    # 取最大人脸注册
    largest = max(faces, key=lambda b: b[2] * b[3])
    x, y, w, h = largest
    face_img = img[y:y + h, x:x + w]

    ok = register_face(face_img, student_id)
    if not ok:
        return jsonify({"code": 3, "msg": "人脸编码失败", "data": None}), 400

    # 先写数据库，再持久化编码
    if name:
        if not add_student(name, student_id):
            return jsonify({"code": 6, "msg": f"学号 {student_id} 已存在", "data": None}), 400

    save_encodings()

    return jsonify({
        "code": 0,
        "msg": "注册成功",
        "data": {"student_id": student_id, "name": name}
    })


@api.route("/student", methods=["PUT"])
def update_student():
    """
    PUT /api/student
    JSON body: {"student_id": "xxx", "name": "新姓名"}
    """
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id", "").strip()
    new_name = data.get("name", "").strip()

    if not student_id or not new_name:
        return jsonify({"code": 1, "msg": "学号和姓名不能为空", "data": None}), 400

    from db.database import update_student_name
    ok = update_student_name(student_id, new_name)
    if not ok:
        return jsonify({"code": 7, "msg": "学生不存在", "data": None}), 404

    return jsonify({"code": 0, "msg": "更新成功", "data": {"student_id": student_id, "name": new_name}})


@api.route("/student", methods=["DELETE"])
def remove_student():
    """
    DELETE /api/student?student_id=xxx
    """
    student_id = request.args.get("student_id", "").strip()
    if not student_id:
        return jsonify({"code": 1, "msg": "学号不能为空", "data": None}), 400

    from cv_core.recognizer import remove_student as remove_face
    remove_face(student_id)
    save_encodings()
    deleted = delete_student(student_id)

    return jsonify({
        "code": 0,
        "msg": "删除成功" if deleted else "学生不存在",
        "data": None
    })


# ---- 健康检查 ----

@api.route("/ping", methods=["GET"])
def ping():
    return jsonify({"code": 0, "msg": "pong", "data": None})
