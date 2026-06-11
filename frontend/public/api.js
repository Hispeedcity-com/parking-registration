const API_BASE_URL = window.__API_BASE_URL__ || 'http://localhost:5000/api';

function getAuthToken() {
    return sessionStorage.getItem('adminToken');
}

function authHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    const token = getAuthToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return headers;
}

async function requestJson(path, options = {}) {
    const { headers: optionHeaders, ...restOptions } = options;
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...restOptions,
        headers: authHeaders(optionHeaders || {}),
    });

    const contentType = response.headers.get('content-type') || '';
    const body = contentType.includes('application/json') ? await response.json() : await response.text();

    if (!response.ok) {
        const message = body && body.detail ? body.detail : (body && body.message ? body.message : 'Request failed');
        throw new Error(message);
    }

    return body;
}

async function requestFormData(path, formData) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
    });

    const body = await response.json();
    if (!response.ok) {
        throw new Error(body.detail || body.message || 'Request failed');
    }
    return body;
}
