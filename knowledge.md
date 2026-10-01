# Musicia — AI Music Creative Studio

## What It Is

Musicia is a desktop-style creative studio for AI-powered music and voice
production. It has two parts:

- **Frontend** — a React + Vite single-page app with an Electron wrapper,
  Tailwind CSS, and rich interactive UI (sequencer, mixer, voice lab).
- **Backend** — a FastAPI service providing TTS (via `edge-tts`), audio
  mixing (via `pydub`), and a stub `/music/generate` endpoint for future
  MusicGen integration.

## Project Layout

```
.
├── AGENTS.md                 # Project rules, commands, conventions
├── knowledge.md              # This file
├── memory.md                 # Bitácora: decisions, tests, results (dated log)
├── .agents/
│   ├── music-orchestrator.ts # Coordinator agent (spawns the two below)
│   ├── music-composer.ts     # Song specification agent (JSON specs, no prose)
│   ├── audio-engineer.ts     # Real audio synthesis/mix/verify agent
│   └── types/                # AgentDefinition TypeScript types
├── .agents/
│   └── types/                # Agent TypeScript type definitions
├── backend/                  # FastAPI backend (Python)
│   ├── main.py               # App entry point: routes, CORS, Pydantic models
│   ├── tts_service.py        # TTS via edge-tts (Azure neural voices)
│   ├── mixer_service.py      # Audio mixing via pydub
│   └── requirements.txt      # Python dependencies
└── frontend/                 # React + Vite frontend
    ├── package.json
    ├── vite.config.js
    ├── eslint.config.js      # Flat config (ESLint 9)
    ├── index.html
    ├── main.js               # Electron entry point
    ├── tailwind.config.js    # (if present) Tailwind config
    ├── src/
    │   ├── main.jsx          # React DOM mount
    │   ├── App.jsx           # App shell: sidebar, titlebar, tab routing
    │   ├── App.css
    │   ├── index.css         # Tailwind import + custom design tokens
    │   └── components/
    │       ├── Mixer.jsx     # Channel faders, master console
    │       └── Sequencer.jsx # 16-step drum machine via Tone.js
    └── README.md
```

## Commands

### Frontend (in `frontend/`)

| Task      | Command           |
| --------- | ----------------- |
| Install   | `npm install`     |
| Dev       | `npm run dev`     |
| Build     | `npm run build`   |
| Preview   | `npm run preview` |
| Lint      | `npm run lint`    |
| Electron  | `npm run electron`|

### Backend (in `backend/`)

| Task      | Command                                           |
| --------- | ------------------------------------------------- |
| Install   | `pip install -r requirements.txt`                 |
| Run       | `python main.py`  (uvicorn, port 8000)            |

## Conventions & Gotchas

### Styling
- Tailwind CSS utility-first; most classes are applied directly in JSX.
- Custom design tokens are defined as CSS custom properties in `index.css`
  (e.g. `--bg-deep`, `--accent-fluor`, `--accent-purple`, `--glass-blur`).
- `glass-panel`, `border-beam`, `btn-premium`, `label-pro`, `fluor-shadow-*`
  are reusable utility classes for the dark, neon-accented aesthetic.

### Frontend
- React 19 (hooks, JSX in `.jsx`).
- ESLint uses **flat config** (ESLint 9 — `eslint.config.js`).
- `Tone.js` powers the sequencer's audio engine and playback scheduling.
- The Music tab (`/music` route) is currently a placeholder with no
  backend integration yet.

### Backend
- FastAPI with `CORSMiddleware` allowing all origins (`*`).
- Routes:
  - `POST /tts/generate` — text → speech (voice param, defaults to
    `es-ES-AlvaroNeural`).
  - `GET /voices` — list available Azure neural voices.
  - `POST /audio/mix` — mix two audio tracks with individual dB volume offsets.
  - `POST /music/generate` — stub; returns mock success. MusicGen is
    commented out in `requirements.txt` (heavy dependency: torch).
- Audio output files go to an `outputs/` directory (created on demand).
- `loguru` is used for logging across all services.
- Pydantic models define request schemas in `main.py`.

### Gotchas
- CORS is wide open (`allow_origins=["*"]`) — fine for dev, tighten for
  production.
- The `/music/generate` endpoint does **not** actually generate music; it
  returns a success message immediately.
- `pydub` requires `ffmpeg` installed on the system for audio format
  conversions.
- No root-level `package.json` or `tsconfig.json` — the project is split
  into `frontend/` and `backend/` with no monorepo tooling.

## Missing / TODO
- No test files exist in the repository.
- No root-level `README.md`.
- Consider adding: type checking (TypeScript), unit tests, tighter CORS
  policy, actual MusicGen integration.