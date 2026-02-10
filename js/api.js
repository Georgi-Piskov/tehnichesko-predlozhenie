/**
 * API module — communication with n8n webhooks
 */
const API = {
    // n8n webhook base URL — will be configured
    BASE_URL: '',

    /**
     * Initialize API with the n8n webhook URL
     */
    init(baseUrl) {
        this.BASE_URL = baseUrl.replace(/\/+$/, '');
    },

    /**
     * Submit the technical proposal generation request
     * @param {FormData} formData - Contains files and contractor info
     * @returns {Promise<{jobId: string}>}
     */
    async submitJob(formData) {
        const response = await fetch(`${this.BASE_URL}/webhook/generate-proposal`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Грешка при изпращане: ${response.status} — ${error}`);
        }

        return response.json();
    },

    /**
     * Poll for job status
     * @param {string} jobId
     * @returns {Promise<{status, phase, progress, message, result?}>}
     */
    async getJobStatus(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/job-status?jobId=${encodeURIComponent(jobId)}`);

        if (!response.ok) {
            throw new Error(`Грешка при проверка на статус: ${response.status}`);
        }

        return response.json();
    },

    /**
     * Download the generated DOCX file
     * @param {string} jobId
     * @returns {Promise<Blob>}
     */
    async downloadDocx(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/download?jobId=${encodeURIComponent(jobId)}&format=docx`);

        if (!response.ok) {
            throw new Error(`Грешка при изтегляне: ${response.status}`);
        }

        return response.blob();
    },

    /**
     * Get the generated document preview (HTML)
     * @param {string} jobId
     * @returns {Promise<{html: string, stats: object}>}
     */
    async getPreview(jobId) {
        const response = await fetch(`${this.BASE_URL}/webhook/preview?jobId=${encodeURIComponent(jobId)}`);

        if (!response.ok) {
            throw new Error(`Грешка при зареждане на преглед: ${response.status}`);
        }

        return response.json();
    }
};
