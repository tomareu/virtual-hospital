  // --- DOM helpers ---
  import { getLocale } from '../i18n.js';

/**
 * Escapes a value before its interpolated into an innerHTML template string.
 */
export const escapeHtml = (value) => {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
};

/**
 * Automatic fallback if the asset doesnt exist
 * (e.g. no matching avatar file)
 */
export const setAvatarWithFallback = (imgElement, src, fallbackSrc) => {
    imgElement.onerror = () => {
        imgElement.onerror = null;
        imgElement.src = fallbackSrc;
    };
    imgElement.src = src;
};

/**
 * Formats an ISO date string (YYYY-MM-DD) into a readable display date,
 * AHTE YOU IOS
 */
export const formatDisplayDate = (isoDate) => {
    if (!isoDate) return '';
    const [year, month, day] = isoDate.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString(getLocale(), { month: 'short', day: 'numeric', year: 'numeric' });
};

export const toLocalIsoDate = (date = new Date()) =>
    [date.getFullYear(), date.getMonth() + 1, date.getDate()]
        .map((part) => String(part).padStart(2, '0'))
        .join('-');

// --- File downloads ---

const OBJECT_URL_LIFETIME_MS = 60000;

export const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement('a'), { href: url, download: filename });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), OBJECT_URL_LIFETIME_MS);
};

// --- Delegated activation for role="button" elements ---

export const onActivate = (container, selector, handler) => {
    const resolve = (event) => event.target.closest(selector);

    container.addEventListener('click', (event) => {
        const target = resolve(event);
        if (target) handler(target);
    });

    container.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const target = resolve(event);
        if (!target) return;
        event.preventDefault();
        handler(target);
    });
};