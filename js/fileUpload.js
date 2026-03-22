/**
 * File Upload module — drag & drop + file selection handling
 */
const FileUpload = {
    docFile: null,
    specFile: null,

    init() {
        this.setupZone('docUploadZone', 'docFile', 'docFileInfo', 'doc');
        this.setupZone('specUploadZone', 'specFile', 'specFileInfo', 'spec');
    },

    setupZone(zoneId, inputId, infoId, type) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);
        const infoDiv = document.getElementById(infoId);

        if (!zone || !input) return;

        // Drag events
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

        // Click selection
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleFile(file, type, zone, infoDiv);
        });
    },

    handleFile(file, type, zone, infoDiv) {
        // Validate file type
        const validTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword'
        ];

        if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|docx|doc)$/i)) {
            showToast('Моля, качете PDF или DOCX файл.', 'error');
            return;
        }

        // Validate file size (50MB)
        if (file.size > 50 * 1024 * 1024) {
            showToast('Файлът е твърде голям. Максимален размер: 50MB.', 'error');
            return;
        }

        // Store file reference
        if (type === 'doc') {
            this.docFile = file;
        } else {
            this.specFile = file;
        }

        // Update UI
        zone.style.display = 'none';
        infoDiv.style.display = 'block';
        infoDiv.innerHTML = `
            <div class="file-info">
                <span style="font-size: 1.5rem;">📄</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${this.formatSize(file.size)}</span>
                <button class="file-remove" onclick="FileUpload.removeFile('${type}')" title="Премахни">✕</button>
            </div>
        `;

        showToast(`Файлът "${file.name}" е качен успешно.`, 'success');
    },

    removeFile(type) {
        if (type === 'doc') {
            this.docFile = null;
            document.getElementById('docUploadZone').style.display = '';
            document.getElementById('docFileInfo').style.display = 'none';
            document.getElementById('docFile').value = '';
        } else {
            this.specFile = null;
            document.getElementById('specUploadZone').style.display = '';
            document.getElementById('specFileInfo').style.display = 'none';
            document.getElementById('specFile').value = '';
        }
    },

    formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    /**
     * Build FormData with all files and contractor info
     */
    buildFormData(contractorInfo, additionalNotes, targetPages) {
        const formData = new FormData();

        if (this.docFile) {
            formData.append('documentation', this.docFile);
        }
        if (this.specFile) {
            formData.append('specification', this.specFile);
        }

        formData.append('contractor', JSON.stringify(contractorInfo));

        if (additionalNotes) {
            formData.append('additionalNotes', additionalNotes);
        }

        formData.append('targetPages', String(targetPages || 50));

        return formData;
    }
};
