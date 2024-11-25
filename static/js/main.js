document.addEventListener('DOMContentLoaded', function() {
    // Store DOM elements with validation
    const elements = {
        form: document.getElementById('transcript-form'),
        urlInput: document.getElementById('youtube-url'),
        transcriptContainer: document.getElementById('transcript-container'),
        playlistContainer: document.getElementById('playlist-container'),
        errorMessage: document.getElementById('error-message'),
        loadingSpinner: document.getElementById('loading-spinner'),
        downloadButton: document.getElementById('download-button'),
        processLogs: document.getElementById('process-logs')
    };

    // Validate all required DOM elements
    const requiredElements = [
        'form', 'urlInput', 'transcriptContainer', 'playlistContainer',
        'errorMessage', 'loadingSpinner', 'downloadButton', 'processLogs'
    ];

    const missingElements = requiredElements.filter(elementName => !elements[elementName]);
    if (missingElements.length > 0) {
        console.error('Missing required DOM elements:', missingElements);
        throw new Error('Required DOM elements not found. Please check the HTML structure.');
    }

    // Constants for request configuration
    const REQUEST_TIMEOUT = 30000; // 30 seconds timeout
    let currentAbortController = null;
    let processingStartTime = null;
    let phaseStartTimes = {
        scraping: null,
        processing: null,
        merging: null
    };

    function updateProcessLogs(message, type = 'info') {
        const logsElement = document.getElementById('process-logs');
        if (logsElement) {
            const timestamp = new Date().toLocaleTimeString();
            const logClass = type === 'error' ? 'text-danger' : (type === 'success' ? 'text-success' : 'text-info');
            logsElement.innerHTML += `<span class="${logClass}">[${timestamp}] ${message}</span>\n`;
            logsElement.scrollTop = logsElement.scrollHeight;
        }
    }

    function formatElapsedTime(startTime) {
        if (!startTime) return '00:00';
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    function updateElapsedTime(phaseElement, startTime) {
        if (startTime) {
            const timeElement = phaseElement.querySelector('.elapsed-time');
            if (timeElement) {
                timeElement.textContent = formatElapsedTime(startTime);
            }
        }
    }

    function createPhaseProgress(phase, label) {
        const div = document.createElement('div');
        div.className = 'phase-progress';
        div.innerHTML = `
            <div class="phase-label">${label}</div>
            <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: 0%" 
                     aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
            </div>
            <div class="elapsed-time">00:00</div>
            <div class="current-operation"></div>
        `;
        return div;
    }

    function setElementDisplay(element, displayValue) {
        if (element && typeof element.style !== 'undefined') {
            try {
                element.style.display = displayValue;
            } catch (error) {
                console.error(`Error setting display for element:`, error);
                updateProcessLogs(`Error setting display for element: ${error.message}`, 'error');
            }
        }
    }

    function showLoading() {
        try {
            setElementDisplay(elements.loadingSpinner, 'block');
            setElementDisplay(elements.transcriptContainer, 'none');
            setElementDisplay(elements.playlistContainer, 'none');
            setElementDisplay(elements.errorMessage, 'none');
            setElementDisplay(elements.downloadButton, 'none');
            updateProcessLogs('Loading started...', 'info');
        } catch (error) {
            console.error('Error in showLoading:', error);
            updateProcessLogs(`Error in showLoading: ${error.message}`, 'error');
        }
    }

    function hideLoading() {
        try {
            setElementDisplay(elements.loadingSpinner, 'none');
            updateProcessLogs('Loading completed', 'success');
        } catch (error) {
            console.error('Error in hideLoading:', error);
            updateProcessLogs(`Error in hideLoading: ${error.message}`, 'error');
        }
    }

    function showError(message) {
        try {
            console.error('Showing error:', message);
            hideLoading();
            if (elements.errorMessage) {
                elements.errorMessage.textContent = message;
                setElementDisplay(elements.errorMessage, 'block');
            }
            setElementDisplay(elements.transcriptContainer, 'none');
            setElementDisplay(elements.playlistContainer, 'none');
            setElementDisplay(elements.downloadButton, 'none');
            updateProcessLogs(`Error: ${message}`, 'error');
        } catch (error) {
            console.error('Error in showError:', error);
            updateProcessLogs(`Error in showError: ${error.message}`, 'error');
        }
    }

    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            updateProcessLogs('Text copied to clipboard', 'success');
            return true;
        } catch (error) {
            console.error('Failed to copy:', error);
            updateProcessLogs(`Failed to copy: ${error.message}`, 'error');
            return false;
        }
    }

    function cleanupRequest() {
        try {
            if (currentAbortController) {
                currentAbortController.abort();
                currentAbortController = null;
            }
            hideLoading();
            updateProcessLogs('Request cleanup completed', 'info');
        } catch (error) {
            console.error('Error in cleanupRequest:', error);
            updateProcessLogs(`Error in cleanupRequest: ${error.message}`, 'error');
        }
    }

    function validateYouTubeUrl(url) {
        const patterns = [
            /^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/watch\?v=[\w-]{11}/,
            /^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/shorts\/[\w-]{11}/,
            /^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/live\/[\w-]{11}/,
            /^((?:https?:)?\/\/)?((?:www|m)\.)?(youtube\.com|youtube-nocookie\.com)\/embed\/[\w-]{11}/,
            /^((?:https?:)?\/\/)?youtu\.be\/[\w-]{11}/,
            /^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/playlist\?list=[\w-]+/
        ];

        url = url.split('&')[0];
        return patterns.some(pattern => pattern.test(url));
    }

    function isPlaylistUrl(url) {
        const playlistPattern = /^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/playlist\?list=[\w-]+/;
        return playlistPattern.test(url);
    }

    async function makeRequest(url, endpoint) {
        try {
            if (currentAbortController) {
                currentAbortController.abort();
            }

            currentAbortController = new AbortController();
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url }),
                signal: currentAbortController.signal,
                timeout: REQUEST_TIMEOUT
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            hideLoading();

            if (data.status === 'error') {
                throw new Error(data.error || 'Unknown error occurred');
            }

            return data;
        } catch (error) {
            hideLoading();
            showError(error.message || 'An unexpected error occurred. Please try again.');
            throw error;
        } finally {
            currentAbortController = null;
        }
    }

    async function processTranscripts(videoIds, style) {
        const response = await fetch('/download_transcript_batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                video_ids: videoIds,
                style: style
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const text = await response.text();
        return text;
    }

    async function checkDownloadProgress(videoIds) {
        try {
            const response = await fetch('/download_progress', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ video_ids: videoIds })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            return result.data.progress;
        } catch (error) {
            console.error('Error checking download progress:', error);
            throw error;
        }
    }

    function updatePhaseProgress(phase, progress, currentOperation = '') {
        const phaseElement = document.querySelector(`.phase-progress[data-phase="${phase}"]`);
        if (phaseElement) {
            const progressBar = phaseElement.querySelector('.progress-bar');
            const operationElement = phaseElement.querySelector('.current-operation');
            
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressBar.textContent = `${progress}%`;
                updateProcessLogs(`${phase} progress: ${progress}%`, 'info');
            }
            
            if (operationElement && currentOperation) {
                operationElement.textContent = currentOperation;
                updateProcessLogs(`${phase}: ${currentOperation}`, 'info');
            }
            
            updateElapsedTime(phaseElement, phaseStartTimes[phase]);
        }
    }

    function displayPlaylist(videos) {
        try {
            if (!elements.playlistContainer) {
                throw new Error('Playlist container element not found');
            }

            if (!Array.isArray(videos) || videos.length === 0) {
                throw new Error('No videos found in the playlist');
            }

            elements.playlistContainer.innerHTML = '';
            const videoList = document.createElement('div');
            videoList.className = 'video-list';
            
            // Add batch process button, download button, style selector, and select all checkbox
            const headerDiv = document.createElement('div');
            headerDiv.className = 'mb-3';
            headerDiv.innerHTML = `
                <div class="d-flex align-items-center mb-2">
                    <div class="me-3">
                        <input type="checkbox" id="select-all" class="video-select">
                        <label for="select-all" class="ms-2">Select All</label>
                    </div>
                </div>
                <div class="d-flex align-items-center">
                    <select class="form-select me-3" id="processing-style" style="width: auto;">
                        <option value="default">Default Style</option>
                        <option value="academic">Academic Style</option>
                        <option value="technical">Technical Style</option>
                        <option value="business">Business Style</option>
                    </select>
                    <button class="btn btn-youtube me-2" id="process-transcripts">Process Transcripts</button>
                    <button class="btn btn-youtube" id="download-transcripts" disabled>Download Transcripts</button>
                </div>
            `;
            elements.playlistContainer.appendChild(headerDiv);

            // Add progress container with phases
            const progressContainer = document.createElement('div');
            progressContainer.id = 'download-progress';
            progressContainer.className = 'progress-phases mb-3 d-none';
            
            // Add progress bars for each phase
            const scrapingProgress = createPhaseProgress('scraping', 'Scraping Transcripts');
            const processingProgress = createPhaseProgress('processing', 'Processing Transcripts');
            const mergingProgress = createPhaseProgress('merging', 'Merging Results');
            
            scrapingProgress.setAttribute('data-phase', 'scraping');
            processingProgress.setAttribute('data-phase', 'processing');
            mergingProgress.setAttribute('data-phase', 'merging');
            
            progressContainer.appendChild(scrapingProgress);
            progressContainer.appendChild(processingProgress);
            progressContainer.appendChild(mergingProgress);
            
            elements.playlistContainer.appendChild(progressContainer);
            
            // Add select all functionality
            const selectAllCheckbox = headerDiv.querySelector('#select-all');
            selectAllCheckbox.addEventListener('change', function() {
                const checkboxes = videoList.querySelectorAll('.video-select');
                checkboxes.forEach(checkbox => checkbox.checked = this.checked);
            });

            // Add videos to the list
            videos.forEach((video, index) => {
                try {
                    if (!video.title || !video.video_id) {
                        console.error(`Invalid video data at index ${index}:`, video);
                        return;
                    }

                    const videoUrl = `https://www.youtube.com/watch?v=${video.video_id}`;
                    const publishDate = video.publishedAt ? new Date(video.publishedAt).toLocaleDateString('tr-TR', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric'
                    }) : 'Date not available';
                    const videoItem = document.createElement('div');
                    videoItem.className = 'video-item';
                    videoItem.innerHTML = `
                        <input type="checkbox" class="video-select" value="${video.video_id}">
                        <span class="video-number">${index + 1}.</span>
                        <div class="video-info">
                            <div class="video-title">${video.title}</div>
                            <div class="video-date">${publishDate}</div>
                            <div class="video-url">${videoUrl}</div>
                            <button class="btn btn-sm btn-youtube copy-url" data-url="${videoUrl}">
                                Copy URL
                            </button>
                        </div>
                    `;

                    // Add click handler for copy button
                    const copyButton = videoItem.querySelector('.copy-url');
                    copyButton.addEventListener('click', async function() {
                        const url = this.getAttribute('data-url');
                        const success = await copyToClipboard(url);
                        
                        // Give user feedback
                        const originalText = this.textContent;
                        this.textContent = success ? 'Copied!' : 'Failed to copy';
                        setTimeout(() => {
                            this.textContent = originalText;
                        }, 2000);
                    });

                    videoList.appendChild(videoItem);
                } catch (error) {
                    console.error(`Error creating video item ${index}:`, error);
                }
            });
            
            elements.playlistContainer.appendChild(videoList);
            setElementDisplay(elements.playlistContainer, 'block');

            let processedContent = null;

            // Add process transcripts handler
            const processButton = headerDiv.querySelector('#process-transcripts');
            const downloadButton = headerDiv.querySelector('#download-transcripts');
            const styleSelect = headerDiv.querySelector('#processing-style');
            
            processButton.addEventListener('click', async function() {
                try {
                    const selectedVideos = Array.from(videoList.querySelectorAll('.video-select:checked'))
                        .map(checkbox => checkbox.value);
                    
                    if (selectedVideos.length === 0) {
                        showError('Please select at least one video');
                        return;
                    }

                    // Reset UI state
                    processButton.disabled = true;
                    downloadButton.disabled = true;
                    const progressContainer = document.getElementById('download-progress');
                    progressContainer.classList.remove('d-none');
                    
                    // Reset progress tracking
                    processingStartTime = Date.now();
                    phaseStartTimes.scraping = Date.now();
                    phaseStartTimes.processing = null;
                    phaseStartTimes.merging = null;

                    const selectedStyle = styleSelect.value;
                    let currentPhase = 'scraping';
                    
                    // Start progress monitoring
                    const progressInterval = setInterval(async () => {
                        try {
                            const progress = await checkDownloadProgress(selectedVideos);
                            let allCompleted = true;
                            let scrapingComplete = true;
                            let processingComplete = true;
                            
                            Object.entries(progress).forEach(([videoId, value]) => {
                                if (value < 50) {
                                    scrapingComplete = false;
                                    processingComplete = false;
                                } else if (value < 100) {
                                    processingComplete = false;
                                }
                                
                                if (value < 100 && value >= 0) {
                                    allCompleted = false;
                                }
                            });

                            // Update phase progress
                            if (currentPhase === 'scraping') {
                                const scrapingProgress = (Object.values(progress).filter(v => v >= 50).length / selectedVideos.length) * 100;
                                updatePhaseProgress('scraping', scrapingProgress, 'Fetching transcripts...');
                                
                                if (scrapingComplete) {
                                    currentPhase = 'processing';
                                    phaseStartTimes.processing = Date.now();
                                }
                            }
                            
                            if (currentPhase === 'processing') {
                                const processingProgress = (Object.values(progress).filter(v => v >= 75).length / selectedVideos.length) * 100;
                                updatePhaseProgress('processing', processingProgress, 'Processing with OpenAI...');
                                
                                if (processingComplete) {
                                    currentPhase = 'merging';
                                    phaseStartTimes.merging = Date.now();
                                }
                            }
                            
                            if (currentPhase === 'merging') {
                                updatePhaseProgress('merging', allCompleted ? 100 : 50, 'Merging results...');
                            }

                            if (allCompleted) {
                                clearInterval(progressInterval);
                                downloadButton.disabled = false;
                                processButton.disabled = false;
                            }
                        } catch (error) {
                            console.error('Progress check error:', error);
                            clearInterval(progressInterval);
                        }
                    }, 5000);

                    // Start processing
                    processedContent = await processTranscripts(selectedVideos, selectedStyle);
                    
                } catch (error) {
                    console.error('Processing error:', error);
                    showError(error.message || 'Failed to process transcripts');
                    processButton.disabled = false;
                }
            });
            
            // Add download handler
            downloadButton.addEventListener('click', async function() {
                if (processedContent) {
                    const blob = new Blob([processedContent], { type: 'text/plain' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'processed_transcripts.txt';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }
            });

        } catch (error) {
            console.error('Error in displayPlaylist:', error);
            showError(error.message || 'Failed to display playlist');
        }
    }

    // Form submission handler
    elements.form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const url = elements.urlInput.value.trim();
        
        try {
            if (!validateYouTubeUrl(url)) {
                throw new Error('Please enter a valid YouTube URL');
            }

            showLoading();
            const data = await makeRequest(url, '/get_playlist');
            displayPlaylist(data.data.videos);
        } catch (error) {
            showError(error.message || 'An error occurred while processing your request');
        }
    });

    // Initialize event listeners and setup
    elements.form.addEventListener('submit', async function(e) {
        e.preventDefault();
        updateProcessLogs('Form submitted', 'info');
        // ... rest of the form submission code
    });

    // Initialize the logs section collapse functionality
    const logsHeader = document.querySelector('.card-header[data-bs-toggle="collapse"]');
    if (logsHeader) {
        logsHeader.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (icon) {
                icon.style.transform = this.getAttribute('aria-expanded') === 'true' ? 'rotate(0deg)' : 'rotate(180deg)';
            }
        });
    }
});