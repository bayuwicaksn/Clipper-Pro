import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Link2,
  Settings2,
  Play,
  Trash2,
  Clock,
  MapPin,
  ExternalLink,
  Download,
  Brain,
  Scissors,
  Smartphone,
  ChevronDown,
} from "lucide-react";

const API_BASE = "http://127.0.0.1:5000";

function getInitialProjectId() {
  const path = window.location.pathname;
  if (!path.startsWith("/project/") || path.includes("/clip/")) return null;
  const parts = path.split("/");
  let pid = parts[2];
  if (pid && pid.includes("--")) {
    pid = pid.split("--").pop();
  }
  return pid || null;
}

export default function HomeLayout({ 
  projects, 
  onOpenProject, 
  onRefreshProjects, 
  notify, 
  initialActiveJobId 
}) {
  const [url, setUrl] = useState("");

  const [minDuration, setMinDuration] = useState(30);
  const [maxDuration, setMaxDuration] = useState(90);
  const [reframeMode, setReframeMode] = useState("opencv");
  const [ttsVoice, setTtsVoice] = useState("alloy");
  const [aiProvider, setAiProvider] = useState("gpt-5.4-mini");
  const [transcriptionProvider, setTranscriptionProvider] = useState("openai-whisper");

  const [showSettings, setShowSettings] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progressState, setProgressState] = useState(null);

  const [activeJobId, setActiveJobId] = useState(initialActiveJobId || getInitialProjectId());
  const [generatedClips, setGeneratedClips] = useState([]);
  const [resultTab, setResultTab] = useState("all");

  function fetchClips(jobId) {
    fetch(`${API_BASE}/api/clips/${jobId}`)
      .then((res) => res.json())
      .then((data) => setGeneratedClips(data.clips || []))
      .catch(console.error);
  }

  function openProjectOverview(projectId, projectSlug = null) {
    const project = projects.find((p) => p.id === projectId);
    setActiveJobId(projectId);
    
    if (project && (project.status === "processing" || project.status === "queued")) {
      setProcessing(true);
      setProgressState({ step: "download", message: "Reconnecting..." });
      startSSE(projectId);
    } else {
      fetchClips(projectId);
    }

    const urlSlug = projectSlug ? `${projectSlug}--${projectId}` : projectId;
    window.history.pushState({}, "", `/project/${encodeURIComponent(urlSlug)}`);
  }

  function startSSE(jobId) {
    const eventSource = new EventSource(`${API_BASE}/api/progress/${jobId}`);

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setProgressState(data);

      if (data.step === "done") {
        eventSource.close();
        setProcessing(false);
        fetchClips(jobId);
      } else if (data.step === "error") {
        eventSource.close();
        setProcessing(false);
        notify("Error: " + data.message, "error");
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      fetch(`${API_BASE}/api/status/${jobId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.status === "completed") {
            setProcessing(false);
            fetchClips(jobId);
          } else if (data.status === "error") {
            setProcessing(false);
            notify("Job failed: " + (data.error || "Unknown error"), "error");
          } else {
            setTimeout(() => startSSE(jobId), 3000);
          }
        })
        .catch(() => {
          setProcessing(false);
        });
    };
  }

  function startProcessing() {
    if (!url) return notify("Please enter a YouTube URL", "error");
    setProcessing(true);
    setProgressState({ step: "download", message: "Initiating..." });
    setGeneratedClips([]);

    fetch(`${API_BASE}/api/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,

        min_duration: parseInt(minDuration, 10),
        max_duration: parseInt(maxDuration, 10),
        reframe_mode: reframeMode,
        tts_voice: ttsVoice,
        ai_provider: aiProvider,
        transcription_provider: transcriptionProvider,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setActiveJobId(data.job_id);
        startSSE(data.job_id);
      })
      .catch((err) => {
        alert(err.message);
        setProcessing(false);
      });
  }

  useEffect(() => {
    if (activeJobId && !processing && generatedClips.length === 0) {
      fetch(`${API_BASE}/api/status/${activeJobId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.error) {
            fetchClips(activeJobId);
            return;
          }
          if (data.status === "processing" || data.status === "queued") {
            setProcessing(true);
            setProgressState({ step: "download", message: "Reconnecting..." });
            startSSE(activeJobId);
          } else if (data.status === "completed") {
            fetchClips(activeJobId);
          } else if (data.status === "error") {
            notify("Job failed: " + (data.error || "Unknown error"), "error");
            setActiveJobId(null);
          }
        })
        .catch(() => {
          fetchClips(activeJobId);
        });
    }
  }, [activeJobId]);

  const steps = [
    { id: "download", icon: <Download />, label: "Downloading & Extracting Audio" },
    { id: "analyze", icon: <Brain />, label: "AI Analysis & Content Parsing" },
  ];

  function getStepStatus(stepId) {
    if (!progressState) return "";
    
    // Map backend steps to frontend UI steps
    let currentUIId = progressState.step;
    if (currentUIId === "clip" || currentUIId === "finalize") {
      currentUIId = "analyze"; // Group backend finishing steps under AI Analysis visually
    }
    
    const currentIndex = steps.findIndex((s) => s.id === currentUIId);
    const thisIndex = steps.findIndex((s) => s.id === stepId);

    if (progressState.step === "done") return "completed";
    if (progressState.step === "error" && thisIndex === currentIndex) return "error";
    if (thisIndex < currentIndex) return "completed";
    if (thisIndex === currentIndex) return "active";
    return "";
  }

  return (
    <>
      <header className="app-header mb-8">
        <div className="header-content">
          <div className="logo-text">ClipperApp AI</div>
        </div>
      </header>

      <div className="app-main">
        {!processing && !activeJobId && (
          <section className="section section-input">
            <div className="section-glow" />
            <h2 className="section-title">Turn long videos into viral shorts</h2>
            <p className="section-subtitle">AI-powered tracking, auto-captions, and perfect reframing.</p>

            <div className="input-group">
              <div className="flex items-center gap-2 rounded-xl border border-input bg-background p-1 transition-all focus-within:ring-2 focus-within:ring-ring/40">
                <Link2 className="ml-3 text-muted-foreground" />
                <Input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="h-12 flex-1 border-none bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
                />
                <Button onClick={startProcessing} className="h-10 rounded-lg px-6 font-bold">
                  Process
                </Button>
              </div>
            </div>

            <Button
              variant="ghost"
              className="mt-4 border border-border"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Settings2 data-icon="inline-start" />
              <span>Settings</span>
              <ChevronDown
                data-icon="inline-end"
                className={`transition-transform duration-200 ${showSettings ? "rotate-180" : ""}`}
              />
            </Button>

            {showSettings && (
              <div className="settings-panel open">
                <div className="settings-grid">

                  <div className="setting-card">
                    <label className="setting-label">Min Duration (sec)</label>
                    <div className="setting-control">
                      <input
                        type="range"
                        min="15"
                        max="60"
                        step="5"
                        value={minDuration}
                        onChange={(e) => setMinDuration(e.target.value)}
                      />
                      <span className="range-value">{minDuration}</span>
                    </div>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">Max Duration (sec)</label>
                    <div className="setting-control">
                      <input
                        type="range"
                        min="30"
                        max="180"
                        step="10"
                        value={maxDuration}
                        onChange={(e) => setMaxDuration(e.target.value)}
                      />
                      <span className="range-value">{maxDuration}</span>
                    </div>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">AI Provider</label>
                    <select
                      className="setting-select"
                      value={aiProvider}
                      onChange={(e) => setAiProvider(e.target.value)}
                    >
                      <option value="gpt-5.4">OpenAI (GPT-5.4)</option>
                      <option value="gpt-5.4-mini">OpenAI (GPT-5.4 mini)</option>
                      <option value="gpt-5.4-nano">OpenAI (GPT-5.4 nano)</option>
                      <option value="gemini-1.5-flash">Google (Gemini 1.5 Flash)</option>
                      <option value="gemini-1.5-pro">Google (Gemini 1.5 Pro)</option>
                    </select>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">YouTube Auth</label>
                    <label 
                      className="generate-btn" 
                      style={{ display: 'inline-block', textAlign: 'center', cursor: 'pointer', padding: '10px 15px', marginTop: '5px' }}
                    >
                      Update Cookies (.txt)
                      <input 
                        type="file" 
                        accept=".txt" 
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          const file = e.target.files[0];
                          if (file) {
                            const formData = new FormData();
                            formData.append('file', file);
                            fetch('http://127.0.0.1:5000/api/upload-cookies', {
                              method: 'POST',
                              body: formData,
                            })
                            .then(res => res.json())
                            .then(data => alert(data.message || 'Error uploading cookies'))
                            .catch(err => alert('Failed to upload cookies'));
                          }
                        }}
                      />
                    </label>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">Reframe Mode</label>
                    <select
                      className="setting-select"
                      value={reframeMode}
                      onChange={(e) => setReframeMode(e.target.value)}
                    >
                      <option value="opencv">OpenCV (Fast)</option>
                      <option value="mediapipe">MediaPipe (Smart)</option>
                    </select>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">Transcription</label>
                    <select
                      className="setting-select"
                      value={transcriptionProvider}
                      onChange={(e) => setTranscriptionProvider(e.target.value)}
                    >
                      <option value="openai-whisper">OpenAI Whisper (Fast API)</option>
                      <option value="gpt-4o-audio">GPT-4o Audio (Multimodal - Experimental)</option>
                      <option value="local-whisper">Local Whisper (Slow/Private)</option>
                    </select>
                  </div>
                  <div className="setting-card">
                    <label className="setting-label">TTS Voice</label>
                    <select
                      className="setting-select"
                      value={ttsVoice}
                      onChange={(e) => setTtsVoice(e.target.value)}
                    >
                      <option value="alloy">Alloy</option>
                      <option value="echo">Echo</option>
                      <option value="fable">Fable</option>
                      <option value="onyx">Onyx</option>
                      <option value="nova">Nova</option>
                      <option value="shimmer">Shimmer</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {processing && (
          <section className="section section-progress">
            <h2 className="section-title">
              <span className="title-icon">⚡</span> Processing Pipeline
            </h2>

            <div className="pipeline-steps">
              {steps.map((s) => {
                const status = getStepStatus(s.id);
                return (
                  <div key={s.id} className={`pipeline-step ${status}`}>
                    <div className="step-icon">{s.icon}</div>
                    <div className="step-info">
                      <div className="step-name">{s.label}</div>
                      {progressState?.step === s.id && <div className="step-detail">{progressState.message}</div>}
                    </div>
                    <div className="step-status">
                      <span className="step-badge">{status || "Waiting"}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {progressState?.progress > 0 && (
              <div className="progress-bar-container">
                <div className="progress-bar" style={{ width: `${progressState.progress}%` }} />
              </div>
            )}
          </section>
        )}

        {!processing && activeJobId && (
          <section className="section section-results">
            <div className="mb-6 flex items-center justify-between gap-3">
              <h2 className="section-title mb-0">
                <span className="title-icon">🎬</span>{" "}
                {generatedClips.length > 0 ? "Project Clips" : "Loading Clips..."}
              </h2>
              <Button
                variant="secondary"
                onClick={() => {
                  setActiveJobId(null);
                  setGeneratedClips([]);
                  setResultTab("all");
                  window.history.pushState({}, "", "/");
                }}
              >
                Back to Library
              </Button>
            </div>

            {generatedClips.length > 0 && (
              <div className="mb-6 flex items-center gap-2">
                <Button
                  variant={resultTab === "all" ? "default" : "secondary"}
                  onClick={() => setResultTab("all")}
                >
                  All Clips ({generatedClips.length})
                </Button>
                <Button
                  variant={resultTab === "exports" ? "default" : "secondary"}
                  onClick={() => setResultTab("exports")}
                >
                  Exports ({generatedClips.reduce((sum, c) => sum + (c.exports?.length || 0), 0)})
                </Button>
              </div>
            )}

            {resultTab === "all" && (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                {generatedClips.map((clip, idx) => (
                  <Card
                    key={idx}
                    className="group flex cursor-pointer flex-col overflow-hidden border-border/40 transition-all hover:border-primary/50"
                  >
                    <div className="relative aspect-video overflow-hidden bg-black" onClick={() => onOpenProject(activeJobId, idx)}>
                      <img
                        src={`${API_BASE}/api/thumbnail/${activeJobId}/${idx}`}
                        alt={clip.title}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        onError={(e) => {
                          e.target.style.display = "none";
                        }}
                      />
                      <Badge variant="secondary" className="absolute bottom-3 left-3 bg-black/80 font-mono">
                        <Clock className="mr-1 size-3" /> {clip.duration_display || "--:--"}
                      </Badge>
                      <div className="absolute inset-0 bg-black/20 transition-colors group-hover:bg-black/0" />
                    </div>

                    <CardHeader className="p-5 pb-2">
                      <CardTitle className="line-clamp-1 text-base">{clip.title || `Clip ${idx + 1}`}</CardTitle>
                      <CardDescription className="flex items-center text-xs">
                        <MapPin className="mr-1 size-3" /> {clip.start_time} → {clip.end_time}
                      </CardDescription>
                    </CardHeader>

                    <CardFooter className="mt-auto flex gap-2 p-5 pt-0">
                      <Button onClick={() => onOpenProject(activeJobId, idx)} className="flex-1 font-bold">
                        <Play data-icon="inline-start" /> Open in NLE
                      </Button>
                      {clip.exported && (
                        <Button variant="secondary" size="icon" asChild>
                          <a href={`${API_BASE}/api/download/${activeJobId}/${clip.filename}`} download>
                            <ExternalLink />
                          </a>
                        </Button>
                      )}
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}

            {resultTab === "exports" && (
              <div>
                {generatedClips.reduce((sum, c) => sum + (c.exports?.length || 0), 0) === 0 ? (
                  <Card className="mx-auto max-w-xl">
                    <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
                      <div className="text-4xl">📦</div>
                      <p className="text-lg font-semibold text-foreground">No exports yet</p>
                      <p className="max-w-md text-sm text-muted-foreground">
                        Open a clip in the NLE editor and click Export to render your first video.
                      </p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="clips-grid">
                    {generatedClips.flatMap((clip, clipIdx) =>
                      (clip.exports || []).map((exp, expIdx) => (
                        <Card key={`${clipIdx}-${expIdx}`} className="clip-card overflow-hidden">
                          <div className="clip-preview relative flex h-[360px] items-center justify-center overflow-hidden bg-black">
                            <video
                              src={`${API_BASE}/api/preview/${activeJobId}/${exp.filename}`}
                              className="h-full w-auto object-contain"
                              controls
                              playsInline
                            />
                          </div>
                          <CardContent className="p-5">
                            <CardTitle className="mb-2 text-base">
                              {clip.title || `Clip ${clipIdx + 1}`}{" "}
                              {exp.version_label && (
                                <span className="ml-2 text-xs text-muted-foreground">({exp.version_label})</span>
                              )}
                            </CardTitle>
                            <CardDescription className="mb-4 text-xs">
                              ⏱ {clip.duration_display} · {clip.start_time} → {clip.end_time}
                            </CardDescription>
                            <div className="flex items-center gap-2">
                              <Button variant="outline" onClick={() => onOpenProject(activeJobId, clipIdx)}>
                                Re-edit
                              </Button>
                              <Button asChild variant="secondary" className="flex-1">
                                <a href={`${API_BASE}/api/download/${activeJobId}/${exp.filename}`} download>
                                  Download
                                </a>
                              </Button>
                              <Button
                                variant="destructive"
                                size="icon"
                                onClick={() => {
                                  if (!confirm(`Delete "${exp.version_label || exp.filename}"?`)) return;
                                  fetch(`${API_BASE}/api/export/${activeJobId}/${exp.filename}`, { method: "DELETE" })
                                    .then((r) => r.json())
                                    .then((data) => {
                                      if (data.status === "deleted") {
                                        fetchClips(activeJobId);
                                      } else {
                                        alert(data.error || "Failed to delete");
                                      }
                                    })
                                    .catch(() => alert("Network error"));
                                }}
                              >
                                <Trash2 />
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {!processing && !activeJobId && (
          <section className="mt-16 border-t border-border/50 pt-16">
            <div className="mb-8 flex items-center justify-between">
              <h2 className="text-2xl font-bold tracking-tight">Past Projects</h2>
              <Button variant="outline" size="sm" onClick={onRefreshProjects}>
                Refresh Library
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {projects.map((proj) => (
                <Card
                  key={proj.id}
                  className={`group relative cursor-pointer overflow-hidden border-border/40 transition-all hover:border-primary/50 ${proj.status === 'processing' ? 'opacity-80' : ''}`}
                >
                  {proj.status === 'processing' && (
                    <div className="absolute top-2 left-2 z-10">
                      <Badge className="bg-orange-600 animate-pulse">
                        Processing...
                      </Badge>
                    </div>
                  )}
                  <div
                    className="relative aspect-video overflow-hidden bg-black"
                    onClick={() => openProjectOverview(proj.id, proj.slug)}
                  >
                    <img
                      src={proj.thumbnail || "https://via.placeholder.com/320x180?text=No+Thumbnail"}
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                      alt="Thumbnail"
                    />
                    <Badge variant="secondary" className="absolute bottom-3 right-3 bg-black/80">
                      {proj.clip_count} Clips
                    </Badge>
                  </div>

                  <CardHeader className="p-5 pb-2" onClick={() => openProjectOverview(proj.id, proj.slug)}>
                    <CardTitle className="line-clamp-1 text-base">{proj.title || "Untitled Video"}</CardTitle>
                    {proj.created_at && (
                      <CardDescription>
                        {new Date(proj.created_at).toLocaleDateString(undefined, {
                          month: "long",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </CardDescription>
                    )}
                  </CardHeader>

                  <CardContent className="p-5 pt-0" onClick={() => openProjectOverview(proj.id, proj.slug)}>
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">ID: {proj.id}</p>
                  </CardContent>

                  <Button
                    variant="destructive"
                    size="icon"
                    className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!confirm(`Delete "${proj.title || proj.id}"? This cannot be undone.`)) return;
                      fetch(`${API_BASE}/api/projects/${proj.id}`, { method: "DELETE" })
                        .then((res) => res.json())
                        .then((data) => {
                          if (data.error) throw new Error(data.error);
                          notify("Project deleted", "success");
                          if (onRefreshProjects) onRefreshProjects();
                        })
                        .catch((err) => notify("Delete failed: " + err.message, "error"));
                    }}
                  >
                    <Trash2 />
                  </Button>
                </Card>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
