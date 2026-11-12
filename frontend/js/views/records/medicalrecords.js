// --- MODULE: medical records view ---

import { fetchPatients, fetchPatientRecords, addPatientRecord } from '../../api/patients.js';
import { ApiError } from '../../api/errors.js';
import { AVATAR_BASE_PATH, DEFAULT_AVATAR } from '../../config.js';
import { escapeHtml, setAvatarWithFallback, formatDisplayDate, toLocalIsoDate, onActivate } from '../../utils/dom.js';
import {
    CONSULTATION_TYPES,
    PROFESSIONALS,
    CALENDAR_ICON,
    DIAGNOSIS_MAXLENGTH,
    DESCRIPTION_MAXLENGTH,
    PROCEDURES_MAXLENGTH,
    INDICATIONS_MAXLENGTH,
    renderOptions,
} from '../../constants/patientOptions.js';
import { formatRecordSummary } from '../../constants/recordOptions.js';
import { showToast } from '../../utils/toast.js';
import { t, tOption, getLocale } from '../../i18n.js';
import { downloadRecordReport } from './reportDownload.js';

// --- Keeps the styled date text in sync with the (visually hidden) native date input ---
const wireDateBadge = (inputId, textId) => {
    const input = document.getElementById(inputId);
    const text = document.getElementById(textId);
    if (!input || !text) return;

    text.textContent = formatDisplayDate(input.value);
    input.addEventListener('change', () => {
        text.textContent = formatDisplayDate(input.value);
    });
};

export const getMedicalRecordsView = () => {
    return `
    <div class="mlvh-card mlvh-record-search-card">
        <div class="mlvh-card-body">
            <div class="mlvh-search-field">
                <img src="/assets/icons/misc/search.svg" alt="">
                <input type="text" id="record-patient-search" class="form-control form-control-sm border-0 bg-transparent p-0" placeholder="${t('records.search')}">
            </div>
            <div id="record-search-results" class="mlvh-record-results"></div>
        </div>
    </div>

    <div id="record-history-placeholder"></div>
    `;
};

// --- Profile summary rows for the history card ---

const buildSummaryRows = (patient) => {
    const rows = [
        [t('patients.fields.species'), tOption('species', patient.species)],
        [t('patients.fields.sex'), tOption('sexes', patient.sex)],
        [t('patients.fields.pronouns'), tOption('pronouns', patient.pronouns)],
        [t('patients.fields.age'), patient.age],
        [t('patients.fields.location'), tOption('locations', patient.location)],
    ];

    return rows.map(([label, value]) => `
        <div class="mlvh-history-summary-row">
            <dt>${escapeHtml(label)}</dt>
            <dd>${escapeHtml(String(value))}</dd>
        </div>
    `).join('');
};

// --- Timeline entries for the history card ---

const buildHistoryEntries = (records) => {
    if (!records || records.length === 0) {
        return `<p class="mlvh-card-subtitle text-center mb-0">${t('records.empty')}</p>`;
    }

    return records.map((record) => {
        const recordDate = record.record_date ?? (record.created_at ? toLocalIsoDate(new Date(record.created_at)) : '');
        const professionalLabel = tOption('professionals', record.assigned_professional);

        return `
        <div class="mlvh-history-entry" data-record-id="${record.id}" role="button" tabindex="0">
            <div class="mlvh-history-entry-header">
                <span class="mlvh-history-entry-date">${escapeHtml(formatDisplayDate(recordDate))}</span>
                ${professionalLabel ? `<span class="mlvh-history-entry-professional">${escapeHtml(professionalLabel)}</span>` : ''}
            </div>
            <div class="mlvh-history-entry-text">${escapeHtml(formatRecordSummary(record))}</div>
            ${record.diagnosis ? `<div class="mlvh-history-entry-diagnosis">${t('records.diagnosis', { diagnosis: escapeHtml(record.diagnosis) })}</div>` : ''}
        </div>
        `;
    }).join('');
};

// --- Add-record form ---
const getRecordFormHTML = () => `
    <form id="record-form">
        <fieldset id="record-fieldset">
            <div class="row">
                <div class="col-6 mb-2">
                    <label class="form-label small text-muted mb-0 d-block">${t('patients.fields.consultationType')}</label>
                    <select class="form-select form-select-sm mlvh-rounded-input" id="record-consultation-type" required>
                        ${renderOptions(CONSULTATION_TYPES)}
                    </select>
                </div>
                <div class="col-6 mb-2">
                    <label class="form-label small text-muted mb-0 d-block">${t('records.fields.date')}</label>
                    <div class="mlvh-date-badge">
                        <img src="${CALENDAR_ICON}" alt="">
                        <span class="mlvh-date-badge-text" id="record-date-text"></span>
                        <input type="date" class="mlvh-date-badge-input" id="record-date" required>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="col-6 mb-2">
                    <label class="form-label small text-muted mb-0 d-block">${t('patients.fields.professional')}</label>
                    <select class="form-select form-select-sm mlvh-rounded-input" id="record-professional" required>
                        ${renderOptions(PROFESSIONALS)}
                    </select>
                </div>
                <div class="col-6 mb-2">
                    <label class="form-label small text-muted mb-0 d-block">${t('records.fields.diagnosis')}</label>
                    <input type="text" class="form-control form-control-sm mlvh-rounded-input" id="record-diagnosis" maxlength="${DIAGNOSIS_MAXLENGTH}" placeholder="${t('records.fields.optional')}">
                </div>
            </div>
            <div class="mb-2">
                <label class="form-label small text-muted mb-0 d-block">${t('patients.fields.description')}</label>
                <div class="mlvh-textarea-wrap"><textarea class="form-control form-control-sm mlvh-rounded-textarea" id="record-description" rows="2" maxlength="${DESCRIPTION_MAXLENGTH}" placeholder="${t('records.fields.descriptionPlaceholder')}" required></textarea></div>
            </div>
            <div class="mb-2">
                <label class="form-label small text-muted mb-0 d-block">${t('records.fields.procedures')}</label>
                <div class="mlvh-textarea-wrap"><textarea class="form-control form-control-sm mlvh-rounded-textarea" id="record-procedures" rows="2" maxlength="${PROCEDURES_MAXLENGTH}" placeholder="${t('records.fields.optional')}"></textarea></div>
            </div>
            <div class="mb-2">
                <label class="form-label small text-muted mb-0 d-block">${t('records.fields.indications')}</label>
                <div class="mlvh-textarea-wrap"><textarea class="form-control form-control-sm mlvh-rounded-textarea" id="record-indications" rows="2" maxlength="${INDICATIONS_MAXLENGTH}" placeholder="${t('records.fields.optional')}"></textarea></div>
            </div>
        </fieldset>
    </form>
`;

// --- LOGIC: event listeners and dom manipulation ---

export const initMedicalRecordsLogic = (initialPatientId = null) => {

    const searchInput = document.getElementById('record-patient-search');
    const resultsList = document.getElementById('record-search-results');
    const historyPlaceholder = document.getElementById('record-history-placeholder');

    let localPatients = [];
    let currentRecords = [];

    if (!searchInput || !resultsList) {
        console.error('Medical Records DOM elements not found.');
        return;
    }

    const loadPatients = async () => {
        try {
            localPatients = await fetchPatients();

            if (initialPatientId != null) {
                selectPatient(initialPatientId);
            }
        } catch (error) {
            console.error('API Error:', error);
        }
    };

    const filterPatients = (patients, query) => {
        const normalizedQuery = query.trim().toLowerCase();
        if (!normalizedQuery) return [];

        return patients.filter((patient) => {
            const displayId = `${patient.location}-${patient.id_number}`.toLowerCase();
            return patient.name.toLowerCase().includes(normalizedQuery) || displayId.includes(normalizedQuery);
        });
    };

    const renderResults = (patients) => {
        if (patients.length === 0) {
            resultsList.innerHTML = '';
            return;
        }

        resultsList.innerHTML = patients.map((patient) => {
            const displayId = `${patient.location}-${patient.id_number}`;
            return `
            <div class="mlvh-record-result-item" data-id="${patient.id}" role="button" tabindex="0" aria-label="${t('records.openHistory', { name: escapeHtml(patient.name) })}">
                <img data-avatar-src="${AVATAR_BASE_PATH}/${patient.avatar_style}.png" alt="${escapeHtml(patient.name)}" loading="lazy" decoding="async">
                <div>
                    <div class="mlvh-record-result-name">${escapeHtml(patient.name)}</div>
                    <div class="mlvh-record-result-id">${escapeHtml(displayId)}</div>
                </div>
            </div>
            `;
        }).join('');

        resultsList.querySelectorAll('.mlvh-record-result-item img').forEach((img) => {
            setAvatarWithFallback(img, img.dataset.avatarSrc, DEFAULT_AVATAR);
        });
    };

    const renderHistoryCard = (patient, records) => {
        currentRecords = records;
        const displayId = `${patient.location}-${patient.id_number}`;

        historyPlaceholder.innerHTML = `
        <div class="mlvh-card mlvh-history-card">
            <div class="mlvh-history-card-actions js-history-actions">
                <button type="button" class="btn mlvh-admit-btn shadow-sm js-add-record" aria-label="${t('records.add')}">
                    <img src="/assets/icons/misc/plus.svg" alt="" class="mlvh-btn-icon">
                </button>
            </div>
            <div class="mlvh-folder-header d-flex justify-content-between align-items-center">
                <h5 class="fw-bold mb-0 mlvh-folder-tab-title">${t('patients.details.history')}</h5>
            </div>
            <div class="mlvh-card-body">
                <div class="mlvh-history-columns">
                    <div class="text-center d-flex flex-column mlvh-profile-left-col mlvh-history-profile-col">
                        <div class="mlvh-avatar-stage">
                            <img id="history-avatar" alt="${escapeHtml(patient.name)}" class="img-fluid mb-2 mlvh-detail-avatar-img">
                        </div>
                        <h5 class="fw-bold mt-3 mb-0">${escapeHtml(patient.name)}</h5>
                        <p class="text-muted small mb-3">[${displayId}]</p>
                        <dl class="text-start mb-0">
                            ${buildSummaryRows(patient)}
                        </dl>
                    </div>
                    <div class="mlvh-history-add-mobile-row js-history-actions">
                        <button type="button" class="btn mlvh-admit-btn shadow-sm js-add-record" aria-label="${t('records.add')}">
                            <img src="/assets/icons/misc/plus.svg" alt="" class="mlvh-btn-icon">
                        </button>
                    </div>
                    <div class="mlvh-profile-right-col mlvh-history-timeline-col">
                        <div id="history-record-list" class="mlvh-history-list">
                            ${buildHistoryEntries(records)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;

        setAvatarWithFallback(
            document.getElementById('history-avatar'),
            `${AVATAR_BASE_PATH}/${patient.avatar_style}.png`,
            DEFAULT_AVATAR
        );

        historyPlaceholder.querySelectorAll('.js-add-record').forEach((btn) => {
            btn.addEventListener('click', () => {
                renderRecordForm(patient);
            });
        });

        const recordList = document.getElementById('history-record-list');
        if (recordList) {
            onActivate(recordList, '.mlvh-history-entry', (entry) => {
                const record = currentRecords.find((r) => r.id == entry.dataset.recordId);
                if (record) renderRecordDetail(patient, record);
            });
        }
    };

    const setCardActions = (extraButtons) => {
        historyPlaceholder.querySelectorAll('.js-history-actions').forEach((container) => {
            container.querySelectorAll('.js-dynamic-action').forEach((btn) => btn.remove());
            const plusBtn = container.querySelector('.js-add-record');

            extraButtons.forEach((config) => {
                const btn = document.createElement('button');
                btn.type = config.type ?? 'button';
                if (config.form) btn.setAttribute('form', config.form);
                btn.className = 'btn mlvh-admit-btn shadow-sm js-dynamic-action';
                btn.setAttribute('aria-label', config.label);
                btn.innerHTML = `<img src="${config.icon}" alt="" class="mlvh-btn-icon">`;
                if (config.onClick) btn.addEventListener('click', config.onClick);
                container.insertBefore(btn, plusBtn);
            });
        });
    };

    const renderRecordForm = (patient) => {
        const timelineCol = historyPlaceholder.querySelector('.mlvh-history-timeline-col');
        if (!timelineCol) return;

        timelineCol.innerHTML = getRecordFormHTML();
        document.getElementById('record-date').value = toLocalIsoDate();
        wireDateBadge('record-date', 'record-date-text');

        const backToHistory = async () => {
            try {
                const records = await fetchPatientRecords(patient.id);
                renderHistoryCard(patient, records);
            } catch (error) {
                console.error('API Error:', error);
            }
        };

        setCardActions([
            { icon: '/assets/icons/misc/back.svg', label: t('common.cancel'), onClick: backToHistory },
            { icon: '/assets/icons/misc/save.svg', label: t('records.save'), type: 'submit', form: 'record-form' },
        ]);

        document.getElementById('record-form').addEventListener('submit', async (event) => {
            event.preventDefault();

            const payload = {
                consultation_type: document.getElementById('record-consultation-type').value,
                assigned_professional: document.getElementById('record-professional').value,
                diagnosis: document.getElementById('record-diagnosis').value,
                record_date: document.getElementById('record-date').value,
                language: getLocale(),
                description: document.getElementById('record-description').value,
                procedures: document.getElementById('record-procedures').value,
                indications: document.getElementById('record-indications').value,
            };

            try {
                await addPatientRecord(patient.id, payload);
                showToast(t('records.saved'));
                await backToHistory();
            } catch (error) {
                console.error('API Error:', error);
                showToast(error instanceof ApiError ? error.message : t('records.saveError'), 'error');
            }
        });
    };

    const renderRecordDetail = (patient, record) => {
        const timelineCol = historyPlaceholder.querySelector('.mlvh-history-timeline-col');
        if (!timelineCol) return;

        timelineCol.innerHTML = getRecordFormHTML();

        document.getElementById('record-consultation-type').value = record.consultation_type;
        document.getElementById('record-professional').value = record.assigned_professional;
        document.getElementById('record-diagnosis').value = record.diagnosis;
        document.getElementById('record-date').value = record.record_date ?? '';
        wireDateBadge('record-date', 'record-date-text');
        document.getElementById('record-description').value = record.description;
        document.getElementById('record-procedures').value = record.procedures;
        document.getElementById('record-indications').value = record.indications;

        document.getElementById('record-fieldset').disabled = true;

        setCardActions([
            { icon: '/assets/icons/misc/back.svg', label: t('records.back'), onClick: () => renderHistoryCard(patient, currentRecords) },
            { icon: '/assets/icons/misc/download.svg', label: t('records.download'), onClick: (event) => downloadReport(event.currentTarget, patient, record) },
        ]);
    };

    const downloadReport = async (button, patient, record) => {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
        try {
            const { original } = await downloadRecordReport(patient, record);
            showToast(t(original ? 'records.downloadedOriginal' : 'records.downloaded'), original ? 'info' : 'success');
        } catch (error) {
            console.error('API Error:', error);
            showToast(error instanceof ApiError ? error.message : t('records.downloadError'), 'error');
        } finally {
            button.disabled = false;
            button.removeAttribute('aria-busy');
        }
    };

    const selectPatient = async (id) => {
        const patient = localPatients.find((p) => p.id == id);
        if (!patient) return;

        document.dispatchEvent(new CustomEvent('mlvh:sync-url', {
            detail: { route: 'medical-records', options: { patientId: patient.id } },
        }));

        searchInput.value = patient.name;
        resultsList.innerHTML = '';

        historyPlaceholder.innerHTML = `
            <div class="mlvh-card text-center py-5">
                <p class="mlvh-card-subtitle mb-0">${t('records.loading')}</p>
            </div>
        `;

        try {
            const records = await fetchPatientRecords(patient.id);
            renderHistoryCard(patient, records);
        } catch (error) {
            console.error('API Error:', error);
            historyPlaceholder.innerHTML = `
                <div class="mlvh-card text-center py-5">
                    <p class="mlvh-card-subtitle mb-0">${t('records.loadError')}</p>
                </div>
            `;
        }
    };

    searchInput.addEventListener('input', () => {
        renderResults(filterPatients(localPatients, searchInput.value));
    });

    onActivate(resultsList, '.mlvh-record-result-item', (item) => selectPatient(item.dataset.id));

    loadPatients();
};