# Deborasaurus Rex — Backend API

Standalone FastAPI server for the **guestbook**, **mystery fill-in**, and **identity votes** features.
Data is stored in a local SQLite file (`deborasaurus.db`).

---

## Endpoints

| Method | Path          | Description                      |
|--------|---------------|----------------------------------|
| GET    | `/health`     | Health check                     |
| GET    | `/guestbook`  | List all guestbook entries        |
| POST   | `/guestbook`  | Add a guestbook entry             |
| GET    | `/mystery`    | Get all mystery questions + answers |
| POST   | `/mystery`    | Submit an answer                  |
| GET    | `/identity`   | Get identity categories + votes   |
| POST   | `/identity`   | Cast a vote                       |

---

## Deploy to Railway (Recommended)

1. Create a free account at [railway.app](https://railway.app).
2. Create a new project → **Deploy from GitHub repo**.
3. Push this backend folder as its own GitHub repository (or a subfolder).
4. Railway will auto-detect the `Procfile` and start the server.
5. Add environment variables in the Railway dashboard:
   - `CORS_ORIGIN` → your Vercel frontend URL  
     e.g. `https://deborasaurus-rex.vercel.app`
6. Copy the Railway public URL (e.g. `https://deborasaurus-rex-production.up.railway.app`).

> **Note on SQLite persistence on Railway:** Railway's filesystem is ephemeral by default. To persist the database, add a **Volume** in the Railway dashboard mounted at `/app`. Then set `DB_PATH=/app/deborasaurus.db`.

---

## Deploy to Render (Free tier available)

1. Create a free account at [render.com](https://render.com).
2. New → **Web Service** → connect your GitHub repo.
3. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `CORS_ORIGIN` → your Vercel frontend URL
5. Add a **Disk** (under Advanced):
   - Mount path: `/data`
   - Then set env var `DB_PATH=/data/deborasaurus.db`
6. Click Deploy. Copy your Render URL.

---

## Connect the Frontend (Vercel) to this Backend

After deploying the backend and getting its public URL, open **`js/config.js`** in the frontend project and set:

```js
const API_BASE = 'https://your-backend-url.railway.app';
//                 ↑ paste your Railway or Render URL here
```

Then redeploy your Vercel frontend. The guestbook, mystery, and identity features will now work.

---

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open: `http://localhost:8000/docs` (interactive API docs)

For the frontend to talk to this local backend while testing:

```js
// js/config.js
const API_BASE = 'http://localhost:8000';
```

---

## Environment Variables

| Variable      | Default            | Description                          |
|---------------|--------------------|--------------------------------------|
| `CORS_ORIGIN` | `*`                | Frontend URL allowed to call this API |
| `DB_PATH`     | `./deborasaurus.db`| Path to the SQLite database file     |
| `PORT`        | set by platform    | Port the server listens on            |
