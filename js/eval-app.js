/**
 * Evaluation App — combined API, file upload & app logic
 */

// ===== Configuration =====
const EVAL_CONFIG = {
    N8N_WEBHOOK_URL: 'https://n8n.simeontsvetanovn8nworkflows.site',
    POLL_INTERVAL: 4000,
    MAX_POLL_TIME: 90 * 60 * 1000
};

// ===== API =====
const EvalAPI = {
    BASE_URL: '',

    init(baseUrl) {
        this.BASE_URL = baseUrl.replace(/\/+$/, '');
    },

    async submitJob(formData) {
        const response = await fetch(`${this.BASE_URL}/webhook/eval-generate`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Грешка при изпращане: ${response.status} — ${error}`);
        }
        return response.json();
    },

    async getJobStatus(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/job-status?jobId=${encodeURIComponent(jobId)}`);
        if (!response.ok) {
            throw new Error(`Грешка при проверка на статус: ${response.status}`);
        }
        return response.json();
    },

    async getPreview(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/preview?jobId=${encodeURIComponent(jobId)}`);
        if (!response.ok) {
            throw new Error(`Грешка при зареждане на преглед: ${response.status}`);
        }
        return response.json();
    },

    async downloadReport(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/download?jobId=${encodeURIComponent(jobId)}&format=md`);
        if (!response.ok) {
            throw new Error(`Грешка при изтегляне: ${response.status}`);
        }
        return response.blob();
    }
};

// ===== File Upload =====
const EvalFileUpload = {
    reqFile: null,
    propFile: null,

    init() {
        this.setupZone('reqUploadZone', 'reqFile', 'reqFileInfo', 'req');
        this.setupZone('propUploadZone', 'propFile', 'propFileInfo', 'prop');
    },

    setupZone(zoneId, inputId, infoId, type) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);
        const infoDiv = document.getElementById(infoId);
        if (!zone || !input) return;

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) this.handleFile(file, type, zone, infoDiv);
        });
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleFile(file, type, zone, infoDiv);
        });
    },

    handleFile(file, type, zone, infoDiv) {
        const validTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword'
        ];
        if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|docx|doc)$/i)) {
            showToast('Моля, качете PDF или DOCX файл.', 'error');
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            showToast('Файлът е твърде голям. Максимален размер: 50MB.', 'error');
            return;
        }

        if (type === 'req') this.reqFile = file;
        else this.propFile = file;

        zone.style.display = 'none';
        infoDiv.style.display = 'block';
        infoDiv.innerHTML = `
            <div class="file-info">
                <span style="font-size: 1.5rem;">📄</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${this.formatSize(file.size)}</span>
                <button class="file-remove" onclick="EvalFileUpload.removeFile('${type}')" title="Премахни">✕</button>
            </div>
        `;
        showToast(`Файлът "${file.name}" е качен успешно.`, 'success');
    },

    removeFile(type) {
        if (type === 'req') {
            this.reqFile = null;
            document.getElementById('reqUploadZone').style.display = '';
            document.getElementById('reqFileInfo').style.display = 'none';
            document.getElementById('reqFile').value = '';
        } else {
            this.propFile = null;
            document.getElementById('propUploadZone').style.display = '';
            document.getElementById('propFileInfo').style.display = 'none';
            document.getElementById('propFile').value = '';
        }
    },

    formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    buildFormData(evaluationNotes) {
        const formData = new FormData();
        if (this.reqFile) formData.append('requirements', this.reqFile);
        if (this.propFile) formData.append('proposal', this.propFile);
        if (evaluationNotes) formData.append('evaluationNotes', evaluationNotes);
        return formData;
    }
};

// ===== App State =====
let evalCurrentStep = 1;
let evalJobId = null;
let evalPollTimer = null;
let evalPollStartTime = null;
let evalNotFoundCount = 0;

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    EvalAPI.init(EVAL_CONFIG.N8N_WEBHOOK_URL);
    EvalFileUpload.init();
});

// ===== Step Navigation =====
function goToStep(step) {
    if (step > evalCurrentStep) {
        if (evalCurrentStep === 1 && !validateStep1()) return;
    }

    document.querySelectorAll('.step-item').forEach(item => {
        const s = parseInt(item.dataset.step);
        item.classList.remove('active', 'completed');
        if (s === step) item.classList.add('active');
        else if (s < step) item.classList.add('completed');
    });

    document.querySelectorAll('.section-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`step${step}`).classList.add('active');

    evalCurrentStep = step;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== Validation =====
function validateStep1() {
    if (!EvalFileUpload.reqFile) {
        showToast('Моля, качете документацията на възложителя (изисквания).', 'warning');
        return false;
    }
    if (!EvalFileUpload.propFile) {
        showToast('Моля, качете техническото предложение на кандидата.', 'warning');
        return false;
    }
    return true;
}

// ===== Generation =====
async function startEvaluation() {
    if (!validateStep1()) return;

    const evaluationNotes = document.getElementById('evaluationNotes').value.trim();
    const formData = EvalFileUpload.buildFormData(evaluationNotes);

    goToStep(2);
    resetProgress();

    try {
        updatePhase('upload', 'active');
        const response = await EvalAPI.submitJob(formData);
        evalJobId = response.jobId;
        updatePhase('upload', 'completed');
        startPolling();
    } catch (error) {
        updatePhase('upload', 'error');
        showToast(`Грешка: ${error.message}`, 'error');
    }
}

// ===== Polling =====
function startPolling() {
    if (evalPollTimer) clearInterval(evalPollTimer);
    evalPollStartTime = Date.now();
    evalNotFoundCount = 0;

    setTimeout(() => {
        doPoll();
        evalPollTimer = setInterval(doPoll, EVAL_CONFIG.POLL_INTERVAL);
    }, 8000);
}

async function doPoll() {
    if (Date.now() - evalPollStartTime > EVAL_CONFIG.MAX_POLL_TIME) {
        clearInterval(evalPollTimer);
        showToast('Времето за изчакване изтече.', 'error');
        showManualRefresh();
        return;
    }

    try {
        const status = await EvalAPI.getJobStatus(evalJobId);
        handleStatusUpdate(status);

        if (status.status === 'completed') {
            clearInterval(evalPollTimer);
            onEvaluationComplete(status);
        } else if (status.status === 'error') {
            clearInterval(evalPollTimer);
            onEvaluationError(status);
        }
    } catch (error) {
        console.error('Polling error:', error);
    }
}

function handleStatusUpdate(status) {
    if (status.status === 'not_found') {
        evalNotFoundCount++;
        const elapsed = Date.now() - (evalPollStartTime || Date.now());
        if (elapsed < 60000) {
            document.getElementById('progressText').textContent = 'Инициализация на заявката...';
        } else if (elapsed < 120000) {
            document.getElementById('progressText').textContent = 'Очакване на статус... Моля, изчакайте.';
        } else {
            document.getElementById('progressText').textContent = '⚠️ Няма статус. Проверете дали Status API е активиран в n8n.';
            showManualRefresh();
        }
        return;
    }

    evalNotFoundCount = 0;

    const phaseMap = {
        'uploading': 'upload',
        'extracting_requirements': 'extract',
        'analyzing_proposal': 'analyze',
        'cross_referencing': 'crossref',
        'legal_validation': 'legal',
        'generating_report': 'report',
        'exporting': 'export'
    };

    const currentPhase = phaseMap[status.phase] || status.phase;

    if (status.progress !== undefined) {
        document.getElementById('progressBar').style.width = `${status.progress}%`;
    }
    if (status.message) {
        document.getElementById('progressText').textContent = status.message;
    }

    const phases = ['upload', 'extract', 'analyze', 'crossref', 'legal', 'report', 'export'];
    const currentIdx = phases.indexOf(currentPhase);

    phases.forEach((phase, idx) => {
        if (idx < currentIdx) {
            updatePhase(phase, 'completed');
        } else if (idx === currentIdx) {
            updatePhase(phase, 'active');
            if (phase === 'crossref' && status.message) {
                const phaseEl = document.querySelector(`[data-phase="crossref"] span:last-child`);
                if (phaseEl) phaseEl.textContent = status.message;
            }
        }
    });
}

function resetProgress() {
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').textContent = 'Стартиране...';
    document.querySelectorAll('.phase-item').forEach(item => {
        item.classList.remove('active', 'completed', 'error');
        item.querySelector('.phase-icon').textContent = '⏳';
    });
}

function updatePhase(phase, status) {
    const item = document.querySelector(`[data-phase="${phase}"]`);
    if (!item) return;
    item.classList.remove('active', 'completed', 'error');
    const icon = item.querySelector('.phase-icon');
    switch (status) {
        case 'active':
            item.classList.add('active');
            icon.innerHTML = '<span class="spinner"></span>';
            break;
        case 'completed':
            item.classList.add('completed');
            icon.textContent = '✅';
            break;
        case 'error':
            item.classList.add('error');
            icon.textContent = '❌';
            break;
    }
}

// ===== Completion =====
async function onEvaluationComplete(status) {
    document.querySelectorAll('.phase-item').forEach(item => {
        item.classList.remove('active');
        item.classList.add('completed');
        item.querySelector('.phase-icon').textContent = '✅';
    });

    document.getElementById('progressBar').style.width = '100%';
    document.getElementById('progressText').textContent = 'Оценката е завършена!';

    if (status.result && status.result.stats) {
        const s = status.result.stats;
        document.getElementById('statTotal').textContent = s.totalRequirements || '—';
        document.getElementById('statCompliant').textContent = s.compliant || '0';
        document.getElementById('statPartial').textContent = s.partiallyCompliant || '0';
        document.getElementById('statNonCompliant').textContent = (s.nonCompliant || 0) + (s.missing || 0);
        document.getElementById('statDisqualify').textContent = s.disqualificationGrounds || '0';

        const recEl = document.getElementById('statRecommendation');
        const rec = s.overallRecommendation || 'N/A';
        const recMap = {
            'DISQUALIFY': { text: 'ОТСТРАНЯВАНЕ', cls: 'rec-disqualify' },
            'ACCEPT_WITH_REMARKS': { text: 'ДОПУСКАНЕ С БЕЛЕЖКИ', cls: 'rec-remarks' },
            'ACCEPT': { text: 'ДОПУСКАНЕ', cls: 'rec-accept' }
        };
        const recInfo = recMap[rec] || { text: rec, cls: '' };
        recEl.textContent = recInfo.text;
        recEl.className = 'recommendation-badge ' + recInfo.cls;
    }

    showToast('Оценката на техническото предложение е завършена!', 'success');
    setTimeout(() => goToStep(3), 1500);
}

function onEvaluationError(status) {
    showToast(`Грешка: ${status.message || 'Неизвестна грешка'}`, 'error');
}

// ===== Preview =====
let previewVisible = false;

async function togglePreview() {
    const card = document.getElementById('previewCard');
    if (previewVisible) {
        card.style.display = 'none';
        previewVisible = false;
        return;
    }

    try {
        const data = await EvalAPI.getPreview(evalJobId);
        const content = document.getElementById('previewContent');
        let html = data.html || '';
        html = html.replace(
            /\[⚠️ ПОПЪЛНЕТЕ: ([^\]]+)\]/g,
            '<span class="placeholder-highlight">[⚠️ ПОПЪЛНЕТЕ: $1]</span>'
        );
        content.innerHTML = html;
        card.style.display = 'block';
        previewVisible = true;
        card.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        showToast(`Грешка при зареждане на прегледа: ${error.message}`, 'error');
    }
}

// ===== Download =====
async function downloadResult() {
    try {
        showToast('Изтегляне...', 'success');
        const blob = await EvalAPI.downloadReport(evalJobId);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Оценка_ТП_${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast(`Грешка при изтегляне: ${error.message}`, 'error');
    }
}

// ===== Manual Refresh =====
function showManualRefresh() {
    const container = document.getElementById('progressPhases');
    if (document.getElementById('manualRefreshBtn')) return;
    const btn = document.createElement('button');
    btn.id = 'manualRefreshBtn';
    btn.className = 'btn btn-success';
    btn.style.marginTop = '1rem';
    btn.style.width = '100%';
    btn.textContent = '🔄 Провери статус';
    btn.onclick = manualCheckStatus;
    container.appendChild(btn);
}

async function manualCheckStatus() {
    if (!evalJobId) {
        showToast('Няма активна заявка.', 'error');
        return;
    }
    try {
        showToast('Проверка...', 'success');
        const status = await EvalAPI.getJobStatus(evalJobId);
        handleStatusUpdate(status);
        if (status.status === 'completed') {
            const btn = document.getElementById('manualRefreshBtn');
            if (btn) btn.remove();
            onEvaluationComplete(status);
        } else if (status.status === 'error') {
            onEvaluationError(status);
        } else {
            showToast(`Статус: ${status.message || status.phase || 'Обработка...'}`, 'success');
            startPolling();
        }
    } catch (error) {
        showToast(`Грешка: ${error.message}`, 'error');
    }
}

// ===== Toast =====
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
