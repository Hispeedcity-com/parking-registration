// Payment Page Handler
let uploadedReceipt = null;

function getCurrentApplication() {
    const savedData = sessionStorage.getItem('currentApplication');
    if (!savedData) {
        window.location.href = 'registration.html';
        return null;
    }
    return JSON.parse(savedData);
}

window.addEventListener('DOMContentLoaded', function() {
    const data = getCurrentApplication();
    if (!data) {
        return;
    }
    document.getElementById('paymentAmount').textContent = `RM ${data.totalAmount}`;
    
    // Upload area click handler
    const uploadArea = document.getElementById('uploadArea');
    const receiptUpload = document.getElementById('receiptUpload');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const uploadPreview = document.getElementById('uploadPreview');
    const previewImage = document.getElementById('previewImage');
    const removeImage = document.getElementById('removeImage');
    
    uploadArea.addEventListener('click', function() {
        receiptUpload.click();
    });
    
    receiptUpload.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Validate file size (5MB max)
            if (file.size > 5 * 1024 * 1024) {
                alert('File size must be less than 5MB');
                return;
            }
            
            // Validate file type
            if (!file.type.match('image.*')) {
                alert('Please upload an image file');
                return;
            }
            
            // Read and display image
            const reader = new FileReader();
            reader.onload = function(event) {
                uploadedReceipt = event.target.result;
                previewImage.src = event.target.result;
                uploadPlaceholder.style.display = 'none';
                uploadPreview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
    
    removeImage.addEventListener('click', function(e) {
        e.stopPropagation();
        uploadedReceipt = null;
        receiptUpload.value = '';
        uploadPlaceholder.style.display = 'block';
        uploadPreview.style.display = 'none';
    });
    
    // Submit button handler
    document.getElementById('submitBtn').addEventListener('click', function() {
        if (!uploadedReceipt) {
            alert('Please upload a payment receipt before submitting');
            return;
        }

        const submitApplication = async () => {
            try {
                const formData = new FormData();
                formData.append('applicationData', JSON.stringify(data));
                formData.append('receipt', receiptUpload.files[0]);

                const result = await requestFormData('/applications', formData);
                sessionStorage.removeItem('currentApplication');
                sessionStorage.setItem('lastSubmission', JSON.stringify(result));
                window.location.href = 'success.html';
            } catch (error) {
                alert(error.message);
            }
        };

        submitApplication();
    });
});