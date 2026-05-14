"""
人脸识别模块
- 输入: face_image (np.ndarray, BGR)
- 输出: student_id (str) 或 None
- 使用 face_recognition 库（dlib 128维编码 + 欧氏距离比对）
- 人脸库存储在 data/encodings.pkl
- 不接触数据库、不接触 HTTP
"""

import pickle
import os
import numpy as np
import face_recognition

# 默认人脸库路径
_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "encodings.pkl")

# 内部状态: {student_id: [encoding_128d, ...]}
_encodings_db: dict[str, list[np.ndarray]] = {}

# 识别阈值（欧氏距离，越小越严格）
MATCH_THRESHOLD = 0.58


def load_encodings(path=None):
    """从 pickle 文件加载人脸库到内存。"""
    global _encodings_db
    filepath = path or _DEFAULT_PATH
    filepath = os.path.abspath(filepath)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            _encodings_db = pickle.load(f)
    else:
        _encodings_db = {}


def save_encodings(path=None):
    """将当前内存中的人脸库保存到 pickle 文件。"""
    global _encodings_db
    filepath = path or _DEFAULT_PATH
    filepath = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        pickle.dump(_encodings_db, f)


def register_face(face_image: np.ndarray, student_id: str):
    """注册一张人脸到库中。一个 student_id 可注册多张。"""
    global _encodings_db
    if face_image is None or face_image.size == 0:
        return False

    rgb = _to_rgb(face_image)
    encodings = face_recognition.face_encodings(rgb)
    if not encodings:
        return False

    if student_id not in _encodings_db:
        _encodings_db[student_id] = []
    _encodings_db[student_id].append(encodings[0])
    return True


def recognize_face(face_image: np.ndarray, threshold=MATCH_THRESHOLD):
    """
    识别单张人脸，返回 student_id。
    如果未匹配到任何人脸库中的记录，返回 None。
    """
    candidates = _search_candidates(face_image, top_k=3)
    if candidates and candidates[0][1] <= threshold:
        return candidates[0][0]
    return None


def recognize_face_topk(face_image: np.ndarray, top_k=3,
                        threshold=MATCH_THRESHOLD):
    """
    识别单张人脸，返回前 k 个候选 [(student_id, distance), ...]，
    仅包含距离在阈值内的候选。

    注意：本函数不设 margin 检查，所有阈值内候选均返回。
    合照去重由 service/group.py 的 _deduplicate_assignments 贪心算法负责。
    """
    candidates = _search_candidates(face_image, top_k=top_k)
    if not candidates or candidates[0][1] > threshold:
        return []
    return [(sid, d) for sid, d in candidates if d <= threshold]


def _search_candidates(face_image: np.ndarray, top_k=3):
    """
    在编码库中搜索前 top_k 个最匹配的候选，
    返回 [(student_id, distance), ...]（按距离升序，含超阈值候选）。
    """
    global _encodings_db
    if face_image is None or face_image.size == 0:
        return []

    rgb = _to_rgb(face_image)
    encodings = face_recognition.face_encodings(rgb)
    if not encodings:
        return []

    query_enc = encodings[0]

    # 收集所有候选距离，取每个学生的最小距离
    best_per_student = {}
    for student_id, stored_encs in _encodings_db.items():
        min_dist = min(
            np.linalg.norm(query_enc - stored_enc)
            for stored_enc in stored_encs
        )
        best_per_student[student_id] = min_dist

    # 按距离排序，取 top_k
    sorted_candidates = sorted(best_per_student.items(), key=lambda x: x[1])
    return sorted_candidates[:top_k]


def get_all_students():
    """返回库中所有 student_id 列表。"""
    return list(_encodings_db.keys())


def remove_student(student_id: str):
    """从库中删除一个学生的全部编码。"""
    global _encodings_db
    if student_id in _encodings_db:
        del _encodings_db[student_id]
        return True
    return False


def _to_rgb(bgr_image):
    """BGR (OpenCV) → RGB (face_recognition)"""
    import cv2
    return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)


# 启动时自动尝试加载
load_encodings()


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys
    import cv2
    from face_detection import detect_faces

    if len(sys.argv) < 2:
        print("用法:")
        print("  注册: python recognizer.py register <图片路径> <学号>")
        print("  识别: python recognizer.py recognize <图片路径>")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "register":
        if len(sys.argv) < 4:
            print("用法: python recognizer.py register <图片路径> <学号>")
            sys.exit(1)
        img = cv2.imread(sys.argv[2])
        if img is None:
            print(f"无法读取图片: {sys.argv[2]}")
            sys.exit(1)
        faces = detect_faces(img)
        if not faces:
            print("未检测到人脸")
            sys.exit(1)
        face_img = img[faces[0][1]:faces[0][1] + faces[0][3],
                       faces[0][0]:faces[0][0] + faces[0][2]]
        ok = register_face(face_img, sys.argv[3])
        if ok:
            save_encodings()
            print(f"注册成功: {sys.argv[3]} (当前库: {list(_encodings_db.keys())})")
        else:
            print("注册失败：无法提取人脸编码")

    elif cmd == "recognize":
        img = cv2.imread(sys.argv[2])
        if img is None:
            print(f"无法读取图片: {sys.argv[2]}")
            sys.exit(1)
        faces = detect_faces(img)
        if not faces:
            print("未检测到人脸")
            sys.exit(1)
        for i, bbox in enumerate(faces):
            x, y, w, h = bbox
            face_img = img[y:y + h, x:x + w]
            sid = recognize_face(face_img)
            label = sid if sid else "未识别"
            print(f"  人脸 {i + 1}: {label} (bbox={bbox})")
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Recognizer", img)
        print("按任意键关闭...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    else:
        print(f"未知命令: {cmd}")
