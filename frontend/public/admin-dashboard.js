// Admin Dashboard Handler
window.addEventListener('DOMContentLoaded', function() {
    requestJson('/admin/dashboard/stats')
        .then(stats => {
            document.getElementById('totalApplications').textContent = stats.totalApplications;
            document.getElementById('pendingCount').textContent = stats.pendingApplications;
            document.getElementById('approvedCount').textContent = stats.approvedApplications;
            document.getElementById('rejectedCount').textContent = stats.rejectedApplications;
        })
        .catch(error => {
            alert(error.message);
            window.location.href = 'admin-login.html';
        });
});