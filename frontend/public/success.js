// Success Page Handler
window.addEventListener('DOMContentLoaded', function() {
    const savedSubmission = sessionStorage.getItem('lastSubmission');

    if (!savedSubmission) {
        window.location.href = 'index.html';
        return;
    }

    const submission = JSON.parse(savedSubmission);
    document.getElementById('referenceNumber').textContent = submission.referenceNumber || '-';

    const submittedAt = submission.submittedAt || new Date().toISOString();
    document.getElementById('submissionDate').textContent = formatDateOnly(submittedAt);
    document.getElementById('submissionTime').textContent = formatTimeOnly(submittedAt);

    const downloadBtn = document.getElementById('downloadFormBtn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', async function() {
            const original = downloadBtn.textContent;
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Preparing PDF...';
            try {
                await downloadSubmissionPdf(submission);
            } catch (e) {
                if (typeof showAppMessage === 'function') {
                    showAppMessage('Could not generate PDF: ' + e.message, 'error');
                } else {
                    alert('Could not generate PDF: ' + e.message);
                }
            } finally {
                downloadBtn.disabled = false;
                downloadBtn.textContent = original;
            }
        });
    }
});

function returnHome() {
    sessionStorage.removeItem('lastSubmission');
    window.location.href = 'index.html';
}
