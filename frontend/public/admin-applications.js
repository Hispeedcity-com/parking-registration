// Admin Applications List Handler
window.addEventListener('DOMContentLoaded', function() {
    const applicationsList = document.getElementById('applicationsList');

    requestJson('/admin/applications', { loadingMessage: 'Loading applications...' })
        .then(result => {
            const applications = result.applications || [];
            if (applications.length === 0) {
                applicationsList.innerHTML = '<div style="text-align:center;padding:40px;color:#757575;">No applications found</div>';
                return;
            }

            applications.forEach((app, index) => {
                const date = new Date(app.submittedAt);
                const formattedDate = date.toLocaleDateString('en-MY', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric'
                });
                const formattedTime = date.toLocaleTimeString('en-MY', {
                    hour: '2-digit',
                    minute: '2-digit'
                });

                const card = document.createElement('div');
                card.className = 'application-card';
                card.setAttribute('data-testid', `application-card-${index}`);
                card.onclick = function() {
                    viewApplication(app.referenceNumber);
                };

                card.innerHTML = `
                    <div class="application-header">
                        <div class="applicant-info">
                            <h3>${app.fullName}</h3>
                            <p class="vehicle-number">${app.vehicleNumber}</p>
                        </div>
                        <span class="status-badge ${app.status.toLowerCase()}" data-testid="status-${index}">${app.status}</span>
                    </div>
                    <div class="application-meta">
                        <span class="date-time">${formattedDate} at ${formattedTime}</span>
                        <span class="date-time">Ref: ${app.referenceNumber}</span>
                    </div>
                `;

                applicationsList.appendChild(card);
            });
        })
        .catch(error => {
            showAppMessage(error.message, 'error', 'Applications unavailable');
            applicationsList.innerHTML = `<div style="text-align:center;padding:40px;color:#b91c1c;">${escapeHtml(error.message)}</div>`;
        });
});

function viewApplication(referenceNumber) {
    sessionStorage.setItem('currentApplicationReference', referenceNumber);
    window.location.href = 'admin-details.html';
}
