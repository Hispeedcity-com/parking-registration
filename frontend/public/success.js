// Success Page Handler
window.addEventListener('DOMContentLoaded', function() {
    const referenceNumber = localStorage.getItem('lastSubmission');
    
    if (!referenceNumber) {
        window.location.href = 'index.html';
        return;
    }
    
    // Get application data
    const applications = JSON.parse(localStorage.getItem('applications') || '[]');
    const application = applications.find(app => app.referenceNumber === referenceNumber);
    
    if (application) {
        document.getElementById('referenceNumber').textContent = application.referenceNumber;
        
        // Format submission date
        const date = new Date(application.submissionDate);
        const formattedDate = date.toLocaleDateString('en-MY', {
            day: '2-digit',
            month: 'long',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('submissionDate').textContent = formattedDate;
    }
});

function returnHome() {
    localStorage.removeItem('lastSubmission');
    window.location.href = 'index.html';
}