# ClipperApp — Refactor Guide

## ⚠️ KONTEKS PENTING
Ini adalah refactor dari codebase yang sudah berjalan.
SEMUA fitur yang ada harus tetap bekerja setelah refactor.

## Tech Stack
- Backend: FastAPI + SQLModel + SQLite
- Frontend: React 19 + TypeScript + Vite + Tailwind v4
- AI: OpenAI (GPT-4, Whisper, TTS)
- Video: FFmpeg + OpenCV + MediaPipe

## Rules — Backend
- Semua Pydantic models di api/schemas.py
- Semua DB operations di db/crud.py
- Router hanya boleh: validasi input → panggil service → return response
- Business logic di services/, BUKAN di router
- Semua env vars/config di config.py pakai pydantic-settings
- Utils (timestamp, slugify, dll) hanya di utils/helpers.py

## Rules — Frontend  
- Semua API calls di api/client.ts — TIDAK ADA fetch() di component
- Semua types di types/index.ts
- Semua time/timestamp utils di utils/time.ts
- Editor global state pakai Zustand di store/editorStore.ts
- Component tidak boleh punya business logic — hanya render & events

## Yang TIDAK BOLEH diubah saat refactor
- Logic di core/ (pipeline, downloader, dll) — jangan sentuh dulu
- File structure workspace/
- API endpoint URLs (agar tidak break yang sudah jalan)

## Definition of Done per Task
- [ ] Tidak ada TypeScript error (frontend)
- [ ] Tidak ada Python warning/error
- [ ] Fitur yang direfactor masih berjalan sama seperti sebelumnya
- [ ] Tidak ada duplicate code yang tersisa