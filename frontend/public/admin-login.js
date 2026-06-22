// Admin Login Handler
document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const submitButton = this.querySelector('button[type="submit"]');
    
    if (!username || !password) {
        showAppMessage('Please enter username and password.', 'warning');
        return;
    }

    setButtonLoading(submitButton, true, 'Logging in...');

    try {
        const result = await requestJson('/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            loadingMessage: 'Logging in...'
        });
        sessionStorage.setItem('adminToken', result.token);
        window.location.href = 'admin-dashboard.html';
    } catch (error) {
        showAppMessage(error.message, 'error');
        setButtonLoading(submitButton, false);
    }
});
