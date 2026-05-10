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
from cv_core.screen_attack_detect import detect_screen_attack

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
            "data": {"liveness": "failed", "liveness_val": 0,
                     "frames_collected": len(landmarks_seq)}
        }

    # 3. 人脸识别
    student_id = recognize_face(face_img)
    if student_id is None:
        return {"code": 5, "msg": "未识别到身份",
                "data": {"liveness": "passed" if liveness_passed else "failed",
                         "liveness_val": 1 if liveness_passed else 0}}

    # 4. 屏幕翻拍检测（对主帧做人脸区域的介质检测）
    screen_result = detect_screen_attack(face_img)
    # [DEBUG] 打印 FFT 指标，供真人 vs 翻拍对比校准阈值
    print(f"[screen_attack] score={screen_result['score']:.3f} "
          f"moire_pr={screen_result['details']['moire'].get('peak_ratio',0):.3f} "
          f"lap_var={screen_result['details']['blur'].get('laplacian_var',0):.1f} "
          f"is_suspicious={screen_result['is_suspicious']}", flush=True)
    liveness_val = 2 if screen_result["is_suspicious"] else 1
    liveness_label = "suspicious_screen" if screen_result["is_suspicious"] else "passed"

    # 5. 写入考勤记录（情绪由后台线程异步写入）
    save_attendance(student_id, status="present", liveness=liveness_val)
    threading.Thread(target=_emotion_async, args=(face_img, student_id),
                     daemon=True).start()

    # 6. 获取学生信息
    student = get_student(student_id)
    name = student["name"] if student else student_id

    msg = "签到成功"
    if screen_result["is_suspicious"]:
        msg = "签到成功（疑似屏幕翻拍，已标记）"
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
            "liveness": liveness_label,
            "liveness_val": liveness_val,
            "screen_score": screen_result["score"],
            "screen_moire_pr": screen_result["details"]["moire"].get("peak_ratio", 0),
            "screen_lap_var": screen_result["details"]["blur"].get("laplacian_var", 0),
            "frames_collected": len(landmarks_seq),
        }
    }
