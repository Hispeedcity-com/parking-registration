// Payment Page Handler
let uploadedReceipt = null;

window.addEventListener('DOMContentLoaded', function() {
    const savedData = localStorage.getItem('currentApplication');
    
    if (!savedData) {
        window.location.href = 'registration.html';
        return;
    }
    
    const data = JSON.parse(savedData);
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
        
        // Save receipt with application data
        data.receiptImage = uploadedReceipt;
        data.submissionDate = new Date().toISOString();
        data.status = 'Pending';
        data.read = false;
        
        // Generate reference number
        let applications = JSON.parse(localStorage.getItem('applications') || '[]');
        const referenceNumber = `SP-2026-${String(applications.length + 1).padStart(6, '0')}`;
        data.referenceNumber = referenceNumber;
        
        // Save to applications list
        applications.push(data);
        localStorage.setItem('applications', JSON.stringify(applications));
        
        // Save current reference for success page
        localStorage.setItem('lastSubmission', referenceNumber);
        
        // Clear current application
        localStorage.removeItem('currentApplication');
        
        // Navigate to success page
        window.location.href = 'success.html';
    });
});