"""
人脸检测模块
- 输入: image (np.ndarray, BGR)
- 输出: list[tuple] — [(x, y, w, h), ...]
- 不接触数据库、不接触 HTTP
"""

import dlib
import cv2
import numpy as np

_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        _detector = dlib.get_frontal_face_detector()
    return _detector


def detect_faces(image: np.ndarray):
    """
    检测图片中的所有人脸，返回 bbox 列表 [(x, y, w, h), ...]。
    无人脸时返回空列表。
    """
    if image is None or image.size == 0:
        return []

    detector = _get_detector()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    rects = detector(gray, 1)

    result = []
    for rect in rects:
        x, y = rect.left(), rect.top()
        w, h = rect.right() - x, rect.bottom() - y
        # 边界裁剪到图像范围内
        x = max(0, x)
        y = max(0, y)
        w = min(w, image.shape[1] - x)
        h = min(h, image.shape[0] - y)
        if w > 0 and h > 0:
            result.append((x, y, w, h))
    return result


def get_largest_face(image: np.ndarray):
    """
    返回面积最大的 bbox，无人脸返回 None。
    考勤场景中默认取最大人脸（文档 §3.1 流程）。
    """
    faces = detect_faces(image)
    if not faces:
        return None
    return max(faces, key=lambda b: b[2] * b[3])


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python face_detection.py <图片路径>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    faces = detect_faces(img)
    print(f"检测到 {len(faces)} 张人脸:")
    for i, (x, y, w, h) in enumerate(faces):
        print(f"  人脸 {i + 1}: x={x}, y={y}, w={w}, h={h}")
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    largest = get_largest_face(img)
    if largest:
        print(f"最大人脸: {largest}")

    # 显示结果（按任意键关闭）
    cv2.imshow("Face Detection", img)
    print("按任意键关闭窗口...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
