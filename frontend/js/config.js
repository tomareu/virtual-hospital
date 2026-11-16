// --- Application configuration (environment dependent values) ---
async function loadConfig() {
    const isLocalHost = ['localhost', '127.0.0.1'].includes(window.location.hostname);

    if (isLocalHost) {
        try {
            const localResponse = await fetch('/config.local.json');
            if (localResponse.ok) return localResponse.json();
        } catch {
        }
    }

    const response = await fetch('/config.json');
    return response.json();
}

const configPromise = loadConfig();

export const getApiBaseUrl = async () => `${(await configPromise).apiBaseUrl}/api`;
export const getTurnstileSiteKey = async () => (await configPromise).turnstileSiteKey;
export const AVATAR_BASE_PATH = '/assets/avatars';
export const DEFAULT_AVATAR = '/assets/default-avatar.png';