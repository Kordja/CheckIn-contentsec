"""
情绪识别模块（基于 DeepFace）
- 输入: face_image (np.ndarray, BGR)
- 输出: emotion_label (str)  — 如 "happy", "sad", "neutral" 等
- 不接触数据库、不接触 HTTP
"""

import sys
import io
import numpy as np
import cv2

# 修复 Windows GBK 编码下 DeepFace logger 输出 emoji 导致的 UnicodeEncodeError
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from deepface import DeepFace

# DeepFace 情绪标签映射（英文 → 中文，可选）
EMOTION_CN = {
    "angry": "愤怒",
    "disgust": "厌恶",
    "fear": "恐惧",
    "happy": "高兴",
    "sad": "悲伤",
    "surprise": "惊讶",
    "neutral": "中性",
}


def analyze_emotion(face_image: np.ndarray, lang="en"):
    """
    分析人脸情绪，返回标签字符串。
    lang="en" 返回英文标签，"cn" 返回中文标签。
    失败时返回 "unknown"。
    """
    if face_image is None or face_image.size == 0:
        return "unknown"

    try:
        rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        # 禁止 DeepFace 的冗长输出和自动下载进度条
        results = DeepFace.analyze(
            rgb,
            actions=["emotion"],
            enforce_detection=False,
            silent=True,
        )
        if isinstance(results, list):
            emotion = results[0]["dominant_emotion"]
        else:
            emotion = results["dominant_emotion"]
    except Exception:
        return "unknown"

    if lang == "cn":
        return EMOTION_CN.get(emotion, emotion)
    return emotion


# --- 独立验证入口 ---
if __name__ == "__main__":
    import sys
    from face_detection import detect_faces

    if len(sys.argv) < 2:
        print("用法: python emotion.py <图片路径>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    faces = detect_faces(img)
    print(f"检测到 {len(faces)} 张人脸")

    for i, bbox in enumerate(faces):
        x, y, w, h = bbox
        face_img = img[y:y + h, x:x + w]
        emotion_en = analyze_emotion(face_img, lang="en")
        emotion_cn = analyze_emotion(face_img, lang="cn")
        print(f"  人脸 {i + 1}: {emotion_en} ({emotion_cn})")
