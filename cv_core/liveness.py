"""
活体检测模块（基于 EAR 眨眼检测）
- 输入: landmarks_sequence — list[np.ndarray], 连续帧的 landmarks 列表
- 输出: bool (True=活体)
- 不接触数据库、不接触 HTTP
"""

import numpy as np

# 阈值（已调优，适配 200ms 帧间隔）
EAR_THRESHOLD = 0.18      # 眨眼时 EAR 低于此值（原 0.2，调低以提高检测灵敏度）
EAR_CONSEC_FRAMES = 1     # 连续低于阈值算闭眼（原 2，降低以避免快眨眼被漏掉）
BLINK_MIN_COUNT = 1       # 至少眨眼次数


def _euclidean(p1, p2):
    return np.linalg.norm(p1 - p2)


def _eye_aspect_ratio(eye_points: np.ndarray):
    """
    计算单只眼睛的 EAR。
    eye_points: shape (6, 2)，索引 0-5 对应眼角→上→下→眼角 顺序。
    """
    # EAR = (|p1-p5| + |p2-p4|) / (2 * |p0-p3|)
    ear = (_euclidean(eye_points[1], eye_points[5]) +
           _euclidean(eye_points[2], eye_points[4])) / \
          (2.0 * _euclidean(eye_points[0], eye_points[3]) + 1e-8)
    return ear


def calc_ear(landmarks: np.ndarray):
    """
    从 68 关键点计算双眼平均 EAR。
    - 左眼（图上右侧）: indices 42-47
    - 右眼（图上左侧）: indices 36-41
    """
    if landmarks is None or len(landmarks) < 68:
        return None
    left_eye = landmarks[42:48]
    right_eye = landmarks[36:42]
    ear_left = _eye_aspect_ratio(left_eye)
    ear_right = _eye_aspect_ratio(right_eye)
    return float((ear_left + ear_right) / 2.0)


def liveness_check(landmarks_sequence: list, threshold=EAR_THRESHOLD,
                   consec_frames=EAR_CONSEC_FRAMES, min_blinks=BLINK_MIN_COUNT):
    """
    基于连续帧 landmarks 判断是否活体（检测眨眼）。
    landmarks_sequence: list of np.ndarray，每帧的 68 关键点
    threshold: EAR 低于此值认为闭眼
    consec_frames: 连续低于阈值算一次闭眼
    min_blinks: 最少眨眼次数
    """
    if not landmarks_sequence or len(landmarks_sequence) < consec_frames + 1:
        return False

    blink_count = 0
    closed_counter = 0

    for landmarks in landmarks_sequence:
        ear = calc_ear(landmarks)
        if ear is None:
            continue

        if ear < threshold:
            closed_counter += 1
        else:
            if closed_counter >= consec_frames:
                blink_count += 1
            closed_counter = 0

    # 收尾：最后一段闭眼也计入
    if closed_counter >= consec_frames:
        blink_count += 1

    return blink_count >= min_blinks


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys
    import cv2
    from face_detection import detect_faces
    from landmarks import get_landmarks

    if len(sys.argv) < 2:
        print("用法: python liveness.py <图片路径>")
        print("注意: 单张图片无法验证活体检测逻辑（需要连续帧），"
              "此脚本仅展示 EAR 计算。")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    faces = detect_faces(img)
    print(f"检测到 {len(faces)} 张人脸")

    for i, bbox in enumerate(faces):
        pts = get_landmarks(img, bbox)
        if pts is None:
            print(f"  人脸 {i+1}: 无关键点")
            continue
        ear = calc_ear(pts)
        print(f"  人脸 {i+1}: EAR = {ear:.4f}")

    print("\n提示: 活体检测需连续帧输入，请通过摄像头或视频验证。")
