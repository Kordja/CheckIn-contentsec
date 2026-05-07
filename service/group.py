"""
合照服务：批量人脸检测 → 逐个识别 → 统计名单 → 写入活动记录
"""

from db.database import add_activity_record, create_activity, get_student
from cv_core.face_detection import detect_faces
from cv_core.recognizer import recognize_face


def process_group(image, activity_name="合照签到") -> dict:
    """
    处理一张合照，返回识别结果列表并写入活动记录。
    """
    if image is None or image.size == 0:
        return {"code": 1, "msg": "无效图片", "data": None}

    faces = detect_faces(image)
    if not faces:
        return {"code": 2, "msg": "未检测到人脸", "data": []}

    # 创建活动
    activity_id = create_activity(activity_name)

    results = []
    identified_count = 0

    for bbox in faces:
        x, y, w, h = bbox
        face_img = image[y:y + h, x:x + w]
        student_id = recognize_face(face_img)

        name = None
        if student_id:
            student = get_student(student_id)
            name = student["name"] if student else None
            add_activity_record(student_id, activity_id)
            identified_count += 1

        results.append({
            "student_id": student_id,
            "name": name,
            "bbox": list(bbox),
        })

    msg = f"检测 {len(faces)} 人，识别 {identified_count} 人"
    return {
        "code": 0,
        "msg": msg,
        "data": {
            "activity_id": activity_id,
            "activity_name": activity_name,
            "total_faces": len(faces),
            "identified": identified_count,
            "results": results,
        }
    }
