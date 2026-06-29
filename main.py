"""
Deborasaurus Rex — Standalone Backend
======================================
FastAPI server for guestbook, mystery fill-in, and identity votes.
Stores data in a local SQLite file (deborasaurus.db).

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Deploy to Railway / Render:
    See README.md
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3, os
from datetime import datetime

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Deborasaurus Rex API")

# ── CORS — allow your Vercel frontend to call this backend ─────────────────────
# Replace the origin below with your actual Vercel URL once deployed.
# You can also set CORS_ORIGIN as an environment variable on Railway/Render.
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ───────────────────────────────────────────────────────────────────
# On Railway/Render the DB lives next to this file.
# Set the DB_PATH env var if you want a different location.
DB_PATH = os.environ.get("DB_PATH", "/data/deborasaurus.db")
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS guestbook (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name  TEXT    NOT NULL,
            message       TEXT    NOT NULL,
            dino_emoji    TEXT    DEFAULT '🦕',
            created_at    TEXT    NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS mystery_answers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question_key  TEXT    NOT NULL,
            answer        TEXT    NOT NULL,
            visitor_name  TEXT,
            created_at    TEXT    NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS identity_votes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            category      TEXT    NOT NULL,
            option_text   TEXT    NOT NULL,
            visitor_name  TEXT,
            created_at    TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

# ══════════════════════════════════════════════════════════════════════════════
#  GUESTBOOK
# ══════════════════════════════════════════════════════════════════════════════
class GuestbookEntry(BaseModel):
    visitor_name: str
    message:      str
    dino_emoji:   Optional[str] = "🦕"

@app.get("/guestbook")
def get_guestbook():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM guestbook ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/guestbook")
def add_guestbook(entry: GuestbookEntry):
    if not entry.visitor_name.strip() or not entry.message.strip():
        raise HTTPException(400, "Name and message required")
    if len(entry.message) > 500:
        raise HTTPException(400, "Message too long (max 500 chars)")
    conn = get_db()
    conn.execute(
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES (?,?,?,?)",
        (
            entry.visitor_name.strip()[:80],
            entry.message.strip(),
            entry.dino_emoji or "🦕",
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════════════════
#  MYSTERY FILL-IN
# ══════════════════════════════════════════════════════════════════════════════
MYSTERY_QUESTIONS = [
    {"key": "superpower", "prompt": "If Kate could have one superpower it would be…"},
    {"key": "snack",      "prompt": "Kate's late-night snack of choice is…"},
    {"key": "villain",    "prompt": "If Kate were a dino villain her name would be…"},
    {"key": "hobby",      "prompt": "Kate's secret hobby no one knows about is…"},
    {"key": "planet",     "prompt": "If Kate ruled a planet it would be called…"},
]

class MysteryAnswer(BaseModel):
    question_key: str
    answer:       str
    visitor_name: Optional[str] = "Anonymous"

@app.get("/mystery")
def get_mystery():
    conn = get_db()
    results = {}
    for q in MYSTERY_QUESTIONS:
        rows = conn.execute(
            "SELECT answer, visitor_name, created_at FROM mystery_answers "
            "WHERE question_key=? ORDER BY created_at DESC LIMIT 20",
            (q["key"],)
        ).fetchall()
        results[q["key"]] = {"prompt": q["prompt"], "answers": [dict(r) for r in rows]}
    conn.close()
    return results

@app.post("/mystery")
def add_mystery(data: MysteryAnswer):
    valid_keys = {q["key"] for q in MYSTERY_QUESTIONS}
    if data.question_key not in valid_keys:
        raise HTTPException(400, "Unknown question")
    if not data.answer.strip():
        raise HTTPException(400, "Answer required")
    conn = get_db()
    conn.execute(
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES (?,?,?,?)",
        (
            data.question_key,
            data.answer.strip()[:200],
            (data.visitor_name or "Anonymous").strip()[:80],
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════════════════
#  IDENTITY VOTES
# ══════════════════════════════════════════════════════════════════════════════
IDENTITY_CATEGORIES = [
    {"key": "vibe",    "label": "Kate's vibe is…"},
    {"key": "era",     "label": "Kate belongs in which era…"},
    {"key": "element", "label": "Kate's element is…"},
]

class IdentityVote(BaseModel):
    category:     str
    option_text:  str
    visitor_name: Optional[str] = "Anonymous"

@app.get("/identity")
def get_identity():
    conn = get_db()
    results = {}
    for cat in IDENTITY_CATEGORIES:
        rows = conn.execute(
            """SELECT option_text, COUNT(*) as votes
               FROM identity_votes WHERE category=?
               GROUP BY option_text ORDER BY votes DESC LIMIT 20""",
            (cat["key"],)
        ).fetchall()
        results[cat["key"]] = {"label": cat["label"], "options": [dict(r) for r in rows]}
    conn.close()
    return results

@app.post("/identity")
def add_identity(data: IdentityVote):
    valid_keys = {c["key"] for c in IDENTITY_CATEGORIES}
    if data.category not in valid_keys:
        raise HTTPException(400, "Unknown category")
    if not data.option_text.strip():
        raise HTTPException(400, "Option required")
    conn = get_db()
    conn.execute(
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES (?,?,?,?)",
        (
            data.category,
            data.option_text.strip()[:100],
            (data.visitor_name or "Anonymous").strip()[:80],
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/admin/import-data")
def import_data():
    conn = get_db()
    statements = [
        # ── GUESTBOOK (21 rows) ──────────────────────────────────────────
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Deborasaurus', 'It has begun 🦕', '🦕', '2026-06-01T11:46:47.093957')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('t', 't', '🦕', '2026-06-01T11:48:48.797962')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Baby mo', 'Hi baby', '🦖', '2026-06-01T11:50:42.538645')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Mael', 'lob na lab kita', '🦖', '2026-06-01T11:55:01.594787')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Cutie', 'Bahala ka diyan', '🦎', '2026-06-01T11:55:18.099205')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Kuyangpinasoksareff', '\"Something\"', '🐉', '2026-06-01T12:00:09.778183')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('may ari ng website', 'kalat nyo guys ha 😃', '🦕', '2026-06-01T12:03:29.882550')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('multo', 'bili ka ng sharmaine', '🐢', '2026-06-01T12:20:27.899018')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Asteroid', 'I''m your worst nightmare', '🦕', '2026-06-01T12:36:33.820979')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('kathryn bernardo×kirby', '67', '🦕', '2026-06-01T12:45:39.909262')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Nomnomdaga...', 'Amacana sa kape!', '🦕', '2026-06-01T12:47:19.526948')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('hibhie', 'misskonasya', '🐉', '2026-06-01T12:47:26.336753')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('mochi', 'kayakakinakainngdagaeh', '🐉', '2026-06-01T12:49:42.373324')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('coffee4layf', 'bawalnapomagcommentyungisangmaypangalanngkuyangbabeldyan', '🐉', '2026-06-01T12:51:14.398204')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('The conjuring', 'Mabisa, Mahusay, very delicate and well balance, epektibo sa lipunan', '🦖', '2026-06-01T19:39:47.806703')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('My preacious 💍', 'Ang Buhay parang kafe, kapag bumagsak Ang ulan bubukas Ang pinto at may magiingay na nazgul...', '🐉', '2026-06-01T19:48:21.270136')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('broken', 'pano po kung hindi ako krux ng krux ko 🥺🥺🥺', '🦕', '2026-06-02T10:23:24.485213')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Jammybear🧸', 'Did you know that water has memory? -olaf⛄', '🐢', '2026-06-07T03:08:22.217090')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('...', '\"CLASSIFIED\"', '🦖', '2026-06-10T19:06:07.217720')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('doi', 'why naman sobrang tagal magsend ng msg sa ig tapos di pa nagana ang fb what is happening????', '🐊', '2026-06-12T14:14:36.159728')",
        "INSERT INTO guestbook (visitor_name, message, dino_emoji, created_at) VALUES ('Oversized toblerone', 'Poems are great!', '🦕', '2026-06-18T19:13:53.852918')",

        # ── MYSTERY ANSWERS (45 rows) ────────────────────────────────────
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Time travel to the Cretaceous period', 'T-Rex', '2026-06-01T11:46:51.653777')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'x', 't', '2026-06-01T11:48:49.019523')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Loving me', 'Visitor', '2026-06-01T11:49:21.506514')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Me', 'Visitor', '2026-06-01T11:49:28.663557')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'My wife', 'Visitor', '2026-06-01T11:49:35.487669')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Loving me', 'Visitor', '2026-06-01T11:49:41.395221')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Our sweet family and home', 'Visitor', '2026-06-01T11:49:50.398418')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to fly one once above the ground', 'Visitor', '2026-06-01T11:50:36.611207')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Inch*', 'Visitor', '2026-06-01T11:51:07.059530')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Over sized tobleron', 'Visitor', '2026-06-01T11:51:27.105848')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Over sized tobleron', 'Visitor', '2026-06-01T11:51:27.105800')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'Katecious-Deborhaptor', 'Visitor', '2026-06-01T12:07:56.526662')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Crying over books', 'Visitor', '2026-06-01T12:09:15.976234')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to read minds but with ads.', 'Visitor', '2026-06-01T12:21:40.064339')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to run fast but with asthma', 'Visitor', '2026-06-01T12:25:17.114936')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Kapeee', 'Visitor', '2026-06-01T12:25:17.137430')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Tobleron under the refrigerator', 'Visitor', '2026-06-01T12:25:59.110686')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Randomly sitting on a long walk', 'Visitor', '2026-06-01T12:26:34.482440')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Little world', 'Visitor', '2026-06-01T12:26:54.073482')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Kapeee', 'Visitor', '2026-06-01T12:27:34.792259')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'Mochi', 'Visitor', '2026-06-01T12:31:03.425986')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'HALFLING.', 'Visitor', '2026-06-01T12:32:30.858594')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'HALFLING.', 'Visitor', '2026-06-01T12:32:44.387199')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to open multiple tabs on your brain...', 'Visitor', '2026-06-01T12:36:50.123165')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to open multiple tabs on your brain...', 'Visitor', '2026-06-01T12:36:50.628111')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to traver your brain across the multiverse...', 'Visitor', '2026-06-01T12:37:40.773526')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to traver your brain across the multiverse...', 'Visitor', '2026-06-01T12:38:01.995143')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to traver your brain across the multiverse...', 'Visitor', '2026-06-01T12:38:01.995222')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Stating at the ceiling for no reason...', 'Visitor', '2026-06-01T12:38:27.274349')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Infantry', 'Visitor', '2026-06-01T12:39:15.445298')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Loading her tabs on her brain', 'Visitor', '2026-06-01T12:43:37.124772')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'buldak', 'Visitor', '2026-06-01T12:46:39.418256')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'endless talk', 'Visitor', '2026-06-01T12:47:04.442914')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'katiesaurus', 'Visitor', '2026-06-01T12:47:15.673841')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Making a joke that has no sense', 'Visitor', '2026-06-01T12:54:19.894655')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Jurassic world...', 'Visitor', '2026-06-01T12:57:00.512511')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Day care center', 'Visitor', '2026-06-01T19:29:13.711767')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('snack', 'Buldak', 'Visitor', '2026-06-01T19:32:18.126796')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('villain', 'Mochi', 'Visitor', '2026-06-01T19:32:36.774425')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Reading books', 'Visitor', '2026-06-01T19:33:00.884607')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('planet', 'Jurassic world', 'Visitor', '2026-06-01T19:33:13.298983')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('superpower', 'Ability to traver your brain across the multiverse', 'Visitor', '2026-06-02T08:35:08.245154')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Mag create ng ganitong bagay (like ano ba itu?)', 'Visitor', '2026-06-07T03:03:03.797097')",
        "INSERT INTO mystery_answers (question_key, answer, visitor_name, created_at) VALUES ('hobby', 'Mag create ng ganitong bagay (like ano ba itu?)', 'Visitor', '2026-06-07T03:03:03.809795')",

        # ── IDENTITY VOTES (23 rows) ─────────────────────────────────────
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', 'Chaotic intellectual', 'Visitor', '2026-06-01T11:46:51.770603')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', 'y', 't', '2026-06-01T11:48:48.899667')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', 'AuHD', 'Visitor', '2026-06-01T11:50:42.521976')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', 'AuHD', 'Visitor', '2026-06-01T11:50:42.538552')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'The beginning of time', 'Visitor', '2026-06-01T11:50:42.538607')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'The beginning of time', 'Visitor', '2026-06-01T11:50:42.737229')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Hurricane', 'Visitor', '2026-06-01T11:58:54.143109')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'The era in the book of Job', 'Visitor', '2026-06-01T11:59:30.092181')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', 'Nerd, messed up...', 'Visitor', '2026-06-01T12:13:03.113559')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Early/late Cretaceous', 'Visitor', '2026-06-01T12:13:19.213790')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Element of surprise', 'Visitor', '2026-06-01T12:13:54.222290')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Pangea...', 'Visitor', '2026-06-01T12:27:19.077710')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Element(ary)', 'Visitor', '2026-06-01T12:27:44.037439')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'New millennium', 'Visitor', '2026-06-01T12:42:07.953816')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Element to be surprised', 'Visitor', '2026-06-01T12:42:09.510703')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Mid tribulation', 'Visitor', '2026-06-01T12:48:14.719061')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Jurassic period', 'Visitor', '2026-06-01T12:56:47.902529')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Middle ages...', 'Visitor', '2026-06-01T13:17:18.859979')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('vibe', '4ft12...', 'Visitor', '2026-06-01T13:17:52.459459')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Hurricane', 'Visitor', '2026-06-01T19:34:50.660449')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('era', 'Fearless era (its fearless😌🫶🏻)-by TS💋', 'Visitor', '2026-06-07T03:05:15.675571')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Elemenowpi', 'Visitor', '2026-06-07T03:05:33.697450')",
        "INSERT INTO identity_votes (category, option_text, visitor_name, created_at) VALUES ('element', 'Burning bush', 'Visitor', '2026-06-18T19:15:02.926639')",
    ]

    imported = 0
    errors = []
    for s in statements:
        try:
            conn.execute(s)
            imported += 1
        except Exception as e:
            errors.append(str(e))

    conn.commit()
    conn.close()
    return {"ok": True, "imported": imported, "errors": errors}
    
