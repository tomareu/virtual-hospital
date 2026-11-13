// --- API layer: errors ---
import { t } from '../i18n.js';

const FIELD_LABEL_KEYS = {
    name: 'patients.fields.name',
    age: 'patients.fields.age',
    species: 'patients.fields.species',
    sex: 'patients.fields.sex',
    pronouns: 'patients.fields.pronouns',
    location: 'patients.fields.location',
    id_number: 'patients.fields.idNumber',
    consultation_type: 'patients.fields.consultationType',
    assigned_professional: 'patients.fields.professional',
    description: 'patients.fields.description',
    record_date: 'records.fields.date',
    diagnosis: 'records.fields.diagnosis',
    procedures: 'records.fields.procedures',
    indications: 'records.fields.indications',
};

const ERROR_MESSAGE_KEYS = {
    unique: 'api.errors.duplicateId',
    not_found: 'api.errors.notFound',
    board_full: 'api.errors.boardFull',
    turnstile_failed: 'api.errors.turnstileFailed',
    record_already_complete: 'api.errors.recordAlreadyComplete',
    record_incomplete: 'api.errors.recordIncomplete',
};

const FIELD_ERROR_MESSAGE_KEYS = {
    required: 'api.errors.fieldRequired',
    blank: 'api.errors.fieldRequired',
    null: 'api.errors.fieldRequired',
    max_length: 'api.errors.fieldTooLong',
};

export class ApiError extends Error {
    constructor(message, code = null) {
        super(message);
        this.name = 'ApiError';
        this.code = code;
    }
}

const findFirstError = (payload) => {
    if (payload.detail) return { field: 'detail', error: payload.detail };

    const field = Object.keys(payload).find((key) => Array.isArray(payload[key]) && payload[key].length > 0);
    return field ? { field, error: payload[field][0] } : null;
};

const describeError = ({ field, error }, fallbackMessage) => {
    const messageKey = ERROR_MESSAGE_KEYS[error.code];
    if (messageKey) return t(messageKey);

    const labelKey = FIELD_LABEL_KEYS[field];
    if (!labelKey) return fallbackMessage;

    return t(FIELD_ERROR_MESSAGE_KEYS[error.code] ?? 'api.errors.fieldInvalid', { field: t(labelKey) });
};

export const buildErrorFromResponse = async (response, fallbackMessage) => {
    const payload = (await response.json().catch(() => null)) ?? {};
    const firstError = findFirstError(payload);
    if (!firstError) return new ApiError(fallbackMessage);
    return new ApiError(describeError(firstError, fallbackMessage), firstError.error.code);
};