"""
68 关键点提取模块
- 输入: image (np.ndarray), face_bbox (x, y, w, h)
- 输出: np.ndarray shape (68, 2) 或 None
- 不接触数据库、不接触 HTTP
"""

import dlib
import cv2
import numpy as np
import os

_predictor = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "shape_predictor_68_face_landmarks.dat")


def _get_predictor():
    global _predictor
    if _predictor is None:
        model_path = os.path.abspath(_MODEL_PATH)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"模型文件不存在: {model_path}\n"
                "请确保 data/shape_predictor_68_face_landmarks.dat 已下载。"
            )
        _predictor = dlib.shape_predictor(model_path)
    return _predictor


def get_landmarks(image: np.ndarray, face_bbox: tuple):
    """
    返回 68 关键点坐标 (np.ndarray, shape=(68,2))。
    无人脸或无关键点时返回 None。
    """
    if image is None or image.size == 0 or face_bbox is None:
        return None

    predictor = _get_predictor()
    x, y, w, h = face_bbox
    rect = dlib.rectangle(int(x), int(y), int(x + w), int(y + h))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    try:
        shape = predictor(gray, rect)
    except Exception:
        return None

    points = np.array([[p.x, p.y] for p in shape.parts()], dtype=np.int32)
    return points


def get_landmarks_dict(image: np.ndarray, face_bbox: tuple):
    """
    返回命名关键点字典，方便按部位选取。
    索引约定（dlib 68点标准）：
      - chin:       0-16
      - right_eyebrow: 17-21
      - left_eyebrow:  22-26
      - nose:          27-35
      - right_eye:     36-41
      - left_eye:      42-47
      - mouth:         48-67
    """
    points = get_landmarks(image, face_bbox)
    if points is None:
        return None
    return {
        "chin": points[0:17],
        "right_eyebrow": points[17:22],
        "left_eyebrow": points[22:27],
        "nose": points[27:36],
        "right_eye": points[36:42],
        "left_eye": points[42:48],
        "mouth": points[48:68],
    }


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python landmarks.py <图片路径>")
        sys.exit(1)

    from face_detection import detect_faces

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    faces = detect_faces(img)
    print(f"检测到 {len(faces)} 张人脸")

    for i, bbox in enumerate(faces):
        print(f"\n人脸 {i + 1} (bbox={bbox}):")
        pts = get_landmarks(img, bbox)
        if pts is None:
            print("  未提取到关键点")
            continue
        print(f"  68关键点 shape: {pts.shape}")
        # 绘制关键点
        for (px, py) in pts:
            cv2.circle(img, (px, py), 2, (0, 255, 0), -1)

    cv2.imshow("Landmarks", img)
    print("\n按任意键关闭窗口...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
