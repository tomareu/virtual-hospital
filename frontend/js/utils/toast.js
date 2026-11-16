  // ------- Notifications ------
  import { t } from '../i18n.js';

const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    customClass: {
        popup: 'mlvh-swal-popup',
    },
    didOpen: (toastEl) => {
        toastEl.addEventListener('mouseenter', Swal.stopTimer);
        toastEl.addEventListener('mouseleave', Swal.resumeTimer);
    },
});

/**
 * Confirmation/error message in the corner of the screen
 * @param {string} message
 * @param {'success' | 'error' | 'info'} variant
 */
export const showToast = (message, variant = 'success') => {
    Toast.fire({
        icon: variant,
        title: message,
    });
};

/**
 * Confirmation dialog for a destructive/important action
 * @param {string} message
 * @param {string} confirmButtonText
 * @returns {Promise<boolean>}
 */
export const confirmAction = async (message, confirmButtonText) => {
    const result = await Swal.fire({
        icon: 'warning',
        iconColor: 'var(--mlvh-blue-deep)',
        text: message,
        showCancelButton: true,
        confirmButtonText,
        cancelButtonText: t('common.cancel'),
        reverseButtons: true,
        target: document.querySelector('.modal.show') ?? 'body',
        buttonsStyling: false,
        customClass: {
            popup: 'mlvh-swal-popup',
            actions: 'mlvh-swal-actions',
            confirmButton: 'btn btn-mlvh-danger',
            cancelButton: 'btn btn-primary',
        },
    });
    return result.isConfirmed;
};