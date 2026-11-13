// --- API layer ---
import { getApiBaseUrl } from '../config.js';
import { t } from '../i18n.js';
import { ApiError, buildErrorFromResponse } from './errors.js';

const patientsUrl = async (path = '') => `${await getApiBaseUrl()}/patients/${path}`;

export const fetchPatients = async () => {
    const response = await fetch(await patientsUrl());
    if (!response.ok) {
        throw new ApiError(t('api.errors.loadPatients'));
    }
    const data = await response.json();
    return Array.isArray(data) ? data : data.results;
};

export const fetchPatientRecords = async (id) => {
    const response = await fetch(await patientsUrl(`${id}/records/`));
    if (!response.ok) {
        throw new ApiError(t('api.errors.loadRecords'));
    }
    return response.json();
};

export const addPatientRecord = async (id, payload) => {
    const response = await fetch(await patientsUrl(`${id}/add_record/`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.saveRecord'));
    }
    return response.json();
};

export const completePatientRecord = async (patientId, recordId, payload) => {
    const response = await fetch(await patientsUrl(`${patientId}/records/${recordId}/complete/`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.completeRecord'));
    }
    return response.json();
};

export const createPatient = async (patientData) => {
    const response = await fetch(await patientsUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patientData),
    });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.createPatient'));
    }
    return response.json();
};

export const updatePatient = async (id, patientData) => {
    const response = await fetch(await patientsUrl(`${id}/`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patientData),
    });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.updatePatient'));
    }
    return response.json();
};

export const dischargePatient = async (id) => {
    const response = await fetch(await patientsUrl(`${id}/`), { method: 'DELETE' });
    if (!response.ok) {
        throw await buildErrorFromResponse(response, t('api.errors.dischargePatient'));
    }
};