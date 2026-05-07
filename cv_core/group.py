"""
合照识别模块（批处理）
- 输入: image (np.ndarray, 完整合照)
- 输出: list[dict] — [{student_id, bbox: (x,y,w,h)}, ...]
- 依赖: face_detection + recognizer
- 不接触数据库、不接触 HTTP
"""

import numpy as np
from .face_detection import detect_faces
from .recognizer import recognize_face


def recognize_group(image: np.ndarray):
    """
    识别合照中的所有人脸，返回识别结果列表。
    未识别到身份的人脸 student_id 为 None。
    """
    if image is None or image.size == 0:
        return []

    faces = detect_faces(image)
    results = []

    for bbox in faces:
        x, y, w, h = bbox
        face_img = image[y:y + h, x:x + w]
        student_id = recognize_face(face_img)
        results.append({
            "student_id": student_id,
            "bbox": bbox,
        })

    return results


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys
    import cv2

    if len(sys.argv) < 2:
        print("用法: python group.py <合照路径>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    results = recognize_group(img)
    print(f"检测到 {len(results)} 张人脸")

    identified = [r for r in results if r["student_id"] is not None]
    unknown = [r for r in results if r["student_id"] is None]
    print(f"已识别: {len(identified)}, 未识别: {len(unknown)}")

    for r in results:
        sid = r["student_id"] or "unknown"
        bbox = r["bbox"]
        print(f"  {sid}: {bbox}")
        x, y, w, h = bbox
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(img, sid, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("Group Recognition", img)
    print("\n按任意键关闭...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
