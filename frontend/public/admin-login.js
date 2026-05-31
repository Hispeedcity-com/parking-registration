// Admin Login Handler
document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // For prototype: Accept any credentials
    if (username && password) {
        // Set admin session
        localStorage.setItem('adminLoggedIn', 'true');
        window.location.href = 'admin-dashboard.html';
    } else {
        alert('Please enter username and password');
    }
});