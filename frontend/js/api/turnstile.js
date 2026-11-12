// --- API layer: human check (Cloudflare Turnstile) ---
import { getTurnstileSiteKey } from '../config.js';
import { t } from '../i18n.js';
import { ApiError } from './errors.js';

const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let scriptPromise = null;

const turnstileFailure = () => new ApiError(t('api.errors.turnstileFailed'), 'turnstile_failed');

const loadTurnstile = () => {
    scriptPromise ??= new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = SCRIPT_URL;
        script.addEventListener('load', () => resolve(window.turnstile));
        script.addEventListener('error', () => {
            scriptPromise = null;
            script.remove();
            reject(turnstileFailure());
        });
        document.head.append(script);
    });
    return scriptPromise;
};

const solveChallenge = (turnstile, sitekey) => new Promise((resolve, reject) => {
    const container = document.createElement('div');
    document.body.append(container);

    let widgetId = null;
    const finish = (settle) => (value) => {
        setTimeout(() => {
            turnstile.remove(widgetId);
            container.remove();
        });
        settle(value);
    };
    const fail = finish(() => reject(turnstileFailure()));

    widgetId = turnstile.render(container, {
        sitekey,
        callback: finish(resolve),
        'error-callback': fail,
        'timeout-callback': fail,
    });
});

export const getTurnstileToken = async () => {
    const [turnstile, sitekey] = await Promise.all([loadTurnstile(), getTurnstileSiteKey()]);
    return solveChallenge(turnstile, sitekey);
};
