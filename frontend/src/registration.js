// Registration Form Handler
let numberOfVehicles = 0;

// Listen for number of cars selection
document.getElementById('numberOfCars').addEventListener('change', function(e) {
    numberOfVehicles = parseInt(e.target.value);
    generateVehicleSections(numberOfVehicles);
    document.getElementById('parkingSection').style.display = 'block';
});

function generateVehicleSections(count) {
    const container = document.getElementById('vehiclesContainer');
    container.innerHTML = '';
    
    for (let i = 0; i < count; i++) {
        const vehicleSection = document.createElement('div');
        vehicleSection.className = 'form-section vehicle-section';
        vehicleSection.innerHTML = `
            <h3>Vehicle ${i + 1} Information</h3>
            <div class="form-row">
                <div class="form-group">
                    <label for="vehicleNumber${i}">Vehicle Number *</label>
                    <input type="text" id="vehicleNumber${i}" name="vehicleNumber${i}" required data-testid="vehicle-number-input-${i}" placeholder="e.g., ABC 1234">
                </div>
                <div class="form-group">
                    <label for="vehicleModel${i}">Vehicle Model *</label>
                    <input type="text" id="vehicleModel${i}" name="vehicleModel${i}" required data-testid="vehicle-model-input-${i}" placeholder="e.g., Toyota Camry">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group full-width">
                    <label>Vehicle Type * (Check one)</label>
                    <div class="checkbox-group">
                        <label class="checkbox-label">
                            <input type="checkbox" name="vehicleType${i}" value="Sedan" data-testid="vehicle-type-sedan-${i}">
                            <span>Sedan</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" name="vehicleType${i}" value="Hatchback" data-testid="vehicle-type-hatchback-${i}">
                            <span>Hatchback</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" name="vehicleType${i}" value="SUV" data-testid="vehicle-type-suv-${i}">
                            <span>SUV</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" name="vehicleType${i}" value="Mini Van" data-testid="vehicle-type-minivan-${i}">
                            <span>Mini Van</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" name="vehicleType${i}" value="Others" data-testid="vehicle-type-others-${i}">
                            <span>Others</span>
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label for="vehicleColor${i}">Vehicle Color *</label>
                    <input type="text" id="vehicleColor${i}" name="vehicleColor${i}" required data-testid="vehicle-color-input-${i}">
                </div>
            </div>
        `;
        container.appendChild(vehicleSection);
        
        // Add checkbox restriction (only one can be checked per vehicle)
        const checkboxes = vehicleSection.querySelectorAll(`input[name="vehicleType${i}"]`);
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                if (this.checked) {
                    checkboxes.forEach(cb => {
                        if (cb !== this) cb.checked = false;
                    });
                }
            });
        });
    }
}

document.getElementById('registrationForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Get personal information
    const formData = {
        fullName: document.getElementById('fullName').value,
        phoneNumber: document.getElementById('phoneNumber').value,
        companyName: document.getElementById('companyName').value,
        staffId: document.getElementById('staffId').value,
        numberOfCars: numberOfVehicles,
        vehicles: [],
        parkingType: document.querySelector('input[name="parkingType"]:checked')?.value,
        subscriptionPeriod: document.querySelector('input[name="subscriptionPeriod"]:checked')?.value
    };
    
    // Validate parking selection
    if (!formData.parkingType) {
        alert('Please select a parking type');
        return;
    }
    if (!formData.subscriptionPeriod) {
        alert('Please select a subscription period');
        return;
    }
    
    // Collect vehicle information
    for (let i = 0; i < numberOfVehicles; i++) {
        const vehicleType = document.querySelector(`input[name="vehicleType${i}"]:checked`)?.value;
        
        if (!vehicleType) {
            alert(`Please select vehicle type for Vehicle ${i + 1}`);
            return;
        }
        
        formData.vehicles.push({
            vehicleNumber: document.getElementById(`vehicleNumber${i}`).value,
            vehicleModel: document.getElementById(`vehicleModel${i}`).value,
            vehicleType: vehicleType,
            vehicleColor: document.getElementById(`vehicleColor${i}`).value
        });
    }
    
    // Calculate total amount
    const parkingPrice = parseInt(document.querySelector('input[name="parkingType"]:checked').dataset.price);
    const multiplier = parseInt(document.querySelector('input[name="subscriptionPeriod"]:checked').dataset.multiplier);
    formData.totalAmount = parkingPrice * multiplier * numberOfVehicles;
    
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
        
        // Populate personal fields
        document.getElementById('fullName').value = data.fullName || '';
        document.getElementById('phoneNumber').value = data.phoneNumber || '';
        document.getElementById('companyName').value = data.companyName || '';
        document.getElementById('staffId').value = data.staffId || '';
        
        // Set number of cars
        if (data.numberOfCars) {
            document.getElementById('numberOfCars').value = data.numberOfCars;
            numberOfVehicles = data.numberOfCars;
            generateVehicleSections(numberOfVehicles);
            document.getElementById('parkingSection').style.display = 'block';
            
            // Populate vehicle data
            setTimeout(() => {
                data.vehicles.forEach((vehicle, i) => {
                    document.getElementById(`vehicleNumber${i}`).value = vehicle.vehicleNumber || '';
                    document.getElementById(`vehicleModel${i}`).value = vehicle.vehicleModel || '';
                    document.getElementById(`vehicleColor${i}`).value = vehicle.vehicleColor || '';
                    
                    if (vehicle.vehicleType) {
                        const checkbox = document.querySelector(`input[name="vehicleType${i}"][value="${vehicle.vehicleType}"]`);
                        if (checkbox) checkbox.checked = true;
                    }
                });
            }, 100);
        }
        
        // Set parking selections
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
