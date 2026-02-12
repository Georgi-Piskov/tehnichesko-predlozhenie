/**
 * Main Application Logic
 */

// ===== Configuration =====
const CONFIG = {
    // Set this to your n8n webhook base URL
    N8N_WEBHOOK_URL: 'https://n8n.simeontsvetanovn8nworkflows.site',
    POLL_INTERVAL: 4000, // Poll every 4 seconds
    MAX_POLL_TIME: 30 * 60 * 1000 // 30 minute timeout
};

let currentStep = 1;
let currentJobId = null;
let pollTimer = null;

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    API.init(CONFIG.N8N_WEBHOOK_URL);
    FileUpload.init();
    loadSavedContractor();
});

// ===== Step Navigation =====
function goToStep(step) {
    // Validate before moving forward
    if (step > currentStep) {
        if (currentStep === 1 && !validateStep1()) return;
        if (currentStep === 2 && !validateStep2()) return;
    }

    // Update step indicators
    document.querySelectorAll('.step-item').forEach(item => {
        const s = parseInt(item.dataset.step);
        item.classList.remove('active', 'completed');
        if (s === step) item.classList.add('active');
        else if (s < step) item.classList.add('completed');
    });

    // Show/hide panels
    document.querySelectorAll('.section-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`step${step}`).classList.add('active');

    currentStep = step;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== Validation =====
function validateStep1() {
    const required = ['companyName', 'companyEik', 'companyAddress', 'companyManager'];
    const labels = {
        companyName: 'Наименование на фирмата',
        companyEik: 'ЕИК',
        companyAddress: 'Адрес',
        companyManager: 'Управител'
    };

    for (const id of required) {
        const value = document.getElementById(id).value.trim();
        if (!value) {
            showToast(`Моля, попълнете полето "${labels[id]}".`, 'warning');
            document.getElementById(id).focus();
            return false;
        }
    }

    // Save contractor info for reuse
    saveContractor();
    return true;
}

function validateStep2() {
    if (!FileUpload.docFile) {
        showToast('Моля, качете документацията по обществената поръчка.', 'warning');
        return false;
    }
    if (!FileUpload.specFile) {
        showToast('Моля, качете техническата спецификация.', 'warning');
        return false;
    }
    return true;
}

// ===== Save/Load Contractor (localStorage) =====
function saveContractor() {
    const data = getContractorInfo();
    localStorage.setItem('tp_contractor', JSON.stringify(data));
}

function loadSavedContractor() {
    const saved = localStorage.getItem('tp_contractor');
    if (!saved) return;

    try {
        const data = JSON.parse(saved);
        if (data.name) document.getElementById('companyName').value = data.name;
        if (data.eik) document.getElementById('companyEik').value = data.eik;
        if (data.address) document.getElementById('companyAddress').value = data.address;
        if (data.manager) document.getElementById('companyManager').value = data.manager;
        if (data.phone) document.getElementById('companyPhone').value = data.phone;
        if (data.email) document.getElementById('companyEmail').value = data.email;
        if (data.description) document.getElementById('companyDescription').value = data.description;
    } catch (e) {
        // Ignore parse errors
    }
}

function getContractorInfo() {
    return {
        name: document.getElementById('companyName').value.trim(),
        eik: document.getElementById('companyEik').value.trim(),
        address: document.getElementById('companyAddress').value.trim(),
        manager: document.getElementById('companyManager').value.trim(),
        phone: document.getElementById('companyPhone').value.trim(),
        email: document.getElementById('companyEmail').value.trim(),
        description: document.getElementById('companyDescription').value.trim()
    };
}

// ===== Generation =====
async function startGeneration() {
    if (!validateStep2()) return;

    const contractorInfo = getContractorInfo();
    const additionalNotes = document.getElementById('additionalNotes').value.trim();
    const formData = FileUpload.buildFormData(contractorInfo, additionalNotes);

    // Move to step 3
    goToStep(3);
    resetProgress();

    try {
        // Submit job
        updatePhase('upload', 'active');
        const response = await API.submitJob(formData);
        currentJobId = response.jobId;
        updatePhase('upload', 'completed');

        // Start polling
        startPolling();

    } catch (error) {
        updatePhase('upload', 'error');
        showToast(`Грешка: ${error.message}`, 'error');
        console.error('Submit error:', error);
    }
}

// ===== Progress Polling =====
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    const startTime = Date.now();

    pollTimer = setInterval(async () => {
        // Timeout check
        if (Date.now() - startTime > CONFIG.MAX_POLL_TIME) {
            clearInterval(pollTimer);
            showToast('Времето за изчакване изтече. Моля, опитайте отново.', 'error');
            return;
        }

        try {
            const status = await API.getJobStatus(currentJobId);
            handleStatusUpdate(status);

            if (status.status === 'completed') {
                clearInterval(pollTimer);
                onGenerationComplete(status);
            } else if (status.status === 'error') {
                clearInterval(pollTimer);
                onGenerationError(status);
            }
        } catch (error) {
            console.error('Polling error:', error);
            // Don't stop polling on transient errors
        }
    }, CONFIG.POLL_INTERVAL);
}

function handleStatusUpdate(status) {
    const phaseMap = {
        'uploading': 'upload',
        'extracting_requirements': 'extract',
        'analyzing_spec': 'analyze',
        'planning': 'plan',
        'writing': 'write',
        'validating': 'validate',
        'finalizing': 'finalize',
        'exporting': 'export'
    };

    const currentPhase = phaseMap[status.phase] || status.phase;

    // Update progress bar
    if (status.progress !== undefined) {
        document.getElementById('progressBar').style.width = `${status.progress}%`;
    }

    // Update progress text
    if (status.message) {
        document.getElementById('progressText').textContent = status.message;
    }

    // Update phases
    const phases = ['upload', 'extract', 'analyze', 'plan', 'write', 'validate', 'finalize', 'export'];
    const currentIdx = phases.indexOf(currentPhase);

    phases.forEach((phase, idx) => {
        if (idx < currentIdx) {
            updatePhase(phase, 'completed');
        } else if (idx === currentIdx) {
            updatePhase(phase, 'active');
            // Update writing progress
            if (phase === 'write' && status.writingProgress) {
                const phaseEl = document.querySelector(`[data-phase="write"] span:last-child`);
                if (phaseEl) {
                    phaseEl.textContent = `Писане на секции (${status.writingProgress.current}/${status.writingProgress.total})`;
                }
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
async function onGenerationComplete(status) {
    // Update all phases to completed
    document.querySelectorAll('.phase-item').forEach(item => {
        item.classList.remove('active');
        item.classList.add('completed');
        item.querySelector('.phase-icon').textContent = '✅';
    });

    document.getElementById('progressBar').style.width = '100%';
    document.getElementById('progressText').textContent = 'Готово!';

    // Update stats
    if (status.result && status.result.stats) {
        document.getElementById('statPages').textContent = status.result.stats.estimatedPages || '—';
        document.getElementById('statSections').textContent = status.result.stats.sections || '—';
        document.getElementById('statPlaceholders').textContent = status.result.stats.placeholderCount || '—';
    }

    showToast('Техническото предложение е генерирано успешно!', 'success');

    // Small delay for UX
    setTimeout(() => goToStep(4), 1500);
}

function onGenerationError(status) {
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
        const data = await API.getPreview(currentJobId);
        const content = document.getElementById('previewContent');

        // Render HTML with placeholder highlighting
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
async function downloadResult(format) {
    try {
        showToast('Изтегляне...', 'success');
        const blob = await API.downloadDocx(currentJobId);

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Техническо_предложение_${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast(`Грешка при изтегляне: ${error.message}`, 'error');
    }
}

// ===== Toast Notifications =====
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
