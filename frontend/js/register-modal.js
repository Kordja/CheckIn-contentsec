// === 注册弹窗（所有页面共享）===

// API_BASE 由各页面主 JS 文件声明，本文件直接引用
var regCameraStream = null;

async function startRegCamera() {
    try {
        regCameraStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });
        document.getElementById('regVideo').srcObject = regCameraStream;
    } catch (e) {
        // 摄像头不可用，只影响拍照注册，上传注册仍可用
    }
}

function stopRegCamera() {
    if (regCameraStream) {
        regCameraStream.getTracks().forEach(t => t.stop());
        regCameraStream = null;
    }
}

function openRegisterModal() {
    document.getElementById('registerModal').classList.add('show');
    document.getElementById('regResult').innerHTML = '';
    startRegCamera();
}

function closeRegisterModal() {
    document.getElementById('registerModal').classList.remove('show');
    document.getElementById('regVideo').srcObject = null;
    stopRegCamera();
}

function closeModalOutside(e) {
    if (e.target === document.getElementById('registerModal')) {
        closeRegisterModal();
    }
}

// ---- 采集帧 ----

function captureRegFrame() {
    const v = document.getElementById('regVideo');
    return new Promise((resolve, reject) => {
        if (!v || !v.videoWidth) { reject(new Error('video not ready')); return; }
        const canvas = document.createElement('canvas');
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        canvas.getContext('2d').drawImage(v, 0, 0);
        canvas.toBlob(b => b ? resolve(b) : reject(new Error('toBlob failed')), 'image/jpeg', 0.85);
    });
}

// ---- 拍照注册 ----

async function registerFace() {
    const name = document.getElementById('regName').value.trim();
    const sid = document.getElementById('regStudentId').value.trim();

    if (!name || !sid) { alert('请填写姓名和学号'); return; }

    const v = document.getElementById('regVideo');
    if (!v || !v.videoWidth) { alert('摄像头未就绪，请刷新页面后重试'); return; }

    const btn = document.getElementById('btnRegister');
    btn.disabled = true;
    btn.textContent = '注册中...';
    document.getElementById('regResult').innerHTML = '<span style="color:var(--text-muted);">正在采集...</span>';

    try {
        const blob = await captureRegFrame();
        const formData = new FormData();
        formData.append('image', blob, 'register.jpg');
        formData.append('student_id', sid);
        formData.append('name', name);

        const resp = await fetch(API_BASE + '/register', { method: 'POST', body: formData });
        const result = await resp.json();

        if (result.code === 0) {
            document.getElementById('regResult').innerHTML = '<span style="color:var(--success);">✅ 注册成功</span>';
            setTimeout(closeRegisterModal, 1500);
        } else {
            document.getElementById('regResult').innerHTML = '<span style="color:var(--danger);">❌ ' + result.msg + '</span>';
        }
    } catch (e) {
        document.getElementById('regResult').innerHTML = '<span style="color:var(--danger);">请求失败: ' + e.message + '</span>';
    }
    btn.disabled = false;
    btn.textContent = '拍照注册';
}

// ---- 上传文件注册 ----

async function registerFromFile(file) {
    if (!file) return;

    const name = document.getElementById('regName').value.trim();
    const sid = document.getElementById('regStudentId').value.trim();
    if (!name || !sid) { alert('请先填写姓名和学号'); return; }

    const btn = document.getElementById('btnRegister');
    btn.disabled = true;
    btn.textContent = '注册中...';
    document.getElementById('regResult').innerHTML = '<span style="color:var(--text-muted);">正在上传...</span>';

    try {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('student_id', sid);
        formData.append('name', name);

        const resp = await fetch(API_BASE + '/register', { method: 'POST', body: formData });
        const result = await resp.json();

        if (result.code === 0) {
            document.getElementById('regResult').innerHTML = '<span style="color:var(--success);">✅ 注册成功</span>';
            setTimeout(closeRegisterModal, 1500);
        } else {
            document.getElementById('regResult').innerHTML = '<span style="color:var(--danger);">❌ ' + result.msg + '</span>';
        }
    } catch (e) {
        document.getElementById('regResult').innerHTML = '<span style="color:var(--danger);">请求失败: ' + e.message + '</span>';
    }
    btn.disabled = false;
    btn.textContent = '拍照注册';
    document.getElementById('regFileInput').value = '';
}
