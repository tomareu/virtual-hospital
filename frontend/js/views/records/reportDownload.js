// --- MODULE: record report download ---

import { createReport, fetchOriginalRecordPdf, fetchReportPdf } from '../../api/reports.js';
import { getTurnstileToken } from '../../api/turnstile.js';
import { getLocale } from '../../i18n.js';
import { downloadBlob } from '../../utils/dom.js';

const ORIGINAL_RECORD_FALLBACK_CODES = ['report_budget_exhausted', 'report_unavailable'];

const reportFilename = (patient, record, language) =>
    `mlvh-${patient.location}-${patient.id_number}-${record.id}-${language}.pdf`;

const downloadReportPdf = async (patient, record, language) => {
    downloadBlob(await fetchReportPdf(record.id, language), reportFilename(patient, record, language));
};

export const downloadRecordReport = async (patient, record) => {
    const language = getLocale();

    try {
        await downloadReportPdf(patient, record, language);
        return { original: false };
    } catch (error) {
        if (error.code !== 'report_not_found') throw error;
    }

    try {
        await createReport(record.id, language, await getTurnstileToken());
    } catch (error) {
        if (!ORIGINAL_RECORD_FALLBACK_CODES.includes(error.code)) throw error;
        downloadBlob(await fetchOriginalRecordPdf(record.id), reportFilename(patient, record, record.language));
        return { original: true };
    }

    await downloadReportPdf(patient, record, language);
    return { original: false };
};
