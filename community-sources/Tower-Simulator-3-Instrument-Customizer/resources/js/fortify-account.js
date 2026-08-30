async function fetchJson(url) {
    const response = await fetch(url, {
        headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'same-origin',
    });

    if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json();
}

async function initTwoFactor(root) {
    const qrTarget = root.querySelector('[data-two-factor-qr]');
    const secretTarget = root.querySelector('[data-two-factor-secret]');
    const recoveryTarget = root.querySelector('[data-two-factor-recovery]');

    if (!qrTarget || !secretTarget) {
        return;
    }

    if (root.dataset.enabled !== 'true') {
        return;
    }

    try {
        const [{ svg }, { secretKey }] = await Promise.all([
            fetchJson(root.dataset.qrUrl),
            fetchJson(root.dataset.secretUrl),
        ]);

        qrTarget.innerHTML = svg || 'QR code unavailable.';
        secretTarget.textContent = secretKey ? `Secret key: ${secretKey}` : 'Secret key unavailable.';
    } catch (error) {
        qrTarget.textContent = 'Unable to load two-factor setup details.';
        secretTarget.textContent = '';
    }

    if (!recoveryTarget || root.dataset.confirmed !== 'true') {
        return;
    }

    try {
        const recoveryCodes = await fetchJson(root.dataset.recoveryUrl);
        recoveryTarget.textContent = Array.isArray(recoveryCodes) && recoveryCodes.length > 0
            ? recoveryCodes.join('\n')
            : 'Recovery codes unavailable.';
    } catch (error) {
        recoveryTarget.textContent = 'Unable to load recovery codes.';
    }
}

document.querySelectorAll('[data-two-factor-root]').forEach((root) => {
    initTwoFactor(root);
});
