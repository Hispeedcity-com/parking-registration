// Registration Form Handler
document.getElementById('registrationForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Get form data
    const formData = {
        fullName: document.getElementById('fullName').value,
        phoneNumber: document.getElementById('phoneNumber').value,
        companyName: document.getElementById('companyName').value,
        staffId: document.getElementById('staffId').value,
        vehicleNumber: document.getElementById('vehicleNumber').value,
        vehicleModel: document.getElementById('vehicleModel').value,
        vehicleType: document.querySelector('input[name="vehicleType"]:checked')?.value,
        vehicleColor: document.getElementById('vehicleColor').value,
        parkingType: document.querySelector('input[name="parkingType"]:checked')?.value,
        subscriptionPeriod: document.querySelector('input[name="subscriptionPeriod"]:checked')?.value
    };
    
    // Validate
    if (!formData.vehicleType) {
        alert('Please select a vehicle type');
        return;
    }
    if (!formData.parkingType) {
        alert('Please select a parking type');
        return;
    }
    if (!formData.subscriptionPeriod) {
        alert('Please select a subscription period');
        return;
    }
    
    // Calculate total amount
    const parkingPrice = parseInt(document.querySelector('input[name="parkingType"]:checked').dataset.price);
    const multiplier = parseInt(document.querySelector('input[name="subscriptionPeriod"]:checked').dataset.multiplier);
    formData.totalAmount = parkingPrice * multiplier;
    
    // Store in localStorage
    localStorage.setItem('currentApplication', JSON.stringify(formData));
    
    // Navigate to review page
    window.location.href = 'review.html';
});

// Load existing data if returning from review page
window.addEventListener('DOMContentLoaded', function() {
    const savedData = localStorage.getItem('currentApplication');
    if (savedData) {
        const data = JSON.parse(savedData);
        
        // Populate form fields
        document.getElementById('fullName').value = data.fullName || '';
        document.getElementById('phoneNumber').value = data.phoneNumber || '';
        document.getElementById('companyName').value = data.companyName || '';
        document.getElementById('staffId').value = data.staffId || '';
        document.getElementById('vehicleNumber').value = data.vehicleNumber || '';
        document.getElementById('vehicleModel').value = data.vehicleModel || '';
        document.getElementById('vehicleColor').value = data.vehicleColor || '';
        
        // Set radio buttons
        if (data.vehicleType) {
            const vehicleTypeRadio = document.querySelector(`input[name="vehicleType"][value="${data.vehicleType}"]`);
            if (vehicleTypeRadio) vehicleTypeRadio.checked = true;
        }
        
        if (data.parkingType) {
            const parkingTypeRadio = document.querySelector(`input[name="parkingType"][value="${data.parkingType}"]`);
            if (parkingTypeRadio) parkingTypeRadio.checked = true;
        }
        
        if (data.subscriptionPeriod) {
            const subscriptionRadio = document.querySelector(`input[name="subscriptionPeriod"][value="${data.subscriptionPeriod}"]`);
            if (subscriptionRadio) subscriptionRadio.checked = true;
        }
    }
});