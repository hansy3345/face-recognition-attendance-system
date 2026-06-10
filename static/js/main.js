/* ==========================================================================
   FRONTEND LOGIC & INTERACTIVITY - SMART FRAS
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function() {
    // -------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------
    const toast = document.getElementById('toast-message');

    function showToast(message, type = 'success') {
        if (!toast) return;
        
        // Reset classes
        toast.className = 'toast';
        toast.classList.add(type === 'success' ? 'toast-success' : 'toast-error');
        toast.textContent = message;
        
        // Show
        toast.classList.remove('hidden');
        
        // Auto hide after 4 seconds
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 4000);
    }

    // -------------------------------------------------------------
    // Student Registration Form AJAX Handling
    // -------------------------------------------------------------
    const registerForm = document.getElementById('student-registration-form');
    
    if (registerForm) {
        const btnSubmit = document.getElementById('btn-submit');
        const step1 = document.getElementById('step-1-indicator');
        const step2 = document.getElementById('step-2-indicator');
        const captureInstructions = document.getElementById('capture-instructions');
        const instructId = document.getElementById('instruct-id');
        
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Show loading state
            const btnSpan = btnSubmit.querySelector('span');
            const originalText = btnSpan.textContent;
            btnSpan.textContent = 'Registering...';
            btnSubmit.disabled = true;
            
            const formData = new FormData(registerForm);
            
            fetch('/register', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                btnSpan.textContent = originalText;
                btnSubmit.disabled = false;
                
                if (data.success) {
                    showToast(data.message, 'success');
                    
                    // Update layout checklist progression
                    if (step1 && step2) {
                        step1.classList.remove('active');
                        step2.classList.add('active');
                    }
                    
                    // Show capture instructions
                    if (captureInstructions && instructId) {
                        const studentIdVal = document.getElementById('student_id').value;
                        instructId.textContent = studentIdVal;
                        captureInstructions.classList.remove('collapsed');
                    }
                    
                    // Disable form fields to prevent editing while image capture is pending
                    Array.from(registerForm.elements).forEach(elem => {
                        if (elem.id !== 'btn-reset-form') {
                            elem.disabled = true;
                        }
                    });
                    btnSubmit.classList.add('hidden');
                } else {
                    showToast(data.message || 'Registration failed.', 'error');
                }
            })
            .catch(error => {
                btnSpan.textContent = originalText;
                btnSubmit.disabled = false;
                showToast('A network error occurred. Please try again.', 'error');
                console.error('Error:', error);
            });
        });

        // -------------------------------------------------------------
        // Web-based Camera Capture & Upload Loop
        // -------------------------------------------------------------
        const btnStartCamera = document.getElementById('btn-start-camera');
        const btnTriggerAutoCapture = document.getElementById('btn-trigger-auto-capture');
        const captureStatusLoader = document.getElementById('capture-status-loader');
        const step3 = document.getElementById('step-3-indicator');
        
        let localStream = null;
        let autoCaptureInterval = null;
        let successCount = 0;
        const totalRequiredFrames = 20;

        if (btnStartCamera) {
            btnStartCamera.addEventListener('click', function() {
                // Request camera permission and start video element
                navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
                .then(function(stream) {
                    localStream = stream;
                    const videoElem = document.getElementById('capture-video');
                    videoElem.srcObject = stream;
                    
                    // Toggle button states
                    document.getElementById('webcam-container').style.display = 'block';
                    btnStartCamera.classList.add('hidden');
                    btnTriggerAutoCapture.classList.remove('hidden');
                    
                    // Show active indicator
                    if (captureStatusLoader) {
                        captureStatusLoader.classList.remove('hidden');
                        document.getElementById('capture-status-text').textContent = 'Camera active. Frame resolution: 640x480.';
                    }
                    
                    document.getElementById('capture-instructions-text').textContent = 
                        'Position your face clearly in the box and click "Start Auto Capture" to record 20 frames.';
                })
                .catch(function(err) {
                    showToast("Cannot access camera: " + err.message, "error");
                    console.error("Camera access error:", err);
                });
            });
        }

        if (btnTriggerAutoCapture) {
            btnTriggerAutoCapture.addEventListener('click', function() {
                successCount = 0;
                
                // Disable button and change state
                btnTriggerAutoCapture.disabled = true;
                btnTriggerAutoCapture.querySelector('span').textContent = 'Capturing... (0/20)';
                
                const canvasElem = document.getElementById('capture-canvas');
                const videoElem = document.getElementById('capture-video');
                const ctx = canvasElem.getContext('2d');
                
                // Match canvas width/height to video dimensions
                canvasElem.width = 640;
                canvasElem.height = 480;
                
                document.getElementById('capture-status-text').textContent = 'Analyzing and capturing face frames...';
                
                // Trigger auto capture loop every 650ms
                autoCaptureInterval = setInterval(function() {
                    // Draw mirror frame from video onto hidden canvas
                    ctx.drawImage(videoElem, 0, 0, canvasElem.width, canvasElem.height);
                    
                    // Get base64 JPEG
                    const dataUrl = canvasElem.toDataURL('image/jpeg', 0.9);
                    
                    fetch('/api/upload_capture', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            student_id: instructId.textContent,
                            image: dataUrl
                        })
                    })
                    .then(res => res.json())
                    .then(resData => {
                        if (resData.success) {
                            successCount = resData.count;
                            btnTriggerAutoCapture.querySelector('span').textContent = `Capturing... (${successCount}/${totalRequiredFrames})`;
                            document.getElementById('capture-status-text').textContent = `Saved frame ${successCount} successfully.`;
                            
                            // Check if threshold reached
                            if (successCount >= totalRequiredFrames) {
                                clearInterval(autoCaptureInterval);
                                autoCaptureInterval = null;
                                
                                // Turn off webcam stream
                                if (localStream) {
                                    localStream.getTracks().forEach(track => track.stop());
                                }
                                document.getElementById('webcam-container').style.display = 'none';
                                btnTriggerAutoCapture.classList.add('hidden');
                                
                                // Call Model Training route
                                document.getElementById('capture-status-text').textContent = 'Registering and encoding face vectors...';
                                document.getElementById('status-pulse-dot').style.backgroundColor = 'var(--warning-color)';
                                
                                fetch('/api/train_student', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json'
                                    },
                                    body: JSON.stringify({
                                        student_id: instructId.textContent
                                    })
                                })
                                .then(trainRes => trainRes.json())
                                .then(trainData => {
                                    if (captureStatusLoader) {
                                        captureStatusLoader.classList.add('hidden');
                                    }
                                    
                                    if (trainData.success) {
                                        showToast(trainData.message, 'success');
                                        document.getElementById('capture-instructions-text').innerHTML = 
                                            '<span style="color: var(--success-color); font-weight: 600; font-size: 1rem;"><i data-lucide="check-circle" style="vertical-align: middle; margin-right: 0.25rem;"></i> Registration & Encoding Complete!</span>';
                                        lucide.createIcons();
                                        
                                        // Update layout checklist
                                        if (step2 && step3) {
                                            step2.classList.remove('active');
                                            step3.classList.add('active');
                                        }
                                    } else {
                                        showToast(trainData.message || 'Face model encoding failed.', 'error');
                                        document.getElementById('capture-instructions-text').textContent = 'Training error. Please reset form and retry.';
                                    }
                                })
                                .catch(trainErr => {
                                    if (captureStatusLoader) {
                                        captureStatusLoader.classList.add('hidden');
                                    }
                                    showToast('Network error while processing face training.', 'error');
                                    console.error(trainErr);
                                });
                            }
                        } else {
                            // Display message if no face detected in uploaded frame
                            document.getElementById('capture-status-text').textContent = resData.message || 'Searching for face...';
                        }
                    })
                    .catch(err => {
                        console.error('Frame upload fail:', err);
                    });
                }, 650);
            });
        }
        
        // Reset Registration Form button inside instructions
        const btnReset = document.getElementById('btn-reset-form');
        if (btnReset) {
            btnReset.addEventListener('click', function() {
                registerForm.reset();
                
                // Clear any running camera/intervals
                if (autoCaptureInterval) {
                    clearInterval(autoCaptureInterval);
                    autoCaptureInterval = null;
                }
                if (localStream) {
                    localStream.getTracks().forEach(track => track.stop());
                    localStream = null;
                }
                
                // Re-enable form fields
                Array.from(registerForm.elements).forEach(elem => {
                    elem.disabled = false;
                });
                
                // Hide webcam and reset button elements
                document.getElementById('webcam-container').style.display = 'none';
                btnStartCamera.classList.remove('hidden');
                btnTriggerAutoCapture.classList.add('hidden');
                btnTriggerAutoCapture.disabled = false;
                btnTriggerAutoCapture.querySelector('span').textContent = 'Start Auto Capture';
                if (captureStatusLoader) {
                    captureStatusLoader.classList.add('hidden');
                }
                document.getElementById('capture-instructions-text').textContent = 
                    'Click "Start Web Camera" to embed the webcam stream and begin capturing images.';
                document.getElementById('status-pulse-dot').style.backgroundColor = 'var(--primary-color)';
                
                // Reset UI Checklist
                if (step1 && step2) {
                    step1.classList.add('active');
                    step2.classList.remove('active');
                }
                if (step3) {
                    step3.classList.remove('active');
                }
                
                if (captureInstructions) {
                    captureInstructions.classList.add('collapsed');
                }
                
                btnSubmit.classList.remove('hidden');
            });
        }
    }
});
