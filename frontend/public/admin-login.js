// Admin Login Handler
document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        alert('Please enter username and password');
        return;
    }

    requestJson('/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    }).then(result => {
        sessionStorage.setItem('adminToken', result.token);
        window.location.href = 'admin-dashboard.html';
    }).catch(error => {
        alert(error.message);
    });
});