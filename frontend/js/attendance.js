// === 考勤签到页面逻辑 ===

const API_BASE = '/api';
let videoEl = null;
let autoMode = false;
let stream = null;
let autoFrameBuffer = [];

// ---- 摄像头 ----

async function initCamera() {
    videoEl = document.getElementById('video');
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });
        videoEl.srcObject = stream;
        // 等视频元数据就绪
        await new Promise(r => videoEl.onloadedmetadata = r);
        document.getElementById('cameraStatus').textContent =
            `摄像头已就绪 (${videoEl.videoWidth}×${videoEl.videoHeight})`;
        updateOverlay('点击拍照签到', 'scanning');
        startAutoCheck();
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
    updateOverlay('采集中...', 'scanning');

    // 采集多帧（用于活体检测，即使部分帧失败也不影响签到）
    const frames = [];
    for (let i = 0; i < 8; i++) {
        try {
            const blob = await captureFrameBlob();
            if (blob && blob.size > 1000) {
                frames.push(blob);
            }
        } catch (e) { /* 跳过失败帧 */ }
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

    // 发送
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

// ---- 自动签到 ----

function toggleAutoMode() {
    autoMode = document.getElementById('autoMode').checked;
    document.getElementById('autoLabel').textContent = '自动签到：' + (autoMode ? '开' : '关');
    autoFrameBuffer = [];
    if (autoMode) {
        updateOverlay('自动检测中，请自然眨眼...', 'scanning');
    } else {
        updateOverlay('点击拍照签到', 'scanning');
    }
}

function startAutoCheck() {
    setInterval(async () => {
        if (!autoMode || !videoEl || !videoEl.srcObject) {
            autoFrameBuffer = [];
            return;
        }

        try {
            const blob = await captureFrameBlob();
            autoFrameBuffer.push(blob);
            if (autoFrameBuffer.length > 12) autoFrameBuffer.shift();

            if (autoFrameBuffer.length >= 8) {
                const formData = new FormData();
                autoFrameBuffer.forEach((b, i) => {
                    formData.append('frames', b, `a${i}.jpg`);
                });

                const resp = await fetch(API_BASE + '/attendance', {
                    method: 'POST', body: formData
                });
                const result = await resp.json();

                if (result.code === 0) {
                    showResult(result);
                    updateOverlay('签到成功', 'success');
                    autoMode = false;
                    document.getElementById('autoMode').checked = false;
                    document.getElementById('autoLabel').textContent = '自动签到：关';
                    autoFrameBuffer = [];
                    setTimeout(() => updateOverlay('点击拍照签到', 'scanning'), 3000);
                }
            }
        } catch (e) {
            // 忽略单次失败，继续采集
        }
    }, 400);
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
            detail += '<p>活体: ' + (result.data.liveness ? '通过' : '未通过（已记录）') + '</p>';
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
