// === 合照识别页面逻辑 ===

const API_BASE = '/api';
let selectedFile = null;
let historyData = [];
let historyPage = 0;
let freqChart = null;
const PAGE_SIZE = 10;

// ---- 默认活动名 ----

function getDefaultActivityName() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}${m}${d}`;
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('activityName').placeholder = '默认: ' + getDefaultActivityName();
});

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

function clearPreview(e) {
    e.stopPropagation();
    selectedFile = null;
    const preview = document.getElementById('preview');
    preview.src = '';
    preview.style.display = 'none';
    preview.className = '';
    document.getElementById('previewClose').style.display = 'none';
    uploadZone.classList.remove('has-preview');
    document.getElementById('btnAnalyze').disabled = true;
    document.getElementById('statusText').textContent = '';
    document.getElementById('fileInput').value = '';
}

function handleFile(file) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        showToast('请选择图片文件', 'error');
        return;
    }
    selectedFile = file;
    document.getElementById('btnAnalyze').disabled = false;
    document.getElementById('statusText').textContent = '已选择: ' + file.name;

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            const preview = document.getElementById('preview');
            preview.src = e.target.result;
            preview.className = (img.height > img.width * 1.2) ? 'portrait' : '';
            preview.style.display = 'block';
            document.getElementById('previewClose').style.display = 'flex';
            uploadZone.classList.add('has-preview');
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// ---- 开始识别 ----

async function analyzeGroup() {
    if (!selectedFile) return;

    const btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    btn.textContent = '识别中...';
    document.getElementById('statusText').textContent = '正在分析...';

    let activityName = document.getElementById('activityName').value.trim();
    if (!activityName) activityName = getDefaultActivityName();

    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('activity_name', activityName);

    try {
        const resp = await fetch(API_BASE + '/group', { method: 'POST', body: formData });
        const result = await resp.json();
        renderResult(result);
        document.getElementById('statusText').textContent = result.msg;
        if (result.code === 0 && document.getElementById('historyPanel').style.display !== 'none') {
            queryHistory();
        }
    } catch (e) {
        document.getElementById('statusText').textContent = '网络错误';
        showToast('网络错误: ' + e.message, 'error');
    }

    btn.disabled = false;
    btn.textContent = '开始识别';
}

const emoMap = {angry:'愤怒',disgust:'厌恶',fear:'恐惧',happy:'高兴',sad:'悲伤',surprise:'惊讶',neutral:'中性'};

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
            <td>${emoMap[r.emotion] || r.emotion || '-'}</td>
            <td style="font-size:12px; color:var(--text-muted);">
                (${r.bbox[0]}, ${r.bbox[1]}, ${r.bbox[2]}, ${r.bbox[3]})
            </td>
        </tr>
    `).join('');
}

// ---- 识别结果折叠 ----

function toggleResult() {
    const panel = document.getElementById('resultPanel');
    const toggle = document.getElementById('resultToggle');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        toggle.textContent = '收起 ▴';
    } else {
        panel.style.display = 'none';
        toggle.textContent = '展开 ▾';
    }
}

// ---- 折叠 ----

function toggleHistory() {
    const panel = document.getElementById('historyPanel');
    const toggle = document.getElementById('historyToggle');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        toggle.textContent = '收起 ▴';
        queryHistory();
    } else {
        panel.style.display = 'none';
        toggle.textContent = '展开 ▾';
    }
}

// ---- 查询 ----

async function queryHistory() {
    const start = document.getElementById('filterDateStart').value;
    const end = document.getElementById('filterDateEnd').value;
    const name = document.getElementById('filterName').value.trim();

    const params = new URLSearchParams();
    if (start) params.set('date_start', start);
    if (end) params.set('date_end', end);
    if (name) params.set('name', name);
    params.set('_t', Date.now());

    try {
        const resp = await fetch(API_BASE + '/activity?' + params, {cache: 'no-store'});
        const data = await resp.json();
        if (data.data && data.data.activities) {
            historyData = data.data.activities.slice();
        } else {
            historyData = [];
        }
        historyPage = 0;
        document.getElementById('selectAll').checked = false;
        renderHistoryPage();
        updateFreqStats();
    } catch (e) {
        showToast('查询失败', 'error');
    }
}

function renderHistoryPage() {
    const tbody = document.getElementById('historyBody');
    const pager = document.getElementById('historyPager');
    const totalPages = Math.ceil(historyData.length / PAGE_SIZE) || 1;
    if (historyPage >= totalPages) historyPage = totalPages - 1;
    const start = historyPage * PAGE_SIZE;
    const page = historyData.slice(start, start + PAGE_SIZE);

    if (page.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">无记录</td></tr>';
    } else {
        tbody.innerHTML = page.map((a, i) => {
            const safeName = a.name.replace(/'/g, "\\'");
            return `<tr>
                <td><input type="checkbox" class="activity-check" data-id="${a.id}" onchange="updateFreqStats()"></td>
                <td>${a.name}</td>
                <td style="font-size:12px;">${(a.time || '').slice(0,10)}</td>
                <td>${a.participant_count || 0}</td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-sm btn-outline" onclick="showParticipants(${a.id},'${safeName}')">查看</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteActivityRecord(${a.id},'${safeName}')">删除</button>
                </td>
            </tr>`;
        }).join('');
    }

    // 翻页（独立容器）
    if (historyData.length > PAGE_SIZE) {
        document.getElementById('historyPager').innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; font-size:13px; color:var(--text-muted);">
            <span>共 ${historyData.length} 条</span>
            <div style="display:flex; gap:6px;">
                <button class="btn btn-sm btn-outline" onclick="historyPage=0;renderHistoryPage();updateFreqStats();" ${historyPage===0?'disabled':''}>«</button>
                <button class="btn btn-sm btn-outline" onclick="historyPage--;renderHistoryPage();updateFreqStats();" ${historyPage===0?'disabled':''}>‹</button>
                <span style="padding:4px 8px;">${historyPage+1}/${totalPages}</span>
                <button class="btn btn-sm btn-outline" onclick="historyPage++;renderHistoryPage();updateFreqStats();" ${historyPage>=totalPages-1?'disabled':''}>›</button>
                <button class="btn btn-sm btn-outline" onclick="historyPage=${totalPages-1};renderHistoryPage();updateFreqStats();" ${historyPage>=totalPages-1?'disabled':''}>»</button>
            </div>
        </div>`;
    } else {
        document.getElementById('historyPager').innerHTML = '';
    }
}

function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.activity-check').forEach(cb => cb.checked = checked);
    updateFreqStats();
}

// ---- 频次统计 ----

async function updateFreqStats() {
    const checked = document.querySelectorAll('.activity-check:checked');
    const ids = Array.from(checked).map(cb => parseInt(cb.dataset.id));

    if (ids.length === 0) {
        // 没有勾选 = 统计全部
        await loadFreqStats([]);
    } else {
        await loadFreqStats(ids);
    }
}

async function loadFreqStats(activityIds) {
    try {
        const resp = await fetch(API_BASE + '/activity/freq-stats', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({activity_ids: activityIds}),
        });
        const data = await resp.json();
        if (data.code === 0) {
            renderFreqStats(data.data.stats);
        }
    } catch (e) {
        document.getElementById('freqStats').textContent = '加载失败';
    }
}

function renderFreqStats(stats) {
    if (!stats || stats.length === 0) {
        document.getElementById('freqStats').textContent = '暂无参与数据';
        document.getElementById('freqTable').innerHTML = '';
        if (freqChart) { freqChart.destroy(); freqChart = null; }
        return;
    }

    document.getElementById('freqStats').textContent = `统计 ${stats.length} 人，共 ${stats.reduce((s,x)=>s+x.count,0)} 人次`;

    // 柱状图
    const ctx = document.getElementById('freqChart');
    if (freqChart) freqChart.destroy();
    const top = stats.slice(0, 15);
    freqChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top.map(s => s.name || s.student_id),
            datasets: [{
                label: '参与次数',
                data: top.map(s => s.count),
                backgroundColor: '#4f46e5',
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { stepSize: 1 } } }
        }
    });

    // 表格
    document.getElementById('freqTable').innerHTML = `
        <table>
            <thead><tr><th>学号</th><th>姓名</th><th>次数</th></tr></thead>
            <tbody>${stats.map(s => `<tr><td>${s.student_id}</td><td>${s.name || '-'}</td><td>${s.count}</td></tr>`).join('')}</tbody>
        </table>`;
}

// ---- 合并导出 ----

async function exportMerged() { exportMergedDo('excel'); }
async function exportMergedCSV() { exportMergedDo('csv'); }

async function exportMergedDo(fmt) {
    const checked = document.querySelectorAll('.activity-check:checked');
    const ids = Array.from(checked).map(cb => parseInt(cb.dataset.id));

    try {
        const resp = await fetch(API_BASE + '/activity/merged-export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({activity_ids: ids, format: fmt}),
        });
        if (!resp.ok) { showToast('导出失败，无数据', 'error'); return; }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'activity_merged.' + (fmt === 'csv' ? 'csv' : 'xlsx');
        a.click();
        URL.revokeObjectURL(url);
        showToast('导出成功', 'success');
    } catch (e) {
        showToast('导出失败', 'error');
    }
}

// ---- 参与人员弹窗 ----

async function showParticipants(activityId, activityName) {
    document.getElementById('participantsTitle').textContent = activityName + ' — 参与人员';
    document.getElementById('participantsBody').innerHTML = '<p style="color:var(--text-muted);">加载中...</p>';
    document.getElementById('participantsModal').classList.add('show');

    try {
        const resp = await fetch(API_BASE + '/activity/' + activityId + '/participants?_t=' + Date.now());
        const data = await resp.json();

        if (data.data && data.data.participants && data.data.participants.length > 0) {
            let html = '<table><thead><tr><th>学号</th><th>姓名</th><th>情绪</th></tr></thead><tbody>';
            data.data.participants.forEach(p => {
                html += `<tr><td>${p.student_id}</td><td>${p.name || '-'}</td><td>${emoMap[p.emotion] || p.emotion || '-'}</td></tr>`;
            });
            html += '</tbody></table>';
            html += `<p style="font-size:12px;color:var(--text-muted);margin-top:8px;">共 ${data.data.participants.length} 人</p>`;
            document.getElementById('participantsBody').innerHTML = html;
        } else {
            document.getElementById('participantsBody').innerHTML = '<p style="color:var(--text-muted);">暂无参与人员</p>';
        }
    } catch (e) {
        document.getElementById('participantsBody').innerHTML = '<p style="color:var(--danger);">加载失败</p>';
    }
}

function closeParticipantsModal() {
    document.getElementById('participantsModal').classList.remove('show');
}

function closeParticipantsModalOutside(e) {
    if (e.target === document.getElementById('participantsModal')) {
        closeParticipantsModal();
    }
}

// ---- 删除活动 ----

async function deleteActivityRecord(activityId, activityName) {
    if (!confirm(`确定删除活动「${activityName}」及其所有参与记录吗？\n此操作不可恢复。`)) return;

    try {
        const resp = await fetch(API_BASE + '/activity/' + activityId, {method: 'DELETE'});
        const result = await resp.json();
        if (result.code === 0) {
            showToast('已删除', 'success');
            queryHistory();
        } else {
            showToast(result.msg, 'error');
        }
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

// ---- Toast ----

function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
}
