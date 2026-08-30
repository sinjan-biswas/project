// Face detection helper (optional)
// This can be enhanced with face detection libraries

class FaceDetectorHelper {
    constructor() {
        this.detector = null;
    }

    async init() {
        // Check if face detection is available
        if ('FaceDetector' in window) {
            this.detector = new FaceDetector({
                maxDetectedFaces: 1,
                fastMode: true
            });
            return true;
        }
        return false;
    }

    async detect(videoElement) {
        if (!this.detector) return null;
        try {
            const faces = await this.detector.detect(videoElement);
            return faces;
        } catch (e) {
            console.warn('Face detection not supported:', e);
            return null;
        }
    }

    drawFaceBox(canvas, faces, video) {
        if (!faces || faces.length === 0) return;
        const ctx = canvas.getContext('2d');
        const face = faces[0];
        const box = face.boundingBox;
        
        ctx.strokeStyle = '#48bb78';
        ctx.lineWidth = 3;
        ctx.strokeRect(box.x, box.y, box.width, box.height);
        
        ctx.fillStyle = 'rgba(72, 187, 120, 0.1)';
        ctx.fillRect(box.x, box.y, box.width, box.height);
    }
}

// Initialize face detector
const faceDetector = new FaceDetectorHelper();

// Monitor camera for face detection
async function monitorFace() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('faceDebugCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    
    const detectLoop = async () => {
        if (!state.isCameraActive) return;
        
        const faces = await faceDetector.detect(video);
        if (faces && faces.length > 0) {
            // Face detected
            document.querySelector('.camera-overlay p').textContent = '✅ Face detected';
            document.querySelector('.camera-overlay p').style.color = '#48bb78';
            elements.captureBtn.disabled = false;
        } else {
            document.querySelector('.camera-overlay p').textContent = 'Position face in frame';
            document.querySelector('.camera-overlay p').style.color = 'white';
        }
        
        requestAnimationFrame(detectLoop);
    };
    
    detectLoop();
}

// Extend startCamera to include face detection
const originalStartCamera = startCamera;
startCamera = async function() {
    await originalStartCamera();
    if (await faceDetector.init()) {
        monitorFace();
    }
};
