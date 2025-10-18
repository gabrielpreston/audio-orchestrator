class TestPhraseRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioContext = null;
        this.analyser = null;
        this.microphone = null;
        this.visualizerCanvas = null;
        this.visualizerCtx = null;
        this.animationId = null;
        this.phrases = [];
        this.currentPhrase = null;
        this.isRecording = false;
        this.apiBaseUrl = window.location.origin;

        this.initializeElements();
        this.setupEventListeners();
        this.loadPhrases();
    }

    initializeElements() {
        this.phraseText = document.getElementById('phraseText');
        this.phraseCategory = document.getElementById('phraseCategory');
        this.addPhraseBtn = document.getElementById('addPhraseBtn');
        this.recordBtn = document.getElementById('recordBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.playBtn = document.getElementById('playBtn');
        this.recordingStatus = document.getElementById('recordingStatus');
        this.visualizerCanvas = document.getElementById('visualizerCanvas');
        this.visualizerCtx = this.visualizerCanvas.getContext('2d');
        this.phrasesList = document.getElementById('phrasesList');
        this.noPhrases = document.getElementById('noPhrases');
        this.exportMetadataBtn = document.getElementById('exportMetadataBtn');
        this.clearAllBtn = document.getElementById('clearAllBtn');
        this.errorMessage = document.getElementById('errorMessage');
        this.successMessage = document.getElementById('successMessage');
    }

    setupEventListeners() {
        this.addPhraseBtn.addEventListener('click', () => this.addPhrase());
        this.phraseText.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addPhrase();
        });
        this.recordBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.playBtn.addEventListener('click', () => this.playLastRecording());
        this.exportMetadataBtn.addEventListener('click', () => this.exportMetadata());
        this.clearAllBtn.addEventListener('click', () => this.clearAll());
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorMessage.style.display = 'block';
        setTimeout(() => {
            this.errorMessage.style.display = 'none';
        }, 5000);
    }

    showSuccess(message) {
        this.successMessage.textContent = message;
        this.successMessage.style.display = 'block';
        setTimeout(() => {
            this.successMessage.style.display = 'none';
        }, 3000);
    }

    async addPhrase() {
        const text = this.phraseText.value.trim();
        const category = this.phraseCategory.value;

        if (!text) {
            this.showError('Please enter a phrase text');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text, category })
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentPhrase = result.phrase;
                this.phraseText.value = '';
                this.recordBtn.disabled = false;
                this.showSuccess(`Added phrase: "${text}"`);
            } else {
                this.showError(result.error || 'Failed to add phrase');
            }
        } catch (error) {
            this.showError('Error adding phrase: ' + error.message);
        }
    }

    async startRecording() {
        if (!this.currentPhrase) {
            this.showError('Please add a phrase first');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 48000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 48000
            });
            this.analyser = this.audioContext.createAnalyser();
            this.microphone = this.audioContext.createMediaStreamSource(stream);
            this.microphone.connect(this.analyser);

            this.analyser.fftSize = 256;
            const bufferLength = this.analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });

            this.audioChunks = [];
            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = () => {
                this.saveRecording();
            };

            this.mediaRecorder.start();
            this.isRecording = true;
            this.updateRecordingUI(true);
            this.startVisualization(dataArray);

        } catch (error) {
            this.showError('Error accessing microphone: ' + error.message);
        }
    }

    async saveRecording() {
        if (!this.currentPhrase || this.audioChunks.length === 0) {
            return;
        }

        try {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            reader.onload = async () => {
                const base64Data = reader.result.split(',')[1];
                
                const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases/${this.currentPhrase.id}/audio`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        phrase_id: this.currentPhrase.id,
                        audio_data: base64Data,
                        audio_format: 'webm'
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showSuccess('Recording saved successfully');
                    this.playBtn.disabled = false;
                    this.loadPhrases(); // Refresh the phrases list
                } else {
                    this.showError(result.error || 'Failed to save recording');
                }
            };
            reader.readAsDataURL(audioBlob);

        } catch (error) {
            this.showError('Error saving recording: ' + error.message);
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.updateRecordingUI(false);
            this.stopVisualization();

            // Stop all tracks
            if (this.audioContext) {
                this.audioContext.close();
            }
        }
    }

    updateRecordingUI(recording) {
        if (recording) {
            this.recordBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.recordingStatus.className = 'recording-status recording';
            this.recordingStatus.querySelector('span').textContent = 'Recording...';
            this.recordingStatus.querySelector('.pulse').style.display = 'block';
        } else {
            this.recordBtn.disabled = false;
            this.stopBtn.disabled = true;
            this.recordingStatus.className = 'recording-status stopped';
            this.recordingStatus.querySelector('span').textContent = 'Ready to record';
            this.recordingStatus.querySelector('.pulse').style.display = 'none';
        }
    }

    startVisualization(dataArray) {
        const canvas = this.visualizerCanvas;
        const ctx = this.visualizerCtx;
        const width = canvas.width = canvas.offsetWidth;
        const height = canvas.height = canvas.offsetHeight;

        const draw = () => {
            if (!this.isRecording) return;

            this.analyser.getByteFrequencyData(dataArray);
            
            ctx.fillStyle = '#f9fafb';
            ctx.fillRect(0, 0, width, height);

            const barWidth = (width / dataArray.length) * 2.5;
            let barHeight;
            let x = 0;

            for (let i = 0; i < dataArray.length; i++) {
                barHeight = (dataArray[i] / 255) * height;
                
                const gradient = ctx.createLinearGradient(0, height - barHeight, 0, height);
                gradient.addColorStop(0, '#4f46e5');
                gradient.addColorStop(1, '#7c3aed');
                
                ctx.fillStyle = gradient;
                ctx.fillRect(x, height - barHeight, barWidth, barHeight);
                
                x += barWidth + 1;
            }

            this.animationId = requestAnimationFrame(draw);
        };

        draw();
    }

    stopVisualization() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        
        // Clear canvas
        const canvas = this.visualizerCanvas;
        const ctx = this.visualizerCtx;
        ctx.fillStyle = '#f9fafb';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    async playLastRecording() {
        if (this.currentPhrase && this.currentPhrase.id) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases/${this.currentPhrase.id}/audio`);
                if (response.ok) {
                    const audioBlob = await response.blob();
                    const audio = new Audio(URL.createObjectURL(audioBlob));
                    audio.play().catch(error => {
                        this.showError('Error playing audio: ' + error.message);
                    });
                } else {
                    this.showError('Audio file not found');
                }
            } catch (error) {
                this.showError('Error playing audio: ' + error.message);
            }
        }
    }

    async loadPhrases() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases`);
            const result = await response.json();
            
            if (result.success) {
                this.phrases = result.phrases;
                this.updatePhrasesList();
                this.updateExportButtons();
            } else {
                this.showError(result.error || 'Failed to load phrases');
            }
        } catch (error) {
            this.showError('Error loading phrases: ' + error.message);
        }
    }

    updatePhrasesList() {
        if (this.phrases.length === 0) {
            this.noPhrases.style.display = 'block';
            return;
        }

        this.noPhrases.style.display = 'none';
        this.phrasesList.innerHTML = '';

        this.phrases.forEach((phrase, index) => {
            const phraseItem = document.createElement('div');
            phraseItem.className = 'phrase-item';
            
            const duration = phrase.audio_duration ? 
                Math.round(phrase.audio_duration) + 's' : 'No audio';
            const size = phrase.audio_size ? 
                Math.round(phrase.audio_size / 1000) + ' KB' : 'No audio';

            phraseItem.innerHTML = `
                <div class="phrase-info">
                    <div class="phrase-text">${phrase.text}</div>
                    <div class="phrase-meta">
                        ${phrase.category} • ${new Date(phrase.timestamp).toLocaleString()} • ${duration} • ${size}
                    </div>
                </div>
                <div class="phrase-actions">
                    <button class="btn btn-small btn-secondary" onclick="recorder.playPhrase('${phrase.id}')">
                        ▶️ Play
                    </button>
                    <button class="btn btn-small btn-primary" onclick="recorder.convertPhrase('${phrase.id}')">
                        🔄 Convert
                    </button>
                    <button class="btn btn-small btn-danger" onclick="recorder.deletePhrase('${phrase.id}')">
                        🗑️ Delete
                    </button>
                </div>
            `;

            this.phrasesList.appendChild(phraseItem);
        });
    }

    async playPhrase(phraseId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases/${phraseId}/audio`);
            if (response.ok) {
                const audioBlob = await response.blob();
                const audio = new Audio(URL.createObjectURL(audioBlob));
                audio.play().catch(error => {
                    this.showError('Error playing audio: ' + error.message);
                });
            } else {
                this.showError('Audio file not found');
            }
        } catch (error) {
            this.showError('Error playing audio: ' + error.message);
        }
    }

    async convertPhrase(phraseId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases/${phraseId}/convert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ sample_rate: 48000 })
            });

            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('Audio converted to WAV format');
                this.loadPhrases(); // Refresh the phrases list
            } else {
                this.showError(result.error || 'Failed to convert audio');
            }
        } catch (error) {
            this.showError('Error converting audio: ' + error.message);
        }
    }

    async deletePhrase(phraseId) {
        if (confirm('Are you sure you want to delete this phrase?')) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases/${phraseId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showSuccess('Phrase deleted successfully');
                    this.loadPhrases();
                } else {
                    this.showError(result.error || 'Failed to delete phrase');
                }
            } catch (error) {
                this.showError('Error deleting phrase: ' + error.message);
            }
        }
    }

    updateExportButtons() {
        const hasPhrases = this.phrases.length > 0;
        this.exportMetadataBtn.disabled = !hasPhrases;
        this.clearAllBtn.disabled = !hasPhrases;
    }

    async exportMetadata() {
        if (this.phrases.length === 0) {
            this.showError('No phrases to export');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/test-recorder/metadata`);
            const result = await response.json();
            
            if (result.success) {
                const blob = new Blob([JSON.stringify(result.metadata, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `test_phrases_metadata_${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                this.showSuccess('Metadata exported successfully');
            } else {
                this.showError(result.error || 'Failed to export metadata');
            }
        } catch (error) {
            this.showError('Error exporting metadata: ' + error.message);
        }
    }

    async clearAll() {
        if (confirm('Are you sure you want to clear all phrases? This cannot be undone.')) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/test-recorder/phrases`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showSuccess(`Cleared ${result.cleared_count} phrases`);
                    this.phrases = [];
                    this.currentPhrase = null;
                    this.updatePhrasesList();
                    this.updateExportButtons();
                    this.recordBtn.disabled = true;
                    this.playBtn.disabled = true;
                } else {
                    this.showError(result.error || 'Failed to clear phrases');
                }
            } catch (error) {
                this.showError('Error clearing phrases: ' + error.message);
            }
        }
    }
}

// Initialize the recorder when the page loads
const recorder = new TestPhraseRecorder();