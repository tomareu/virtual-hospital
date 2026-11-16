// --- API layer: reports ---
import { getApiBaseUrl } from '../config.js';
import { t } from '../i18n.js';
import { buildErrorFromResponse } from './errors.js';

const recordsUrl = async (path) => `${await getApiBaseUrl()}/reports/records/${path}`;

const fetchPdf = async (path) => {
    const query = new URLSearchParams({ tz: Intl.DateTimeFormat().resolvedOptions().timeZone });
    const response = await fetch(`${await recordsUrl(path)}?${query}`);
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.downloadReport'));
    }
    return response.blob();
};

export const fetchReportPdf = (recordId, language) => fetchPdf(`${recordId}/${language}/pdf/`);

export const fetchOriginalRecordPdf = (recordId) => fetchPdf(`${recordId}/pdf/`);

export const createReport = async (recordId, language, turnstileToken) => {
    const response = await fetch(await recordsUrl(`${recordId}/`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, turnstile_token: turnstileToken }),
    });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.downloadReport'));
    }
};
