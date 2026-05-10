// === 数据查询页面逻辑 ===

const API_BASE = '/api';
let emotionChart = null;

// ---- 查询 ----

async function queryAll() {
    const date = document.getElementById('filterDate').value;
    const studentId = document.getElementById('filterStudentId').value.trim();

    const params = new URLSearchParams();
    if (date) params.set('date', date);
    if (studentId) params.set('student_id', studentId);
    params.set('_t', Date.now());  // 防止浏览器缓存

    // 并行请求
    const [attResp, emoResp, stuResp] = await Promise.all([
        fetch(API_BASE + '/attendance?' + params, {cache: 'no-store'}),
        fetch(API_BASE + '/emotion?' + params, {cache: 'no-store'}),
        fetch(API_BASE + '/students?_t=' + Date.now(), {cache: 'no-store'}),
    ]);

    const attData = await attResp.json();
    const emoData = await emoResp.json();
    const stuData = await stuResp.json();

    renderAttendance(attData);
    renderEmotionChart(emoData);
    updateStats(attData, emoData, stuData);
}

function updateStats(attData, emoData, stuData) {
    document.getElementById('statAttendance').textContent =
        attData.data?.total ?? '-';
    document.getElementById('statEmotion').textContent =
        emoData.data?.total ?? '-';
    document.getElementById('statStudents').textContent =
        stuData.data?.total ?? '-';
}

// ---- 考勤表格 ----

function renderAttendance(data) {
    const tbody = document.getElementById('attendanceBody');
    if (!data.data || !data.data.records || data.data.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">无记录</td></tr>';
        return;
    }
    const emoMap = {angry:'愤怒',disgust:'厌恶',fear:'恐惧',happy:'高兴',sad:'悲伤',surprise:'惊讶',neutral:'中性'};
    tbody.innerHTML = data.data.records.map(r => `
        <tr>
            <td>${r.student_id}</td>
            <td>${r.name || '-'}</td>
            <td style="font-size:12px;">${r.time || ''}</td>
            <td><span class="${r.status === 'present' ? 'text-success' : 'text-danger'}">${r.status === 'present' ? '出勤' : r.status}</span></td>
            <td>${emoMap[r.emotion] || r.emotion || '-'}</td>
        </tr>
    `).join('');
}

// ---- 情绪图表 ----

function renderEmotionChart(data) {
    const canvas = document.getElementById('emotionChart');
    const emptyMsg = document.getElementById('emotionEmpty');

    const cnMap = {
        angry: '愤怒', disgust: '厌恶', fear: '恐惧',
        happy: '高兴', sad: '悲伤', surprise: '惊讶', neutral: '中性'
    };

    if (!data.data || !data.data.stats || data.data.stats.length === 0) {
        canvas.style.display = 'none';
        emptyMsg.style.display = 'block';
        return;
    }
    canvas.style.display = 'block';
    emptyMsg.style.display = 'none';

    const labels = data.data.stats.map(s => cnMap[s.emotion] || s.emotion);
    const values = data.data.stats.map(s => s.count);
    const colors = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#6b7280'];

    if (emotionChart) emotionChart.destroy();

    emotionChart = new Chart(canvas, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 16 } }
            }
        }
    });
}

// ---- 学生列表弹窗 ----

let studentListData = [];
let studentPage = 0;
const PAGE_SIZE = 10;

async function openStudentListModal() {
    document.getElementById('studentListModal').classList.add('show');
    studentPage = 0;
    await loadStudentList();
}

function closeStudentListModal() {
    document.getElementById('studentListModal').classList.remove('show');
}

function closeStudentListModalOutside(e) {
    if (e.target === document.getElementById('studentListModal')) {
        closeStudentListModal();
    }
}

async function loadStudentList() {
    document.getElementById('studentListBody').innerHTML = '<p style="color:var(--text-muted);">加载中...</p>';

    try {
        const resp = await fetch(API_BASE + '/students?' + Date.now(), {cache: 'no-store'});
        const data = await resp.json();
        studentListData = (data.data && data.data.students) ? data.data.students : [];
        studentPage = 0;
        renderStudentPage();
    } catch (e) {
        document.getElementById('studentListBody').innerHTML = '<p style="color:var(--danger);">加载失败</p>';
    }
}

function filterStudents() {
    studentPage = 0;
    renderStudentPage();
}

function renderStudentPage() {
    const keyword = (document.getElementById('studentSearch')?.value || '').trim().toLowerCase();
    let filtered = studentListData;
    if (keyword) {
        filtered = studentListData.filter(s =>
            s.student_id.toLowerCase().includes(keyword) ||
            s.name.toLowerCase().includes(keyword)
        );
    }

    const totalPages = Math.ceil(filtered.length / PAGE_SIZE) || 1;
    if (studentPage >= totalPages) studentPage = totalPages - 1;
    const start = studentPage * PAGE_SIZE;
    const page = filtered.slice(start, start + PAGE_SIZE);

    let html = '';

    if (page.length === 0) {
        html += '<p style="color:var(--text-muted);text-align:center;padding:16px;">' + (keyword ? '无匹配结果' : '暂无注册学生') + '</p>';
    } else {
        html += '<table><thead><tr><th>学号</th><th>姓名</th><th style="width:130px;">操作</th></tr></thead><tbody>';
        page.forEach(s => {
            html += `<tr>
                <td>${s.student_id}</td>
                <td><span id="name-${s.student_id}">${s.name}</span>
                    <input id="edit-${s.student_id}" value="${s.name}" style="display:none;width:80px;padding:4px 8px;border:1px solid var(--border);border-radius:6px;font-size:13px;">
                </td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-sm btn-outline" id="btnEdit-${s.student_id}" onclick="startEdit('${s.student_id}')">编辑</button>
                    <button class="btn btn-sm btn-outline" id="btnSave-${s.student_id}" onclick="saveEdit('${s.student_id}')" style="display:none;">保存</button>
                    <button class="btn btn-sm btn-outline" id="btnCancel-${s.student_id}" onclick="cancelEdit('${s.student_id}')" style="display:none;">取消</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteStudent('${s.student_id}')">删除</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';

        // 翻页
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;font-size:13px;color:var(--text-muted);">';
        html += `<span>共 ${filtered.length} 人`;
        if (keyword) html += `（搜索自 ${studentListData.length} 人）`;
        html += '</span>';
        html += '<div style="display:flex;gap:6px;">';
        html += `<button class="btn btn-sm btn-outline" onclick="studentPage=0;renderStudentPage();" ${studentPage===0?'disabled':''}>«</button>`;
        html += `<button class="btn btn-sm btn-outline" onclick="studentPage--;renderStudentPage();" ${studentPage===0?'disabled':''}>‹</button>`;
        html += `<span style="padding:4px 8px;">${studentPage+1}/${totalPages}</span>`;
        html += `<button class="btn btn-sm btn-outline" onclick="studentPage++;renderStudentPage();" ${studentPage>=totalPages-1?'disabled':''}>›</button>`;
        html += `<button class="btn btn-sm btn-outline" onclick="studentPage=${totalPages-1};renderStudentPage();" ${studentPage>=totalPages-1?'disabled':''}>»</button>`;
        html += '</div></div>';
    }

    document.getElementById('studentListBody').innerHTML = html;
}

function startEdit(sid) {
    document.getElementById('name-' + sid).style.display = 'none';
    document.getElementById('edit-' + sid).style.display = 'inline';
    document.getElementById('btnEdit-' + sid).style.display = 'none';
    document.getElementById('btnSave-' + sid).style.display = 'inline';
    document.getElementById('btnCancel-' + sid).style.display = 'inline';
    document.getElementById('edit-' + sid).focus();
}

function cancelEdit(sid) {
    document.getElementById('name-' + sid).style.display = 'inline';
    document.getElementById('edit-' + sid).style.display = 'none';
    document.getElementById('btnEdit-' + sid).style.display = 'inline';
    document.getElementById('btnSave-' + sid).style.display = 'none';
    document.getElementById('btnCancel-' + sid).style.display = 'none';
}

async function saveEdit(sid) {
    const newName = document.getElementById('edit-' + sid).value.trim();
    if (!newName) return;

    try {
        const resp = await fetch(API_BASE + '/student', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({student_id: sid, name: newName})
        });
        const result = await resp.json();
        if (result.code === 0) {
            document.getElementById('name-' + sid).textContent = newName;
            cancelEdit(sid);
            showToast('姓名已更新', 'success');
        } else {
            showToast(result.msg, 'error');
        }
    } catch (e) {
        showToast('请求失败', 'error');
    }
}

async function deleteStudent(sid) {
    if (!confirm(`确定删除学号为 ${sid} 的学生及其所有记录吗？此操作不可恢复。`)) return;

    try {
        const resp = await fetch(API_BASE + '/student?student_id=' + sid, {method: 'DELETE'});
        const result = await resp.json();
        if (result.code === 0) {
            showToast('已删除', 'success');
            loadStudentList();
            queryAll();  // 刷新概览数据
        } else {
            showToast(result.msg, 'error');
        }
    } catch (e) {
        showToast('请求失败', 'error');
    }
}

function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
}

// ---- 导出 ----

async function exportData(fmt) {
    const date = document.getElementById('filterDate').value;
    const studentId = document.getElementById('filterStudentId').value.trim();
    const params = new URLSearchParams();
    if (date) params.set('date', date);
    if (studentId) params.set('student_id', studentId);
    params.set('format', fmt);
    params.set('_t', Date.now());

    try {
        const resp = await fetch(API_BASE + '/export?' + params, {cache: 'no-store'});
        if (!resp.ok) {
            showToast('导出失败，无数据', 'error');
            return;
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'attendance_export.' + (fmt === 'csv' ? 'csv' : 'xlsx');
        a.click();
        URL.revokeObjectURL(url);
        showToast('导出成功', 'success');
    } catch (e) {
        showToast('导出失败: ' + e.message, 'error');
    }
}

// 首次加载兜底数据
queryAll();
