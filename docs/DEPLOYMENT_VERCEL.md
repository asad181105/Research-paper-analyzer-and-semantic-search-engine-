# Deploying on Vercel (and where the backend must live)

## Important split

| Component | Vercel? | Why |
|-----------|---------|-----|
| **React frontend** (`frontend/`) | **Yes** | Static Vite build; ideal for Vercel |
| **Flask API + FAISS + embeddings** (`backend/`) | **No** (not as-is) | Needs long-lived process, large RAM, persistent `DATA_DIR`, PyTorch/sentence-transformers |

Deploy the **backend** on Railway, Render, Fly.io, or Docker on a VPS. Point the Vercel frontend at that API.

---

## 1. Deploy backend (example: Railway / Render)

1. Push repo to GitHub.
2. Create a service from `research-paper-engine/backend/Dockerfile` (or `gunicorn`):
   ```bash
   gunicorn -w 1 -b 0.0.0.0:5000 --timeout 120 "run:app"
   ```
   Note: expose `app` from `run.py` — already `app = create_app()`.
3. Set environment variables (see `.env.example`), especially:
   - `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`
   - `DATA_DIR=/data` with a **persistent volume**
   - `SECRET_KEY`
4. Note public URL, e.g. `https://paper-api.up.railway.app`

---

## 2. Deploy frontend on Vercel

1. Vercel project → **Root Directory**: `research-paper-engine/frontend`
2. Framework: **Vite**
3. Build: `npm run build` → Output: `dist`
4. Environment variable:
   ```
   VITE_API_BASE_URL=https://paper-api.up.railway.app/api
   ```
   When set, the UI calls the remote API directly (no proxy).

**Alternative — rewrite proxy** (single domain):

Edit `frontend/vercel.json` and replace `YOUR_BACKEND_HOST`:

```json
"destination": "https://paper-api.up.railway.app/api/$1"
```

Then keep `VITE_API_BASE_URL` unset so the app uses `/api` on the same host.

5. Deploy. Enable **CORS** on Flask (already `flask-cors` on `/api/*`).

---

## 3. Gemini on Vercel

Gemini runs **only on the backend** (summarize, Q&A, compare). Vercel hosts static JS; never put `GEMINI_API_KEY` in `VITE_*` variables.

Backend `.env`:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_from_google_ai_studio
GEMINI_MODEL=gemini-2.0-flash
```

Verify: `GET https://your-api/api/config` → `"configured": true`.

---

## 4. Checklist

- [ ] Backend volume for `DATA_DIR`
- [ ] `VITE_API_BASE_URL` or `vercel.json` rewrites
- [ ] HTTPS on both sides
- [ ] Run `python scripts/seed_demo.py` on the **server** (not locally) for demo data
- [ ] First request may be slow (embedding model download)

---

## 5. What not to do

- Do not deploy Flask + FAISS as a single Vercel Python function (10s timeout, 50MB limit, no local index).
- Do not commit `.env` with API keys.
