// API Configuration
const API_URL = 'http://localhost:8000';
const API_ENDPOINT = `${API_URL}/api/v2/screen`;

// State
let state = {
    documentFile: null,
    faceImage: null,
    faceImageData: null,
    isCameraActive: false,
    isScreening: false,
    results: null
};

// DOM Elements
const elements = {
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    uploadBtn: document.getElementById('uploadBtn'),
    filePreview: document.getElementById('filePreview'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFileBtn: document.getElementById('removeFileBtn'),
    video: document.getElementById('video'),
    canvas: document.getElementById('canvas'),
    cameraOverlay: document.getElementById('cameraOverlay'),
    startCameraBtn: document.getElementById('startCameraBtn'),
    captureBtn: document.getElementById('captureBtn'),
    stopCameraBtn: document.getElementById('stopCameraBtn'),
    capturedFace: document.getElementById('capturedFace'),
    facePreview: document.getElementById('facePreview'),
    screenBtn: document.getElementById('screenBtn'),
    actionStatus: document.getElementById('actionStatus'),
    resultsContainer: document.getElementById('resultsContainer'),
    fileInput: document.getElementById('fileInput')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkAPIHealth();
});

// Setup Event Listeners
function setupEventListeners() {
    // Upload
    elements.uploadBtn.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.uploadZone.addEventListener('dragover', handleDragOver);
    elements.uploadZone.addEventListener('dragleave', handleDragLeave);
    elements.uploadZone.addEventListener('drop', handleDrop);
    elements.removeFileBtn.addEventListener('click', removeFile);

    // Camera
    elements.startCameraBtn.addEventListener('click', startCamera);
    elements.captureBtn.addEventListener('click', capturePhoto);
    elements.stopCameraBtn.addEventListener('click', stopCamera);

    // Action
    elements.screenBtn.addEventListener('click', startScreening);
}

// File Handling
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        loadFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    elements.uploadZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.uploadZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    elements.uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) {
        loadFile(file);
    }
}

function loadFile(file) {
    state.documentFile = file;
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.filePreview.classList.remove('hidden');
    elements.uploadZone.classList.add('hidden');
    updateScreenButton();
}

function removeFile() {
    state.documentFile = null;
    elements.fileInput.value = '';
    elements.filePreview.classList.add('hidden');
    elements.uploadZone.classList.remove('hidden');
    updateScreenButton();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// Camera Functions
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: 640, height: 480 }
        });
        elements.video.srcObject = stream;
        await elements.video.play();
        elements.cameraOverlay.classList.add('active');
        elements.captureBtn.disabled = false;
        elements.stopCameraBtn.disabled = false;
        elements.startCameraBtn.disabled = true;
        state.isCameraActive = true;
        setStatus('Camera started', 'success');
    } catch (err) {
        console.error('Camera error:', err);
        setStatus('Camera access denied', 'error');
        alert('Please allow camera access to use face verification.');
    }
}

function capturePhoto() {
    const canvas = elements.canvas;
    const video = elements.video;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert to data URL
    const dataURL = canvas.toDataURL('image/jpeg', 0.9);
    state.faceImageData = dataURL;
    
    // Display preview
    elements.capturedFace.src = dataURL;
    elements.facePreview.classList.remove('hidden');
    
    // Convert to blob for upload
    canvas.toBlob((blob) => {
        state.faceImage = blob;
        updateScreenButton();
    }, 'image/jpeg', 0.9);
    
    setStatus('Face captured ✓', 'success');
}

function stopCamera() {
    const stream = elements.video.srcObject;
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    elements.video.srcObject = null;
    elements.cameraOverlay.classList.remove('active');
    elements.captureBtn.disabled = true;
    elements.stopCameraBtn.disabled = true;
    elements.startCameraBtn.disabled = false;
    state.isCameraActive = false;
    setStatus('Camera stopped', 'info');
}

// API Functions
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_URL}/health`);
        if (response.ok) {
            setStatus('API connected', 'success');
        } else {
            setStatus('API error', 'error');
        }
    } catch {
        setStatus('API offline', 'error');
    }
}

async function startScreening() {
    if (!state.documentFile || !state.faceImage) {
        alert('Please upload a document and capture a face photo.');
        return;
    }

    state.isScreening = true;
    elements.screenBtn.disabled = true;
    elements.screenBtn.innerHTML = '<span class="spinner"></span> Screening...';
    setStatus('Screening in progress...', 'loading');

    try {
        const formData = new FormData();
        formData.append('document', state.documentFile);
        formData.append('live_photo', state.faceImage, 'face.jpg');

        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            state.results = data;
            displayResults(data);
            setStatus('Screening complete ✓', 'success');
        } else {
            const error = await response.text();
            setStatus('Screening failed', 'error');
            showError('Screening failed: ' + error);
        }
    } catch (err) {
        console.error('Screening error:', err);
        setStatus('Network error', 'error');
        showError('Failed to connect to server');
    } finally {
        state.isScreening = false;
        elements.screenBtn.disabled = false;
        elements.screenBtn.innerHTML = '<i class="fas fa-play"></i> Start Screening';
        updateScreenButton();
    }
}

function displayResults(data) {
    const container = elements.resultsContainer;
    const risk = data.risk_assessment;
    const decision = risk.decision;
    let decisionClass = 'decision-approve';
    let riskClass = 'risk-low';
    
    if (decision === 'DENY') {
        decisionClass = 'decision-deny';
        riskClass = 'risk-high';
    } else if (decision === 'SECONDARY_INSPECTION') {
        decisionClass = 'decision-inspect';
        riskClass = 'risk-medium';
    }

    container.innerHTML = `
        <div class="results-content">
            <div class="risk-score risk-${riskClass}">
                ${risk.total_score}/100
            </div>
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <span class="decision-badge ${decisionClass}">${decision}</span>
                <p style="color: #718096; font-size: 0.875rem; margin-top: 0.5rem;">
                    Confidence: ${risk.confidence}
                </p>
            </div>
            
            <h4 style="margin-bottom: 0.75rem; color: #2d3748;">Passport Details</h4>
            <div class="result-item">
                <span class="result-label">Name</span>
                <span class="result-value">${data.ocr_data.surname}, ${data.ocr_data.given_names}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Passport Number</span>
                <span class="result-value">${data.ocr_data.document_number}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Country</span>
                <span class="result-value">${data.ocr_data.country_code}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Date of Birth</span>
                <span class="result-value">${data.ocr_data.date_of_birth}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Expiry Date</span>
                <span class="result-value">${data.ocr_data.date_of_expiry}</span>
            </div>
            
            <h4 style="margin: 1rem 0 0.75rem; color: #2d3748;">Security Checks</h4>
            <div class="result-item">
                <span class="result-label">Tampering Score</span>
                <span class="result-value ${data.tampering.tampering_score > 30 ? 'risk-high' : 'risk-low'}">
                    ${data.tampering.tampering_score}%
                </span>
            </div>
            <div class="result-item">
                <span class="result-label">Tampering Detected</span>
                <span class="result-value">${data.tampering.is_tampered ? '⚠️ Yes' : '✅ No'}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Face Verified</span>
                <span class="result-value">${data.biometrics.verified ? '✅ Yes' : '❌ No'}</span>
            </div>
            <div class="result-item">
                <span class="result-label">Document Valid</span>
                <span class="result-value">${data.validation.valid ? '✅ Yes' : '⚠️ No'}</span>
            </div>
            ${data.validation.errors.length > 0 ? `
                <div style="margin-top: 0.75rem; padding: 0.75rem; background: #fed7d7; border-radius: 8px;">
                    <p style="color: #9b2c2c; font-size: 0.875rem; font-weight: 500;">
                        ⚠️ Issues: ${data.validation.errors.join(', ')}
                    </p>
                </div>
            ` : ''}
            
            <div style="margin-top: 1rem; padding: 0.75rem; background: #edf2f7; border-radius: 8px;">
                <p style="font-size: 0.75rem; color: #718096;">
                    Screening ID: ${data.screening_id}
                </p>
                <p style="font-size: 0.75rem; color: #718096;">
                    Timestamp: ${new Date(data.timestamp).toLocaleString()}
                </p>
            </div>
        </div>
    `;
}

// UI Helpers
function updateScreenButton() {
    const hasDocument = state.documentFile !== null;
    const hasFace = state.faceImage !== null;
    elements.screenBtn.disabled = !hasDocument || !hasFace || state.isScreening;
}

function setStatus(message, type = 'info') {
    const statusEl = document.querySelector('.action-status .status-text');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.style.color = type === 'success' ? '#48bb78' : 
                                type === 'error' ? '#fc8181' : 
                                type === 'loading' ? '#4299e1' : '#718096';
    }
}

function showError(message) {
    const container = elements.resultsContainer;
    container.innerHTML = `
        <div class="empty-state" style="color: #fc8181;">
            <i class="fas fa-exclamation-circle" style="font-size: 3rem;"></i>
            <p>${message}</p>
            <p style="font-size: 0.875rem;">Please try again</p>
        </div>
    `;
}

// Export for debugging
window.app = {
    state,
    elements,
    startCamera,
    stopCamera,
    startScreening
};
