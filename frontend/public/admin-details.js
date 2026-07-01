// Admin Application Details Handler
window.addEventListener('DOMContentLoaded', function() {
    const referenceNumber = sessionStorage.getItem('currentApplicationReference');

    if (!referenceNumber) {
        window.location.href = 'admin-applications.html';
        return;
    }
    
    const detailsContainer = document.getElementById('detailsContainer');

    requestJson(`/admin/applications/${encodeURIComponent(referenceNumber)}`, { loadingMessage: 'Loading application details...' })
        .then(result => {
            const app = result.application;
            const formattedDate = formatDateTime(app.submittedAt);

            // Wire admin download button (full PDF using shared util)
            const adminDownloadBtn = document.getElementById('adminDownloadFormBtn');
            if (adminDownloadBtn) {
                adminDownloadBtn.addEventListener('click', async function() {
                    const original = adminDownloadBtn.textContent;
                    adminDownloadBtn.disabled = true;
                    adminDownloadBtn.textContent = 'Preparing PDF...';
                    try {
                        await downloadSubmissionPdf(app);
                    } catch (e) {
                        showAppMessage('Could not generate PDF: ' + e.message, 'error');
                    } finally {
                        adminDownloadBtn.disabled = false;
                        adminDownloadBtn.textContent = original;
                    }
                });
            }

            const appTypeLabels = {
                registration: 'New Registration',
                deregistration: 'Deregistration',
                edit_remove: 'Edit / Remove Vehicle'
            };
            const appType = app.applicationType || 'registration';
            const appTypeLabel = appTypeLabels[appType] || 'New Registration';
            const isRegistration = appType === 'registration';
            const isEditRemove = appType === 'edit_remove';

            const remarksSectionHtml = isEditRemove ? `
                <div class="details-section" data-testid="detail-remarks-section">
                    <h2>Remarks / Notes</h2>
                    <div class="detail-row" style="align-items:flex-start;">
                        <span class="detail-value" data-testid="detail-remarks" style="white-space:pre-wrap;line-height:1.55;">${escapeHtml(app.remarks || '-')}</span>
                    </div>
                </div>
            ` : '';

            const receiptSectionHtml = isRegistration ? `
                <div class="details-section" data-testid="detail-receipt-section">
                    <h2>Payment Receipt</h2>
                    ${app.receiptUrl ? `<a href="${escapeHtml(app.receiptUrl)}" target="_blank" rel="noopener noreferrer"><img src="${escapeHtml(app.receiptUrl)}" alt="Payment Receipt" class="receipt-image" data-testid="receipt-image"></a>` : '<p class="no-receipt">No receipt uploaded</p>'}
                </div>
            ` : '';

            const parkingSectionHtml = `
                <div class="details-section">
                    <h2>Parking Information</h2>
                    <div class="detail-row"><span class="detail-label">Parking Type:</span><span class="detail-value">${escapeHtml(app.parkingType || '-')}</span></div>
                    <div class="detail-row"><span class="detail-label">Subscription Period:</span><span class="detail-value">${escapeHtml(app.subscriptionPeriod || '-')}</span></div>
                    ${isRegistration ? `<div class="detail-row"><span class="detail-label">Total Amount:</span><span class="detail-value"><strong>RM ${app.totalAmount ?? '-'}</strong></span></div>` : ''}
                </div>
            `;

            detailsContainer.innerHTML = `
                <div class="details-section">
                    <h2>Reference Information</h2>
                    <div class="detail-row">
                        <span class="detail-label">Reference Number:</span>
                        <span class="detail-value" data-testid="detail-reference">${escapeHtml(app.referenceNumber || '')}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Application Type:</span>
                        <span class="detail-value" data-testid="detail-app-type">${appTypeLabel}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Submission Date:</span>
                        <span class="detail-value" data-testid="detail-date">${formattedDate}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Status:</span>
                        <span class="status-badge ${(app.status || '').toLowerCase()}" data-testid="detail-status">${escapeHtml(app.status || '')}</span>
                    </div>
                </div>

                <div class="details-section">
                    <h2>Applicant Information</h2>
                    <div class="detail-row"><span class="detail-label">Full Name:</span><span class="detail-value" data-testid="detail-name">${escapeHtml(app.fullName || '')}</span></div>
                    <div class="detail-row"><span class="detail-label">Phone Number:</span><span class="detail-value">${escapeHtml(app.phoneNumber || '')}</span></div>
                    <div class="detail-row"><span class="detail-label">Customer Email:</span><span class="detail-value" data-testid="detail-email">${escapeHtml(app.email || '-')}</span></div>
                    <div class="detail-row"><span class="detail-label">Company Name:</span><span class="detail-value">${escapeHtml(app.companyName || '')}</span></div>
                    <div class="detail-row"><span class="detail-label">Staff ID:</span><span class="detail-value">${escapeHtml(app.staffId || '-')}</span></div>
                </div>

                ${remarksSectionHtml}

                <div class="details-section">
                    <h2>Vehicle Information</h2>
                    <div class="detail-row"><span class="detail-label">Vehicle Number:</span><span class="detail-value">${escapeHtml(app.vehicleNumber || '-')}</span></div>
                    <div class="detail-row"><span class="detail-label">Vehicle Model:</span><span class="detail-value">${escapeHtml(app.vehicleModel || '-')}</span></div>
                    <div class="detail-row"><span class="detail-label">Vehicle Type:</span><span class="detail-value">${escapeHtml(app.vehicleType || '-')}</span></div>
                    <div class="detail-row"><span class="detail-label">Vehicle Color:</span><span class="detail-value">${escapeHtml(app.vehicleColor || '-')}</span></div>
                </div>

                ${parkingSectionHtml}

                ${receiptSectionHtml}
            `;

            if (app.status === 'Pending') {
                const actionButtons = document.getElementById('actionButtons');
                actionButtons.style.display = 'flex';

                document.getElementById('approveBtn').addEventListener('click', function() {
                    updateApplicationStatus(referenceNumber, 'Approved', this);
                });

                document.getElementById('rejectBtn').addEventListener('click', function() {
                    updateApplicationStatus(referenceNumber, 'Rejected', this);
                });
            }
        })
        .catch(error => {
            showAppMessage(error.message, 'error', 'Application unavailable');
            detailsContainer.innerHTML = `<div style="color:#b91c1c;padding:24px;">${escapeHtml(error.message)}</div>`;
        });
});

async function updateApplicationStatus(referenceNumber, newStatus, button) {
    setButtonLoading(button, true, `${newStatus}...`);

    try {
        await requestJson(`/admin/applications/${encodeURIComponent(referenceNumber)}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus }),
            loadingMessage: `Updating application...`
        });
        showAppMessage(`Application ${newStatus.toLowerCase()} successfully.`, 'success');
        setTimeout(() => {
            window.location.href = 'admin-applications.html';
        }, 900);
    } catch (error) {
        showAppMessage(error.message, 'error');
        setButtonLoading(button, false);
    }
}
