// === 合照识别页面逻辑 ===

const API_BASE = '/api';
let selectedFile = null;

// ---- 文件选择 ----

const uploadZone = document.getElementById('uploadZone');

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
});

function handleFile(file) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        showToast('请选择图片文件', 'error');
        return;
    }
    selectedFile = file;
    document.getElementById('btnAnalyze').disabled = false;
    document.getElementById('statusText').textContent = '已选择: ' + file.name;

    // 预览
    const reader = new FileReader();
    reader.onload = (e) => {
        const preview = document.getElementById('preview');
        preview.src = e.target.result;
        preview.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

// ---- 发送识别 ----

async function analyzeGroup() {
    if (!selectedFile) return;

    const btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    btn.textContent = '识别中...';
    document.getElementById('statusText').textContent = '正在分析...';

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
        const resp = await fetch(API_BASE + '/group', { method: 'POST', body: formData });
        const result = await resp.json();
        renderResult(result);
        document.getElementById('statusText').textContent = result.msg;
    } catch (e) {
        document.getElementById('statusText').textContent = '网络错误';
        showToast('网络错误: ' + e.message, 'error');
    }

    btn.disabled = false;
    btn.textContent = '开始识别';
}

function renderResult(result) {
    const card = document.getElementById('resultCard');
    card.style.display = 'block';

    if (result.code !== 0) {
        document.getElementById('statsGrid').innerHTML = '';
        document.getElementById('resultBody').innerHTML = '';
        showToast(result.msg, 'error');
        return;
    }

    const data = result.data;
    document.getElementById('statsGrid').innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${data.total_faces}</div>
            <div class="stat-label">检测人脸</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${data.identified}</div>
            <div class="stat-label">已识别</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${data.total_faces - data.identified}</div>
            <div class="stat-label">未识别</div>
        </div>
    `;

    const tbody = document.getElementById('resultBody');
    tbody.innerHTML = data.results.map((r, i) => `
        <tr>
            <td>${i + 1}</td>
            <td>${r.student_id || '-'}</td>
            <td>${r.name || '-'}</td>
            <td style="font-size:12px; color:var(--text-muted);">
                (${r.bbox[0]}, ${r.bbox[1]}, ${r.bbox[2]}, ${r.bbox[3]})
            </td>
        </tr>
    `).join('');
}

function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
}
