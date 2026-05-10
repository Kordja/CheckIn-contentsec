// === 考勤签到页面逻辑 ===

const API_BASE = '/api';
let videoEl = null;
let stream = null;

// ---- 摄像头 ----

async function initCamera() {
    videoEl = document.getElementById('video');
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });
        videoEl.srcObject = stream;
        await new Promise(r => videoEl.onloadedmetadata = r);
        document.getElementById('cameraStatus').textContent =
            `摄像头已就绪 (${videoEl.videoWidth}×${videoEl.videoHeight})`;
        updateOverlay('点击拍照签到', 'scanning');
    } catch (e) {
        document.getElementById('cameraStatus').textContent = '摄像头不可用: ' + e.message;
        updateOverlay('摄像头不可用', 'error');
    }
}

function updateOverlay(msg, type) {
    const el = document.getElementById('cameraOverlay');
    el.textContent = msg;
    el.className = 'camera-overlay overlay-' + type;
}

// ---- 拍照签到 ----

async function manualCapture() {
    if (!videoEl || !videoEl.videoWidth) {
        showToast('摄像头未就绪', 'error');
        return;
    }

    const btn = document.getElementById('btnCapture');
    btn.disabled = true;
    btn.textContent = '采集中...';
    updateOverlay('采集中，请连续眨眼...', 'scanning');

    const frames = [];
    for (let i = 0; i < 8; i++) {
        try {
            const blob = await captureFrameBlob();
            if (blob && blob.size > 1000) {
                frames.push(blob);
            }
        } catch (e) { /* skip */ }
        await sleep(120);
    }

    btn.textContent = '识别中...';
    updateOverlay('识别中...', 'scanning');

    if (frames.length === 0) {
        showResult({ code: -1, msg: '采集失败，请重试', data: null });
        btn.disabled = false;
        btn.textContent = '拍照签到';
        updateOverlay('采集失败', 'error');
        return;
    }

    const formData = new FormData();
    frames.forEach((blob, i) => {
        formData.append('frames', blob, `f${i}.jpg`);
    });

    try {
        const resp = await fetch(API_BASE + '/attendance', {
            method: 'POST',
            body: formData,
        });
        if (!resp.ok && resp.status >= 500) {
            throw new Error('服务器错误 ' + resp.status);
        }
        const result = await resp.json();
        showResult(result);

        if (result.code === 0) {
            updateOverlay('签到成功: ' + (result.data?.name || ''), 'success');
        } else {
            updateOverlay(result.msg, 'error');
        }
    } catch (e) {
        showResult({ code: -1, msg: '请求失败: ' + e.message, data: null });
        updateOverlay('请求失败', 'error');
    }

    btn.disabled = false;
    btn.textContent = '拍照签到';
    setTimeout(() => updateOverlay('点击拍照签到', 'scanning'), 3000);
}

function captureFrameBlob(srcVideo = null) {
    const v = srcVideo || videoEl;
    return new Promise((resolve, reject) => {
        if (!v || !v.videoWidth) {
            reject(new Error('video not ready'));
            return;
        }
        const canvas = document.createElement('canvas');
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) { reject(new Error('no context')); return; }
        ctx.drawImage(v, 0, 0);
        canvas.toBlob((blob) => {
            if (blob) resolve(blob);
            else reject(new Error('toBlob failed'));
        }, 'image/jpeg', 0.85);
    });
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

// ---- 结果展示 ----

function showResult(result) {
    const container = document.getElementById('resultContainer');
    const cls = result.code === 0 ? 'result-success' : 'result-error';
    const title = result.code === 0 ? '签到成功' : '签到失败';

    let detail = '';
    if (result.data) {
        if (result.data.name) detail += '<p>姓名: ' + result.data.name + '</p>';
        if (result.data.student_id) detail += '<p>学号: ' + result.data.student_id + '</p>';
        if (result.data.emotion) detail += '<p>情绪: ' + result.data.emotion + '</p>';
        if (result.data.liveness !== undefined) {
            let livenessText = result.data.liveness;
            if (result.data.liveness === 'passed') livenessText = '通过';
            else if (result.data.liveness === 'failed') livenessText = '未通过';
            else if (result.data.liveness === 'suspicious_screen') livenessText = '通过（⚠ 疑似屏幕翻拍）';
            detail += '<p>活体: ' + livenessText + '</p>';
        }
        if (result.data.screen_score !== undefined) {
            detail += '<p style="font-size:12px;color:var(--text-muted);">屏幕检测: score=' + result.data.screen_score.toFixed(2) + ', moire=' + result.data.screen_moire_pr.toFixed(2) + ', blur=' + result.data.screen_lap_var.toFixed(0) + '</p>';
        }
    }

    container.innerHTML = `
        <div class="result-card ${cls} show">
            <div class="result-title">${title}</div>
            <div class="result-detail">${result.msg}</div>
            ${detail}
        </div>`;
}

// ---- Toast ----

function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
}

// ---- 启动 ----
initCamera();
