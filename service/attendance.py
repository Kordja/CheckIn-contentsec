"""
考勤服务：串联多帧人脸检测 → landmarks → 活体 → 识别 → 情绪(异步) → 入库
"""

import cv2
import threading
from db.database import save_attendance, save_emotion, get_student
from cv_core.face_detection import detect_faces, get_largest_face
from cv_core.landmarks import get_landmarks
from cv_core.liveness import liveness_check
from cv_core.recognizer import recognize_face

MAX_WIDTH = 640  # 图片超此宽度时自动缩放


def _resize(img):
    h, w = img.shape[:2]
    if w > MAX_WIDTH:
        scale = MAX_WIDTH / w
        return cv2.resize(img, (MAX_WIDTH, int(h * scale)))
    return img


def _emotion_async(face_img, student_id):
    """后台线程：分析情绪并写入数据库。"""
    from cv_core.emotion import analyze_emotion
    emotion = analyze_emotion(face_img, lang="cn")
    if emotion == "unknown":
        emotion = "neutral"
    save_emotion(student_id, emotion)


def process_attendance(images: list) -> dict:
    """
    处理一次考勤签到。
    images: 连续帧列表（list of np.ndarray），最少 1 帧。
    """
    if not images:
        return {"code": 1, "msg": "无图像数据", "data": None}

    images = [_resize(img) for img in images]
    last_img = images[-1]

    # 1. 人脸检测
    faces = detect_faces(last_img)
    if not faces:
        return {"code": 2, "msg": "未检测到人脸", "data": None}

    face_bbox = get_largest_face(last_img)
    x, y, w, h = face_bbox
    face_img = last_img[y:y + h, x:x + w]

    multi_face_hint = "检测到多人脸，已自动选最大人脸" if len(faces) > 1 else None

    # 2. 活体检测：每帧独立提取 landmarks
    landmarks_seq = []
    for img in images:
        faces_in_frame = detect_faces(img)
        if not faces_in_frame:
            continue
        bbox = max(faces_in_frame, key=lambda b: b[2] * b[3])
        pts = get_landmarks(img, bbox)
        if pts is not None:
            landmarks_seq.append(pts)

    liveness_passed = liveness_check(landmarks_seq)

    if not liveness_passed:
        return {
            "code": 4,
            "msg": f"活体检测未通过（采集 {len(landmarks_seq)} 帧，未检测到眨眼），请眨眼后重试",
            "data": {"liveness": False, "frames_collected": len(landmarks_seq)}
        }

    # 3. 人脸识别
    student_id = recognize_face(face_img)
    if student_id is None:
        return {"code": 5, "msg": "未识别到身份", "data": {"liveness": liveness_passed}}

    # 4. 写入考勤记录（情绪由后台线程异步写入）
    save_attendance(student_id, status="present", liveness=1)
    threading.Thread(target=_emotion_async, args=(face_img, student_id),
                     daemon=True).start()

    # 5. 获取学生信息
    student = get_student(student_id)
    name = student["name"] if student else student_id

    msg = "签到成功"
    if multi_face_hint:
        msg = multi_face_hint

    return {
        "code": 0,
        "msg": msg,
        "data": {
            "name": name,
            "student_id": student_id,
            "status": "present",
            "emotion": "分析中...",
            "liveness": True,
            "frames_collected": len(landmarks_seq),
        }
    }
