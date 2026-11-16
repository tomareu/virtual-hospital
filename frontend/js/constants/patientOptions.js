// --- Option lists for <select> ---
import { tOption } from '../i18n.js';

const defineOptions = (group, values) => values.map((value) => ({
    value,
    get label() {
        return tOption(group, value);
    },
}));

export const LOCATIONS = defineOptions('locations', ['EA', 'PL', 'ET', 'NW', 'XX']);

export const SPECIES = defineOptions('species', ['human', 'cat', 'bunny', 'rat', 'monkey', 'unknown']);

export const SEXES = defineOptions('sexes', ['unknown', 'male', 'female']);

export const ID_NUMBER_PATTERN = '[a-zA-Z0-9]{1,5}';
export const ID_NUMBER_MAXLENGTH = 5;
export const NAME_MAXLENGTH = 20;
export const DIAGNOSIS_MAXLENGTH = 200;
export const DESCRIPTION_MAXLENGTH = 1000;
export const PROCEDURES_MAXLENGTH = 500;
export const INDICATIONS_MAXLENGTH = 500;

export const renderOptions = (options) => {
    const shownLabels = new Set();

    return options.map(({ value, label }) => {
        const isRepeated = shownLabels.has(label);
        shownLabels.add(label);
        return `<option value="${value}"${isRepeated ? ' hidden disabled' : ''}>${label}</option>`;
    }).join('');
};

export const PRONOUNS = defineOptions('pronouns', ['she/her', 'he/him', 'they/them']);

export const CONSULTATION_TYPES = defineOptions('consultationTypes', ['scheduled', 'preventive', 'urgent']);

// im not creating staff accounts yet, so professionals will only be these now
export const PROFESSIONALS = defineOptions('professionals', ['dr_milo', 'rn_tam']);

// ----- Icon sets -----
export const SPECIES_ICONS = {
    human: '/assets/icons/species/human.svg',
    cat: '/assets/icons/species/cat.svg',
    bunny: '/assets/icons/species/bunny.svg',
    rat: '/assets/icons/species/rat.svg',
    monkey: '/assets/icons/species/monkey.svg',
    unknown: '/assets/icons/species/unknown.svg',
};

export const SEX_ICONS = {
    male: '/assets/icons/sex/male.svg',
    female: '/assets/icons/sex/female.svg',
    unknown: '/assets/icons/sex/unknown.svg',
};

export const CALENDAR_ICON = '/assets/icons/misc/calendar.svg';
export const PENCIL_ICON = '/assets/icons/misc/pencil.svg';

export const renderIconButtons = (options, iconsMap, groupName) =>
    options.map(({ value, label }) => `
        <button type="button" class="mlvh-icon-btn" data-group="${groupName}" data-value="${value}" title="${label}">
            <img src="${iconsMap[value]}" alt="${label}">
        </button>
    `).join('');