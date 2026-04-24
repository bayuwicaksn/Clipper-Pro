/* ═══════════════════════════════════════════════════════════════
   ClipperApp — Frontend Logic
   ═══════════════════════════════════════════════════════════════ */

// ─── State ──────────────────────────────────────────────────────
let currentJobId = null;
let eventSource = null;
const stepOrder = ['download', 'analyze', 'clip', 'reframe', 'hook', 'caption', 'finalize'];
let completedSteps = new Set();

// ─── DOM References ─────────────────────────────────────────────
const $url = document.getElementById('youtube-url');
const $btnProcess = document.getElementById('btn-process');
const $sectionInput = document.getElementById('section-input');
const $sectionProgress = document.getElementById('section-progress');
const $sectionResults = document.getElementById('section-results');
const $sectionError = document.getElementById('section-error');
const $progressBar = document.getElementById('overall-progress');
const $progressText = document.getElementById('progress-text');
const $clipsGrid = document.getElementById('clips-grid');
const $errorMessage = document.getElementById('error-message');
const $connectionStatus = document.getElementById('connection-status');

// ─── Settings Toggle ────────────────────────────────────────────
function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    const toggle = document.getElementById('settings-toggle');
    panel.classList.toggle('open');
    toggle.classList.toggle('active');
}

function updateRangeDisplay(input) {
    const valSpan = document.getElementById(input.id + '-val');
    if (valSpan) valSpan.textContent = input.value;
}


async function uploadCookies(input) {
    const file = input.files[0];
    if (!file) return;
    const status = document.getElementById('cookies-status');
    status.textContent = 'Uploading...';
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/upload-cookies', { method: 'POST', body: formData });
        const data = await res.json();
        status.textContent = res.ok ? '✅ Uploaded!' : '❌ ' + data.error;
    } catch (e) {
        status.textContent = '❌ Upload failed';
    }
}

// ─── Process Video ──────────────────────────────────────────────
async function startProcessing() {
    const url = $url.value.trim();

    if (!url) {
        shakeElement($url.closest('.input-wrapper'));
        return;
    }

    // Validate YouTube URL
    if (!isValidYouTubeUrl(url)) {
        shakeElement($url.closest('.input-wrapper'));
        return;
    }

    const config = {
        url: url,
        num_clips: parseInt(document.getElementById('num-clips').value),
        min_duration: parseInt(document.getElementById('min-duration').value),
        max_duration: parseInt(document.getElementById('max-duration').value),
        reframe_mode: document.getElementById('reframe-mode').value,
        tts_voice: document.getElementById('tts-voice').value,
        enable_hook: document.getElementById('enable-hook').checked,
        enable_captions: document.getElementById('enable-captions').checked,
    };

    // Disable button
    $btnProcess.disabled = true;
    $btnProcess.innerHTML = '<span class="spinner"></span><span>Starting...</span>';

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to start processing');
        }

        currentJobId = data.job_id;
        showProgressSection();
        startSSE(currentJobId);

    } catch (err) {
        showError(err.message);
        resetButton();
    }
}

// ─── SSE Progress ───────────────────────────────────────────────
function startSSE(jobId) {
    if (eventSource) eventSource.close();
    if (window._pollTimer) clearInterval(window._pollTimer);

    let sseWorking = false;

    eventSource = new EventSource(`/api/progress/${jobId}`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.step !== 'heartbeat' && data.step !== 'connected') {
            sseWorking = true;
        }
        handleProgressEvent(data);
    };

    eventSource.onerror = () => {
        updateConnectionStatus('Reconnecting...', false);
    };

    eventSource.onopen = () => {
        updateConnectionStatus('Connected', true);
    };

    // Start polling fallback after 5 seconds if SSE hasn't delivered real events
    setTimeout(() => {
        if (!sseWorking) {
            console.log('[ClipperApp] SSE not working, switching to polling fallback');
            startPolling(jobId);
        }
    }, 5000);
}

let pollInterval = null;

function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    updateConnectionStatus('Polling', true);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress-poll/${jobId}`);
            const data = await res.json();

            if (data.latest_event && data.latest_event.step !== 'waiting') {
                handleProgressEvent(data.latest_event);
            }

            if (data.status === 'completed') {
                clearInterval(pollInterval);
                pollInterval = null;
                // Mark all steps done
                stepOrder.forEach(s => markStepCompleted(s));
                $progressBar.style.width = '100%';
                closeSSE();
                setTimeout(() => loadResults(), 500);
            } else if (data.status === 'error') {
                clearInterval(pollInterval);
                pollInterval = null;
                closeSSE();
                showError(data.error || 'Pipeline failed');
            }
        } catch (e) {
            console.error('[Poll] Error:', e);
        }
    }, 2000);

    window._pollTimer = pollInterval;
}

function handleProgressEvent(event) {
    const { step, message, progress } = event;

    // Update progress bar
    if (progress > 0) {
        $progressBar.style.width = progress + '%';
    }
    $progressText.textContent = message;

    // Update pipeline steps
    if (step === 'heartbeat') return;

    if (step === 'done') {
        // Mark all remaining steps as completed
        stepOrder.forEach(s => markStepCompleted(s));
        $progressBar.style.width = '100%';
        closeSSE();
        setTimeout(() => loadResults(), 500);
        return;
    }

    if (step === 'error') {
        closeSSE();
        showError(message);
        return;
    }

    if (step === 'warning') return;

    // Mark current step as active, previous as completed
    const stepIdx = stepOrder.indexOf(step);
    if (stepIdx >= 0) {
        // Complete all previous steps
        for (let i = 0; i < stepIdx; i++) {
            markStepCompleted(stepOrder[i]);
        }
        markStepActive(step);
    }
}

function markStepActive(step) {
    const el = document.querySelector(`.pipeline-step[data-step="${step}"]`);
    if (!el) return;
    el.classList.remove('completed');
    el.classList.add('active');
    el.querySelector('.step-badge').textContent = 'Processing';
}

function markStepCompleted(step) {
    if (completedSteps.has(step)) return;
    completedSteps.add(step);
    const el = document.querySelector(`.pipeline-step[data-step="${step}"]`);
    if (!el) return;
    el.classList.remove('active');
    el.classList.add('completed');
    el.querySelector('.step-badge').textContent = 'Done';
}

function closeSSE() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// ─── Results ────────────────────────────────────────────────────
async function loadResults() {
    try {
        const response = await fetch(`/api/clips/${currentJobId}`);
        const data = await response.json();

        if (data.clips && data.clips.length > 0) {
            showResultsSection(data.clips);
        } else {
            showError('No clips were generated. The video might not have had enough engaging content.');
        }
    } catch (err) {
        showError('Failed to load results: ' + err.message);
    }
}

function showResultsSection(clips) {
    $sectionProgress.classList.add('hidden');
    $sectionResults.classList.remove('hidden');

    document.getElementById('results-subtitle').textContent =
        `Generated ${clips.length} clip${clips.length !== 1 ? 's' : ''} ready to download`;

    $clipsGrid.innerHTML = '';

    clips.forEach((clip, i) => {
        const card = createClipCard(clip, i);
        $clipsGrid.appendChild(card);
    });
}

function createClipCard(clip, index) {
    const card = document.createElement('div');
    card.className = 'clip-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.animation = 'fadeInUp 0.5s ease forwards';

    const tagsHtml = (clip.tags || []).slice(0, 4)
        .map(t => `<span class="clip-tag">#${t}</span>`).join('');

    const duration = clip.duration_seconds
        ? `${Math.floor(clip.duration_seconds / 60)}:${String(Math.floor(clip.duration_seconds % 60)).padStart(2, '0')}`
        : '';

    card.innerHTML = `
        <div class="clip-preview" id="preview-${index}">
            <video
                src="/api/preview/${currentJobId}/${clip.filename}"
                preload="metadata"
                loop
                muted
                playsinline
                id="video-${index}"
            ></video>
            <div class="play-overlay" onclick="toggleVideo(${index})">
                <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
        </div>
        <div class="clip-info">
            <div class="clip-title">${escapeHtml(clip.title || `Clip ${index + 1}`)}</div>
            <div class="clip-meta">
                <div class="clip-tags">${tagsHtml}</div>
                ${duration ? `<span class="clip-duration"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>${duration}</span>` : ''}
            </div>
            <div class="clip-actions">
                <button class="btn btn-primary" onclick="window.open('http://localhost:5173/?project=' + currentJobId, '_blank')" style="flex: 1; padding: 0.6rem 0.5rem;" title="Edit clip">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    <span>Edit in NLE</span>
                </button>
                <button class="btn btn-download" onclick="downloadClip('${clip.filename}')" title="Download">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
                <button class="btn btn-copy-meta btn-secondary" onclick="copyMetadata(${index})" title="Copy metadata">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
                <button class="btn btn-regen-meta btn-secondary" style="border-color: var(--accent-purple); color: var(--accent-purple);" id="btn-regen-${index}" onclick="regenerateMetadata(${index}, '${clip.filename}')" title="Regenerate Metadata">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.92-10.22l-4.28 4.28"/></svg>
                </button>
            </div>
        </div>
    `;

    // Store metadata for copy
    card.dataset.metadata = JSON.stringify(clip);

    return card;
}

// ─── Video Preview ──────────────────────────────────────────────
function toggleVideo(index) {
    const video = document.getElementById(`video-${index}`);
    if (!video) return;

    if (video.paused) {
        // Pause all other videos
        document.querySelectorAll('.clip-preview video').forEach(v => {
            if (v !== video) v.pause();
        });
        video.muted = false;
        video.play();
    } else {
        video.pause();
    }
}

// ─── Actions ────────────────────────────────────────────────────
async function regenerateMetadata(index, filename) {
    const btn = document.getElementById(`btn-regen-${index}`);
    const originalContent = btn.innerHTML;
    
    btn.innerHTML = `<span class="spinner" style="width: 14px; height: 14px;"></span> <span>Wait...</span>`;
    btn.disabled = true;

    try {
        const response = await fetch(`/api/regenerate/${currentJobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to regenerate');
        }

        // Re-render this specific card's info
        const card = document.querySelectorAll('.clip-card')[index];
        const infoDiv = card.querySelector('.clip-info');
        
        const tagsHtml = (data.tags || []).slice(0, 4)
            .map(t => `<span class="clip-tag">#${t}</span>`).join('');
            
        const durationHtml = data.duration_seconds
            ? `<span class="clip-duration"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>${Math.floor(data.duration_seconds / 60)}:${String(Math.floor(data.duration_seconds % 60)).padStart(2, '0')}</span>` 
            : '';

        infoDiv.innerHTML = `
            <div class="clip-title">${escapeHtml(data.title || `Clip ${index + 1}`)}</div>
            <div class="clip-meta">
                <div class="clip-tags">${tagsHtml}</div>
                ${durationHtml}
            </div>
            <div class="clip-actions">
                <button class="btn btn-download" onclick="downloadClip('${data.filename}')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>Download</span>
                </button>
                <button class="btn btn-copy-meta btn-secondary" style="flex: 1;" onclick="copyMetadata(${index})" title="Copy title & description">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    <span>Copy</span>
                </button>
                <button class="btn btn-regen-meta btn-secondary" style="flex: 1; border-color: var(--accent-purple); color: var(--accent-purple);" id="btn-regen-${index}" onclick="regenerateMetadata(${index}, '${data.filename}')" title="AI Regenerate Metadata">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.92-10.22l-4.28 4.28"/></svg>
                    <span>Regen</span>
                </button>
            </div>
        `;
        
        card.dataset.metadata = JSON.stringify(data);
        
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        // Find button again because innerHTML replace above destroys the old button reference
        const newBtn = document.getElementById(`btn-regen-${index}`);
        if (newBtn) {
            newBtn.innerHTML = originalContent;
            newBtn.disabled = false;
        }
    }
}

function downloadClip(filename) {
    window.open(`/api/download/${currentJobId}/${filename}`, '_blank');
}

function copyMetadata(index) {
    const card = document.querySelectorAll('.clip-card')[index];
    if (!card) return;

    const meta = JSON.parse(card.dataset.metadata);
    const text = [
        meta.title || '',
        '',
        meta.description || '',
        '',
        (meta.tags || []).map(t => `#${t}`).join(' '),
    ].join('\n');

    navigator.clipboard.writeText(text).then(() => {
        const btn = card.querySelector('.btn-copy-meta span');
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 2000);
    });
}

// ─── UI Helpers ─────────────────────────────────────────────────
function showProgressSection() {
    $sectionInput.classList.add('hidden');
    $sectionProgress.classList.remove('hidden');
    $sectionResults.classList.add('hidden');
    $sectionError.classList.add('hidden');
    document.getElementById('section-editor').classList.add('hidden');

    // Reset steps
    completedSteps.clear();
    document.querySelectorAll('.pipeline-step').forEach(el => {
        el.classList.remove('active', 'completed', 'error');
        el.querySelector('.step-badge').textContent = 'Waiting';
    });
    $progressBar.style.width = '0%';
    $progressText.textContent = 'Initializing...';
}

function showError(message) {
    $sectionProgress.classList.add('hidden');
    $sectionError.classList.remove('hidden');
    document.getElementById('section-editor').classList.add('hidden');
    $errorMessage.textContent = message;
    resetButton();
}

function resetApp() {
    closeSSE();
    currentJobId = null;
    completedSteps.clear();

    $sectionInput.classList.remove('hidden');
    $sectionProgress.classList.add('hidden');
    $sectionResults.classList.add('hidden');
    $sectionError.classList.add('hidden');
    document.getElementById('section-editor').classList.add('hidden');

    $url.value = '';
    resetButton();
    updateConnectionStatus('Ready', true);
}

function resetButton() {
    $btnProcess.disabled = false;
    $btnProcess.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        <span>Process</span>
    `;
}

function shakeElement(el) {
    el.style.animation = 'none';
    el.offsetHeight; // Force reflow
    el.style.animation = 'shake 0.4s ease';
    setTimeout(() => el.style.animation = '', 400);
}

function updateConnectionStatus(text, connected) {
    $connectionStatus.querySelector('span:last-child').textContent = text;
    const dot = $connectionStatus.querySelector('.status-dot');
    dot.style.background = connected ? 'var(--accent-green)' : 'var(--accent-amber)';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function isValidYouTubeUrl(url) {
    const patterns = [
        /^https?:\/\/(www\.)?youtube\.com\/watch\?v=[\w-]+/,
        /^https?:\/\/youtu\.be\/[\w-]+/,
        /^https?:\/\/(www\.)?youtube\.com\/shorts\/[\w-]+/,
    ];
    return patterns.some(p => p.test(url));
}

// ─── CSS Animation for Shake ────────────────────────────────────
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-8px); }
        40% { transform: translateX(8px); }
        60% { transform: translateX(-4px); }
        80% { transform: translateX(4px); }
    }
`;
document.head.appendChild(style);

// ─── Keyboard Shortcut ─────────────────────────────────────────
$url.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') startProcessing();
});

// ─── Project Library Logic ──────────────────────────────────────
const $projectsGrid = document.getElementById('projects-grid');
const $sectionLibrary = document.getElementById('section-library');

async function loadProjects() {
    $projectsGrid.innerHTML = `
        <div class="loading-state">
            <span class="spinner"></span>
            <span>Loading your library...</span>
        </div>
    `;

    try {
        const res = await fetch('/api/projects');
        const projects = await res.json();

        if (!projects || projects.length === 0) {
            $projectsGrid.innerHTML = `
                <div class="empty-state">
                    <p>No projects found in your workspace.</p>
                </div>
            `;
            return;
        }

        $projectsGrid.innerHTML = '';
        projects.forEach((proj, idx) => {
            const card = document.createElement('div');
            card.className = 'project-card';
            card.style.animationDelay = `${idx * 0.05}s`;
            card.style.animation = 'fadeInUp 0.4s ease forwards';

            const dateStr = proj.created_at ? new Date(proj.created_at).toLocaleDateString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
            }) : 'Unknown date';

            card.innerHTML = `
                <div class="project-thumb">
                    <img src="${proj.thumbnail || 'https://via.placeholder.com/320x180?text=No+Thumbnail'}" alt="Thumbnail" onerror="this.src='https://via.placeholder.com/320x180?text=Error+Loading+Image'">
                    <span class="clip-badge">${proj.clip_count} Clip${proj.clip_count !== 1 ? 's' : ''}</span>
                </div>
                <div class="project-content">
                    <div class="project-card-title" title="${escapeHtml(proj.title)}">${escapeHtml(proj.title)}</div>
                    <div class="project-date">${dateStr}</div>
                    <div class="project-actions">
                        ${proj.clip_count > 0 ? `
                        <button class="btn btn-secondary btn-sm" onclick="viewProject('${proj.id}')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            <span>View Clips</span>
                        </button>
                        ` : `
                        <button class="btn btn-primary btn-sm" onclick="reprocessJob('${proj.id}', '${proj.video_url || ''}')" style="background: var(--accent-amber); box-shadow: none;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                            <span>Resume</span>
                        </button>
                        `}
                    </div>
                </div>
            `;
            $projectsGrid.appendChild(card);
        });
    } catch (e) {
        $projectsGrid.innerHTML = `
            <div class="empty-state">
                <p>Failed to load projects: ${e.message}</p>
            </div>
        `;
    }
}

async function viewProject(jobId) {
    currentJobId = jobId;
    $sectionInput.classList.add('hidden');
    $sectionLibrary.classList.add('hidden');
    $sectionProgress.classList.add('hidden');

    try {
        await loadResults();
    } catch (e) {
        showError('Could not load project clips.');
    }
}

async function reprocessJob(jobId, url) {
    if (!confirm('Resume processing this video? The large video file is already downloaded and will be reused.')) {
        return;
    }

    const config = {
        url: url,
        num_clips: parseInt(document.getElementById('num-clips').value),
        min_duration: parseInt(document.getElementById('min-duration').value),
        max_duration: parseInt(document.getElementById('max-duration').value),
        reframe_mode: document.getElementById('reframe-mode').value,
        tts_voice: document.getElementById('tts-voice').value,
        enable_hook: document.getElementById('enable-hook').checked,
        enable_captions: document.getElementById('enable-captions').checked,
    };

    $sectionLibrary.classList.add('hidden');
    showProgressSection();
    document.querySelectorAll('.pipeline-step').forEach(el => el.classList.remove('active', 'completed', 'error'));
    $progressText.textContent = 'Resuming...';

    try {
        const response = await fetch(`/api/reprocess/${jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to resume processing');
        }

        currentJobId = data.job_id;
        startSSE(currentJobId);

    } catch (err) {
        showError(err.message);
        resetButton();
    }
}

// Override resetApp to include library visibility
const originalResetApp = resetApp;
resetApp = function() {
    originalResetApp();
    $sectionLibrary.classList.remove('hidden');
    loadProjects(); // Refresh library on reset
};

// ─── Editor Logic ───────────────────────────────────────────────
let editorClipMeta = null;
let editorStartSecs = 0;
let editorEndSecs = 0;
let editorCropXPct = 0.5;

function timestampToSeconds(ts) {
    if (!ts) return 0;
    const parts = ts.split(':');
    return parseFloat(parts[0])*3600 + parseFloat(parts[1])*60 + parseFloat(parts[2]);
}

function secondsToTimestamp(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = (secs % 60).toFixed(3);
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(6,'0')}`;
}

function openEditor(clipIndex) {
    const card = document.querySelectorAll('.clip-card')[clipIndex];
    if (!card) return;
    const meta = JSON.parse(card.dataset.metadata);
    editorClipMeta = meta;

    // Hide other sections
    $sectionResults.classList.add('hidden');
    $sectionLibrary.classList.add('hidden');
    $sectionInput.classList.add('hidden');
    document.getElementById('section-editor').classList.remove('hidden');

    // Parse bounds
    editorStartSecs = timestampToSeconds(meta.start_time);
    editorEndSecs = timestampToSeconds(meta.end_time);

    // Setup Video Player (Load source video!)
    const video = document.getElementById('editor-video');
    video.src = `/api/preview_source/${currentJobId}#t=${editorStartSecs}`;
    
    // Custom timeline logic to loop bounds
    video.ontimeupdate = () => {
        if (video.currentTime > editorEndSecs + 0.5) { // Add 0.5s buffer to prevent aggressive looping cut
            video.currentTime = editorStartSecs;
        } else if (video.currentTime < editorStartSecs - 0.5) {
            video.currentTime = editorStartSecs;
        }
        
        // Update visual timeline bar
        const duration = video.duration || (editorEndSecs + 30); // fallback if metadata not loaded
        const pct = (video.currentTime / duration) * 100;
        document.getElementById('editor-timeline-fill').style.width = `${pct}%`;
    };

    video.play().catch(e => console.log('Autoplay prevented', e));

    // Setup Vertical Frame Draggable Logic
    editorCropXPct = (meta.custom_crop_x !== undefined) ? meta.custom_crop_x : 0.5;
    const frame = document.querySelector('.vertical-frame');
    frame.style.setProperty('--crop-x', `${editorCropXPct * 100}%`);
    
    frame.onmousedown = (e) => {
        e.preventDefault();
        const startX = e.clientX;
        const startPct = editorCropXPct;
        const thumbWidth = frame.parentElement.clientWidth;
        const frameW = frame.clientWidth / thumbWidth; 
        
        let isDrag = false;

        document.onmousemove = (moveEvent) => {
            isDrag = true;
            const dx = moveEvent.clientX - startX;
            let newPct = startPct + (dx / thumbWidth);
            
            const minPct = frameW / 2;
            const maxPct = 1 - (frameW / 2);
            
            if (newPct < minPct) newPct = minPct;
            if (newPct > maxPct) newPct = maxPct;
            
            editorCropXPct = newPct;
            frame.style.setProperty('--crop-x', `${newPct * 100}%`);
        };
        
        document.onmouseup = () => {
            document.onmousemove = null;
            document.onmouseup = null;
            if (!isDrag) {
                // If they just clicked without dragging, toggle play
                if (video.paused) video.play();
                else video.pause();
            }
        };
    };

    // Setup timeline (basic visualization bounds text)
    const durationMins = Math.floor((meta.duration_seconds || (editorEndSecs - editorStartSecs)) / 60);
    const durationSecs = Math.floor((meta.duration_seconds || (editorEndSecs - editorStartSecs)) % 60);
    document.getElementById('editor-time-start').textContent = `${Math.floor(editorStartSecs/60)}:${String(Math.floor(editorStartSecs%60)).padStart(2,'0')}`;
    document.getElementById('editor-time-end').textContent = `Duration: ${durationMins}:${String(durationSecs).padStart(2, '0')}`;

    // Populate Sidebar: Related Clips
    const allCards = document.querySelectorAll('.clip-card');
    const clipsListHtml = Array.from(allCards).map((c, i) => {
        const cMeta = JSON.parse(c.dataset.metadata);
        const dur = cMeta.duration_seconds 
            ? `${Math.floor(cMeta.duration_seconds/60)}:${String(Math.floor(cMeta.duration_seconds%60)).padStart(2,'0')}` 
            : '--:--';
        return `
            <div class="clip-list-item ${i === clipIndex ? 'selected' : ''}" onclick="openEditor(${i})">
                <div style="flex:1;">
                    <div style="font-size: 13px; font-weight: 600; line-height: 1.2; margin-bottom:4px;">${escapeHtml(cMeta.title || `Clip ${i+1}`)}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${dur}</div>
                </div>
            </div>
        `;
    }).join('');
    document.getElementById('editor-clips-list').innerHTML = clipsListHtml;

    // Populate Sidebar: Captions
    // Currently, we don't have deep word-by-word JSON attached to metadata, 
    // so we mock the caption blocks using the clip's description or hook.
    let capLineHtml = '';
    if (meta.extract) {
        // Just break the extract into faux lines for visualization
        const words = meta.extract.split(' ');
        const chunks = [];
        for (let i = 0; i < words.length; i += 6) {
            chunks.push(words.slice(i, i + 6).join(' '));
        }
        capLineHtml = chunks.map((chunk, i) => {
            const ts = `0:0${i * 2 % 10}`; // mock timestamp
            return `
                <div class="cap-line">
                    <span class="cap-ts">${ts}</span>
                    <span>${escapeHtml(chunk)}</span>
                </div>
            `;
        }).join('');
    } else {
        capLineHtml = `
            <div class="cap-line">
                <span class="cap-ts">0:00</span>
                <span>No specific caption data extracted.</span>
            </div>
        `;
    }
    document.getElementById('editor-captions-list').innerHTML = capLineHtml;
}

function closeEditor() {
    const video = document.getElementById('editor-video');
    video.pause();
    video.src = '';
    video.ontimeupdate = null;
    document.getElementById('section-editor').classList.add('hidden');
    $sectionResults.classList.remove('hidden');
    $sectionLibrary.classList.remove('hidden');
}

async function downloadEditorClip() {
    if (!editorClipMeta || !currentJobId) return;

    // Grab custom times (in a real app, these would come from the user dragging the timeline sliders)
    // For now, we will just use the editor bounding vars.
    const payload = {
        filename: editorClipMeta.filename,
        custom_start: secondsToTimestamp(editorStartSecs),
        custom_end: secondsToTimestamp(editorEndSecs),
        custom_crop_x: editorCropXPct
    };

    closeEditor();
    showProgressSection();
    document.querySelectorAll('.pipeline-step').forEach(el => el.classList.remove('active', 'completed', 'error'));
    $progressText.textContent = 'Preparing precision export...';

    try {
        const response = await fetch(`/api/export/${currentJobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error);

        // Start SSE observing the new export_id
        startSSE(data.export_id);

    } catch (err) {
        showError('Export failed: ' + err.message);
    }
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
});
