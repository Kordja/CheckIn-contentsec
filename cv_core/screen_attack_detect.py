"""
屏幕翻拍攻击检测（介质检测，非动作检测）
基于纯 RGB 摄像头，静默检测，不依赖用户动作。

特征：
  1. FFT 摩尔纹检测 — 主特征（屏幕像素网格与摄像头传感器干涉产生周期性条纹）
  2. Laplacian 模糊度 — 辅助（二次成像导致高频细节丢失）

返回：{"is_suspicious": bool, "score": float 0~1, "details": {...}}
"""

import cv2
import numpy as np

# 版本标记（每次校准递增，用于确认代码已生效）
__version__ = "v2-calibrated"

# ---- 校准后阈值（基于真人×6 + 视频翻拍×4 实测数据）----
# FFT 峰值比：真人 2.33-2.96，视频 2.32-2.65 → 完全重叠，不作为主特征
# Laplacian 方差：真人 107-278，视频 42-95 → 干净分离，阈值设在 100
FFT_PEAK_RATIO_THRESHOLD = 2.9
LAP_VAR_MIN = 100.0

# 加权权重（Laplacian 为主，FFT 为辅助）
W_BLUR = 0.9
W_FFT = 0.1

# 综合判定阈值（score ≥ 此值判为可疑）
SCORE_THRESHOLD = 0.5

import sys
print(f"[screen_attack_detect] loaded {__version__} "
      f"FFT_THR={FFT_PEAK_RATIO_THRESHOLD} LAP_MIN={LAP_VAR_MIN} "
      f"W_FFT={W_FFT} W_BLUR={W_BLUR}", flush=True)


# ---- 1. FFT 摩尔纹检测 ----

def _fft_moire_detect(gray_face: np.ndarray) -> dict:
    """
    对灰度人脸区域做 2D FFT，检测高频区是否存在摩尔纹引起的异常峰值。

    摩尔纹产生原理：
      屏幕的像素网格（空间频率 f_screen）与摄像头 CMOS 像素阵列（空间频率 f_cmos）
      发生差拍干涉，在图像上产生低频的彩色/亮度波纹。

      在频域中，这表现为：在正常人脸频谱（集中在低频）之外，
      中高频区域出现一个或多个孤立尖峰（对应波纹的周期性方向）。

    返回：{"has_moire": bool, "peak_ratio": float, "hf_noise_level": float}
    """
    h, w = gray_face.shape
    if h < 64 or w < 64:
        return {"has_moire": False, "peak_ratio": 0, "hf_noise_level": 0,
                "reason": "face_too_small"}

    # Hann 窗函数减少频谱泄漏
    window = np.outer(np.hanning(h), np.hanning(w))
    gray_windowed = gray_face.astype(np.float64) * window

    # 2D FFT
    f = np.fft.fft2(gray_windowed)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)

    # 对数尺度提升弱信号可见性
    log_mag = np.log1p(magnitude)

    # 构建高频区域掩膜
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]

    # 低频区（人脸轮廓）：椭圆，排除
    low_freq_mask = ((x - cx) ** 2 / (w * 0.3) ** 2 +
                     (y - cy) ** 2 / (h * 0.3) ** 2) < 1

    # 极高频区（超出摩尔纹典型频率的噪点）：排除
    high_freq_mask = ((x - cx) ** 2 / (w * 0.45) ** 2 +
                      (y - cy) ** 2 / (h * 0.45) ** 2) > 1

    # 十字轴（直流分量 & 轴对齐伪影）：排除
    cross_mask = (abs(x - cx) < 8) | (abs(y - cy) < 8)

    # 中高频带通区域
    mid_high_region = (~low_freq_mask) & (~high_freq_mask) & (~cross_mask)

    if mid_high_region.sum() < 100:
        return {"has_moire": False, "peak_ratio": 0, "hf_noise_level": 0,
                "reason": "region_too_small"}

    # 计算该区域的统计量
    region_vals = log_mag[mid_high_region]
    mean_val = float(np.mean(region_vals))
    std_val = float(np.std(region_vals))
    max_val = float(np.max(region_vals))

    # 峰值比：最高峰 vs 均值（摩尔纹产生孤立尖峰，比值异常高）
    peak_ratio = (max_val - mean_val) / (std_val + 1e-8)

    # 高频噪声水平：该区域的标准差与均值之比
    hf_noise = std_val / (mean_val + 1e-8)

    has_moire = peak_ratio > FFT_PEAK_RATIO_THRESHOLD

    return {
        "has_moire": has_moire,
        "peak_ratio": round(float(peak_ratio), 3),
        "hf_noise_level": round(float(hf_noise), 3),
        "region_mean": round(mean_val, 3),
        "region_std": round(std_val, 3),
    }


# ---- 2. Laplacian 模糊度检测 ----

def _laplacian_blur_detect(gray_face: np.ndarray) -> dict:
    """
    Laplacian 方差衡量图像清晰度（高频分量强度）。

    原理：
      真人直接拍摄：镜头直接对焦人脸，边缘锐利，Laplacian 方差较高。
      屏幕翻拍：
        - 经历两次镜头 + 一次屏幕显示的模糊叠加
        - 屏幕分辨率低于真实场景，丢失高频纹理
        - 二次拍摄可能对焦不准
        → Laplacian 方差显著降低。

    返回：{"is_blurry": bool, "laplacian_var": float}
    """
    lap = cv2.Laplacian(gray_face, cv2.CV_64F)
    var = float(lap.var())

    return {
        "is_blurry": var < LAP_VAR_MIN,
        "laplacian_var": round(var, 1),
    }


# ---- 综合判定 ----

def detect_screen_attack(face_roi: np.ndarray) -> dict:
    """
    检测输入人脸图像是否为屏幕翻拍攻击。

    输入：
      face_roi — 裁剪后的人脸区域 (np.ndarray, BGR)
    输出：
      {
        "is_suspicious": bool,   # 是否疑似翻拍
        "score": float 0~1,      # 综合可疑度（≥0.5 为可疑）
        "details": {
          "moire": {...},
          "blur": {...}
        }
      }

    注意：此模块用于「最终用于识别的主帧」，
    而非考勤流程中采集的所有帧。
    """
    if face_roi is None or face_roi.size == 0:
        return {
            "is_suspicious": False,
            "score": 0.0,
            "details": {"error": "empty_input"}
        }

    h, w = face_roi.shape[:2]
    if min(h, w) < 60:
        return {
            "is_suspicious": False,
            "score": 0.0,
            "details": {"error": "face_too_small"}
        }

    # 统一缩放到 256px 宽（保证 FFT 计算稳定，消除分辨率差异影响）
    if w > 256:
        scale = 256 / w
        face_roi = cv2.resize(face_roi, (256, int(h * scale)))

    gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

    # 两个特征并行计算
    moire = _fft_moire_detect(gray)
    blur = _laplacian_blur_detect(gray)

    # 加权打分
    score = (W_FFT * float(moire["has_moire"]) +
             W_BLUR * float(blur["is_blurry"]))

    return {
        "is_suspicious": score >= SCORE_THRESHOLD,
        "score": round(float(score), 3),
        "details": {
            "moire": moire,
            "blur": blur,
        }
    }


# ---- 独立验证入口 ----
if __name__ == "__main__":
    import sys
    from face_detection import detect_faces

    if len(sys.argv) < 2:
        print("用法: python screen_attack_detect.py <图片路径>")
        print("对比真人自拍 vs 屏幕翻拍图片的 FFT 峰值比和 Laplacian 方差")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print(f"无法读取图片: {sys.argv[1]}")
        sys.exit(1)

    faces = detect_faces(img)
    print(f"检测到 {len(faces)} 张人脸\n")

    for i, bbox in enumerate(faces):
        x, y, w, h = bbox
        face = img[y:y + h, x:x + w]
        result = detect_screen_attack(face)

        label = "⚠ 疑似屏幕翻拍" if result["is_suspicious"] else "✅ 疑似真人"
        print(f"人脸 {i + 1} (bbox={bbox})")
        print(f"  判定: {label}  (score={result['score']})")
        d = result["details"]
        if "error" not in d:
            print(f"  FFT 峰值比:    {d['moire']['peak_ratio']}  (阈值>{FFT_PEAK_RATIO_THRESHOLD})")
            print(f"  FFT 高频噪声:  {d['moire']['hf_noise_level']}")
            print(f"  Laplacian方差: {d['blur']['laplacian_var']}  (阈值<{LAP_VAR_MIN} 视为模糊)")
            print(f"  摩尔纹: {'有' if d['moire']['has_moire'] else '无'}，"
                  f"模糊: {'有' if d['blur']['is_blurry'] else '无'}")
        print()
