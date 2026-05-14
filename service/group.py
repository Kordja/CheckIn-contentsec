"""
合照服务：批量人脸检测 → 逐个识别 → 情绪分析 → 统计名单 → 写入活动记录
"""

import cv2
from datetime import datetime
from db.database import add_activity_record, create_activity, get_student, save_emotion
from cv_core.face_detection import detect_faces
from cv_core.recognizer import recognize_face_topk, MATCH_THRESHOLD
from cv_core.emotion import analyze_emotion

MAX_WIDTH = 1200


def _resize(img):
    h, w = img.shape[:2]
    if w > MAX_WIDTH:
        scale = MAX_WIDTH / w
        return cv2.resize(img, (MAX_WIDTH, int(h * scale)))
    return img


def _deduplicate_assignments(candidates_list, threshold=MATCH_THRESHOLD):
    """
    贪心去重 + 二次分配。

    candidates_list: list of [(student_id, distance), ...]，每人脸的候选列表
    threshold: 匹配距离阈值

    返回: [(assigned_id, distance), ...]，同一个人脸数量。
    assigned_id 可能为 None（无法匹配）。
    """
    n = len(candidates_list)
    assigned = [None] * n          # 最终分配: student_id 或 None
    assigned_dist = [None] * n     # 对应距离

    # 第一轮：收集所有 (face_index, candidate_index, student_id, distance)，
    #         按距离升序排列
    flat = []
    for i, cands in enumerate(candidates_list):
        for j, (sid, d) in enumerate(cands):
            if d <= threshold:
                flat.append((d, i, j, sid))

    flat.sort(key=lambda x: x[0])  # 按距离升序

    used_ids = set()
    used_faces = set()

    for d, face_idx, cand_idx, sid in flat:
        if face_idx in used_faces:
            continue  # 该人脸已分配
        if sid in used_ids:
            continue  # 该 ID 已被占用
        assigned[face_idx] = sid
        assigned_dist[face_idx] = d
        used_faces.add(face_idx)
        used_ids.add(sid)

    # 第二轮：对未分配的人脸，尝试候选列表中未被占用的次优 ID
    for i in range(n):
        if assigned[i] is not None:
            continue
        cands = candidates_list[i]
        for sid, d in cands:
            if d <= threshold and sid not in used_ids:
                assigned[i] = sid
                assigned_dist[i] = d
                used_ids.add(sid)
                break

    return assigned, assigned_dist


def process_group(image, activity_name="") -> dict:
    """
    处理一张合照，返回识别结果列表并写入活动记录。
    activity_name 为空时默认使用当天日期（如 20260510）。
    """
    if not activity_name:
        activity_name = datetime.now().strftime("%Y%m%d")
    if image is None or image.size == 0:
        return {"code": 1, "msg": "无效图片", "data": None}

    # 检测用缩放图，但裁剪从原图取（保持人脸分辨率）
    original = image
    detection_img = _resize(image)
    scale_x = original.shape[1] / detection_img.shape[1]
    scale_y = original.shape[0] / detection_img.shape[0]

    faces = detect_faces(detection_img)
    if not faces:
        return {"code": 2, "msg": "未检测到人脸", "data": []}

    activity_id = create_activity(activity_name)

    # 提取每张人脸的候选列表和情绪（从原图裁剪）
    face_imgs = []
    emotions = []
    candidates_list = []
    for bbox in faces:
        x, y, w, h = bbox
        # bbox 坐标从检测图映射回原图
        ox, oy = int(x * scale_x), int(y * scale_y)
        ow, oh = int(w * scale_x), int(h * scale_y)
        ox, oy = max(0, ox), max(0, oy)
        ow, oh = min(original.shape[1] - ox, ow), min(original.shape[0] - oy, oh)
        face_img = original[oy:oy + oh, ox:ox + ow]
        # 群照中的人脸可能太小，放大到至少 300px 保证 face_recognition 编码质量
        if face_img.shape[1] < 300:
            scale_f = 300 / face_img.shape[1]
            face_img = cv2.resize(face_img, (300, int(face_img.shape[0] * scale_f)),
                                  interpolation=cv2.INTER_LANCZOS4)
        face_imgs.append(face_img)

        # 情绪（与人脸一一对应，不受识别结果影响）
        emotion = analyze_emotion(face_img, lang="cn")
        if emotion == "unknown":
            emotion = "neutral"
        emotions.append(emotion)

        # 获取前 3 候选
        cands = recognize_face_topk(face_img, top_k=3)
        candidates_list.append(cands)

    # 贪心去重 + 二次分配
    assigned_ids, assigned_dists = _deduplicate_assignments(candidates_list)

    results = []
    identified_count = 0

    for i, bbox in enumerate(faces):
        student_id = assigned_ids[i]
        x, y, w, h = bbox
        # 输出原图坐标
        ox, oy = int(x * scale_x), int(y * scale_y)
        ow, oh = int(w * scale_x), int(h * scale_y)

        name = None
        if student_id:
            student = get_student(student_id)
            name = student["name"] if student else None
            add_activity_record(student_id, activity_id)
            save_emotion(student_id, emotions[i])
            identified_count += 1

        results.append({
            "student_id": student_id,
            "name": name,
            "bbox": [ox, oy, ow, oh],
            "emotion": emotions[i],
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
