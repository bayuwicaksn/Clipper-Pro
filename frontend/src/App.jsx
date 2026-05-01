import { useState, useEffect } from 'react'
import './index.css'
import EditorLayout from './components/EditorLayout'
import HomeLayout from './components/HomeLayout'
import { Toaster, toast } from 'sonner'

import * as api from './api/client'

function getInitialState() {
  const path = window.location.pathname;
  let jobId = null;
  let clipIdx = 0;

  if (path.startsWith('/project/') && path.includes('/clip/')) {
    const parts = path.split('/');
    let pid = parts[2];
    if (pid && pid.includes('--')) {
      pid = pid.split('--').pop();
    }
    jobId = pid;
    clipIdx = parseInt(parts[4]) || 0;
  } else {
    const params = new URLSearchParams(window.location.search);
    let pid = params.get('project');
    if (pid) {
      if (pid.includes('--')) pid = pid.split('--').pop();
      jobId = pid;
    }
  }
  return { jobId, clipIdx };
}

function App() {
  const initial = getInitialState();
  const [projects, setProjects] = useState([])
  const [currentJobId, setCurrentJobId] = useState(initial.jobId)
  const [activeClipIndex, setActiveClipIndex] = useState(initial.clipIdx)

  const showToast = (message, type = 'info') => {
    if (type === 'success') toast.success(message);
    else if (type === 'error') toast.error(message);
    else toast(message);
  };
  
  const refreshProjects = () => {
    api.fetchProjects()
      .then(data => {
        const sorted = data.sort((a,b) => b.created_timestamp - a.created_timestamp)
        setProjects(sorted)
      })
      .catch(err => console.error("Could not load projects", err))
  };

  useEffect(() => {
    refreshProjects();
  }, [])

  // If a project is selected, check if it's already completed
  const activeProject = projects.find(p => p.id === currentJobId);
  const isProcessing = activeProject && (activeProject.status === 'processing' || activeProject.status === 'queued');

  if (currentJobId && !isProcessing) {
    return (
      <>
        <EditorLayout 
          project={activeProject} 
          initialClipIndex={activeClipIndex}
          onClose={() => {
            setCurrentJobId(null);
            setActiveClipIndex(0);
            const urlSlug = activeProject.slug ? `${activeProject.slug}--${activeProject.id}` : activeProject.id;
            window.history.pushState({}, '', `/project/${encodeURIComponent(urlSlug)}`);
          }} 
          notify={showToast}
        />
        <Toaster theme="dark" position="bottom-right" richColors />
      </>
    );
  }

  return (
    <>
      <HomeLayout 
        projects={projects} 
        initialActiveJobId={currentJobId}
        onOpenProject={(id, clipIdx = 0) => {
          setCurrentJobId(id);
          setActiveClipIndex(clipIdx);
          
          const project = projects.find(p => p.id === id);
          if (project) {
            const urlSlug = project.slug ? `${project.slug}--${project.id}` : project.id;
            window.history.pushState({}, '', `/project/${encodeURIComponent(urlSlug)}/clip/${clipIdx}`);
          } else {
            window.history.pushState({}, '', `/project/${id}/clip/${clipIdx}`);
          }
        }} 
        onRefreshProjects={refreshProjects}
        notify={showToast}
      />
      <Toaster theme="dark" position="bottom-right" richColors />
    </>
  );
}


export default App
