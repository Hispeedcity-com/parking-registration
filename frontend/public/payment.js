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
                showAppMessage('File size must be less than 5MB.', 'warning');
                receiptUpload.value = '';
                return;
            }

            // Validate file type (JPG, JPEG, PNG, PDF only)
            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
            const fileName = (file.name || '').toLowerCase();
            const extOk = /\.(jpg|jpeg|png|pdf)$/i.test(fileName);
            if (!allowedTypes.includes(file.type) && !extOk) {
                showAppMessage('Unsupported file format. Please upload JPG, JPEG, PNG or PDF only.', 'warning');
                receiptUpload.value = '';
                return;
            }

            // Read and display image (PDFs show a generic preview)
            const reader = new FileReader();
            reader.onload = function(event) {
                uploadedReceipt = event.target.result;
                if (file.type === 'application/pdf') {
                    previewImage.src = '';
                    previewImage.alt = `PDF receipt: ${file.name}`;
                    previewImage.style.display = 'none';
                    let pdfLabel = document.getElementById('pdfReceiptLabel');
                    if (!pdfLabel) {
                        pdfLabel = document.createElement('div');
                        pdfLabel.id = 'pdfReceiptLabel';
                        pdfLabel.style.cssText = 'padding:20px;background:#f0fdf4;border-radius:8px;color:#166534;font-weight:600;text-align:center;';
                        uploadPreview.insertBefore(pdfLabel, uploadPreview.firstChild);
                    }
                    pdfLabel.textContent = `📄 ${file.name}`;
                    pdfLabel.style.display = 'block';
                } else {
                    const pdfLabel = document.getElementById('pdfReceiptLabel');
                    if (pdfLabel) pdfLabel.style.display = 'none';
                    previewImage.src = event.target.result;
                    previewImage.style.display = '';
                }
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
            showAppMessage('Please upload a payment receipt before submitting.', 'warning');
            return;
        }

        const submitApplication = async () => {
            setButtonLoading(this, true, 'Submitting...');
            try {
                const formData = new FormData();
                formData.append('applicationData', JSON.stringify(data));
                formData.append('receipt', receiptUpload.files[0]);

                const result = await requestFormData('/applications', formData, {
                    loadingMessage: 'Submitting your application...'
                });
                // Merge full submitted application data with server response for downstream pages
                const fullSubmission = Object.assign({}, data, result);
                sessionStorage.removeItem('currentApplication');
                sessionStorage.setItem('lastSubmission', JSON.stringify(fullSubmission));
                window.location.href = 'success.html';
            } catch (error) {
                showAppMessage(error.message, 'error', 'Submission failed');
                setButtonLoading(this, false);
            }
        };

        submitApplication();
    });
});
