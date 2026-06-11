// Success Page Handler
window.addEventListener('DOMContentLoaded', function() {
    const savedSubmission = sessionStorage.getItem('lastSubmission');
    
    if (!savedSubmission) {
        window.location.href = 'index.html';
        return;
    }

    const submission = JSON.parse(savedSubmission);
    document.getElementById('referenceNumber').textContent = submission.referenceNumber;

    const date = new Date(submission.submittedAt || Date.now());
    const formattedDate = date.toLocaleDateString('en-MY', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    document.getElementById('submissionDate').textContent = formattedDate;
});

function returnHome() {
    sessionStorage.removeItem('lastSubmission');
    window.location.href = 'index.html';
}