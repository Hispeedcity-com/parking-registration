// Review Page Handler
window.addEventListener('DOMContentLoaded', function() {
    const savedData = localStorage.getItem('currentApplication');
    
    if (!savedData) {
        // No data found, redirect to registration
        window.location.href = 'registration.html';
        return;
    }
    
    const data = JSON.parse(savedData);
    
    // Populate review fields
    document.getElementById('review-fullName').textContent = data.fullName;
    document.getElementById('review-phoneNumber').textContent = data.phoneNumber;
    document.getElementById('review-companyName').textContent = data.companyName;
    document.getElementById('review-staffId').textContent = data.staffId;
    document.getElementById('review-vehicleNumber').textContent = data.vehicleNumber;
    document.getElementById('review-vehicleModel').textContent = data.vehicleModel;
    document.getElementById('review-vehicleType').textContent = data.vehicleType;
    document.getElementById('review-vehicleColor').textContent = data.vehicleColor;
    
    // Format parking type with price
    const parkingTypeText = data.parkingType;
    let price = 0;
    if (parkingTypeText.includes('Non Reserved')) price = 150;
    else if (parkingTypeText.includes('Reserved')) price = 200;
    else if (parkingTypeText.includes('Premium')) price = 300;
    
    document.getElementById('review-parkingType').textContent = `${data.parkingType} (RM${price})`;
    document.getElementById('review-subscriptionPeriod').textContent = data.subscriptionPeriod;
    document.getElementById('review-totalAmount').textContent = `RM ${data.totalAmount}`;
});