# 🔍 Secure Cloud Log Analyzer
### CS-508 Cloud Computing — Course Project

A production-grade web application that processes raw Apache/Nginx access logs using a **pure-Python MapReduce pipeline** with parallelism, stores results in **Neon DB (PostgreSQL)**, and enforces **IAM-based access control**.

---

## 🏗️ Architecture

```
Browser → Flask Web Portal → MapReduce Engine (Split→Map→Shuffle→Reduce)
                           → Neon DB (PostgreSQL) — persist results & audit logs
                           → Railway (hosting via GitHub CI/CD)
```

### Components
| Component | Tech |
|---|---|
| Web Framework | Flask 3 |
| MapReduce | Pure Python (ThreadPoolExecutor) |
| Database | Neon DB (serverless PostgreSQL) |
| Auth | Flask-Session + Werkzeug password hashing |
| Hosting | Railway (auto-deploy from GitHub) |
| Secrets | `.env` + Railway environment variables |

---

## 🚀 Local Setup

### 1. Clone & install
```bash
git clone https://github.com/YOUR_USERNAME/cloud-log-analyzer.git
cd cloud-log-analyzer
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your Neon DB URL and a secret key
```

**Get your Neon DB URL:**
1. Go to [neon.tech](https://neon.tech) → create a free project
2. Dashboard → **Connection Details** → copy the `postgresql://...` string
3. Paste it as `DATABASE_URL` in your `.env`

### 3. Run locally
```bash
python start.py
# → http://localhost:5000
```

### 4. Generate a test log file
```bash
python generate_sample_log.py
# → sample_access.log (5000 lines)
```

Default credentials: **admin / admin123**

---

## ☁️ Deploy to Railway (Free)

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/cloud-log-analyzer.git
git push -u origin main
```

### 2. Create Railway project
1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repository → Railway auto-detects `Procfile`

### 3. Add environment variables in Railway
In your Railway project → **Variables** tab, add:
```
DATABASE_URL = postgresql://user:pass@ep-xxxx.neon.tech/neondb?sslmode=require
SECRET_KEY   = your-super-secret-random-key
```

### 4. Deploy
Railway automatically builds and deploys on every push to `main`. Your live URL will be:
`https://your-project-name.up.railway.app`

---

## 🔒 Security Features
- **IAM Simulation**: Username/password login with bcrypt-style hashing (Werkzeug)
- **Session management**: Flask server-side sessions
- **Audit logging**: Every login, logout, and upload is recorded with IP + timestamp
- **Secrets management**: No credentials in source code — all via environment variables
- **`.gitignore`**: `.env` is excluded from version control

---

## 🗺️ MapReduce Pipeline

```
Raw .log file
    │
    ▼ SPLIT
  [chunk_1] [chunk_2] [chunk_3] ... [chunk_N]   ← 500 lines each
    │           │           │
    ▼           ▼           ▼       MAP (parallel threads)
  [(STATUS_404,1),(HOUR_14,1), ...]    ← (key, value) pairs
    │
    ▼ SHUFFLE
  { "STATUS_404": [1,1,1,...], "HOUR_14": [1,1,...] }
    │
    ▼ REDUCE
  { "STATUS_404": 247, "HOUR_14": 832 }
```

**Parallelism**: `concurrent.futures.ThreadPoolExecutor` processes chunks concurrently.

---

## 📁 Project Structure
```
cloud-log-analyzer/
├── app.py                  # Flask app + routes + DB
├── start.py                # Local dev entry point
├── mapreduce/
│   ├── __init__.py
│   └── engine.py           # MapReduce: Split/Map/Shuffle/Reduce
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── result.html
│   ├── history.html
│   └── audit.html
├── generate_sample_log.py  # Test log generator
├── requirements.txt
├── Procfile                # Railway/Render start command
├── railway.toml            # Railway config
├── .env.example            # Template for secrets
├── .gitignore              # Excludes .env from git
└── README.md
```
