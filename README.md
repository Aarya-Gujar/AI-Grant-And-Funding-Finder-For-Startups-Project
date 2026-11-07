# AI Grant & Funding Finder for Startups
### AICTE Problem Statement #18

> **Powered by IBM Granite (watsonx.ai) + IBM Cloud Lite** — mandatory as per AICTE guidelines.

---

## 📌 Problem Statement

Developing an AI-based Grant and Funding Finder for startups poses several challenges:

- Funding opportunities are spread across **multiple platforms**, each with different formats, languages, and update frequencies
- Extracting relevant details like eligibility, deadlines, and submission requirements from **unstructured content** demands robust NLP
- **Personalizing results** based on a startup's stage, domain, and location adds another layer of complexity
- Automatically generating tailored **proposals or application drafts** must balance accuracy and creativity
- Ensuring the agent respects **legal boundaries** and submission rules — especially for confidential or restricted portals

---

## 🤖 IBM Technology Stack (Mandatory)

| Technology | Usage |
|---|---|
| **IBM Granite 13B Instruct** (watsonx.ai) | AI-powered grant matching, proposal generation, grant summarisation, eligibility extraction |
| **IBM Cloud Lite** | Free-tier hosting, API key management, secure credential storage |
| **IBM watsonx.ai Platform** | Foundation model inference endpoint for IBM Granite |
| **IBM Watson NLU** | Entity extraction, keyword analysis from raw grant content |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (SPA)                      │
│   HTML + CSS (IBM Design) + Vanilla JS           │
│   Browse Grants / AI Match / Draft Proposal      │
└──────────────────┬──────────────────────────────┘
                   │ REST API (/api/...)
┌──────────────────▼──────────────────────────────┐
│            Flask Backend (Python)                │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Grant Aggregator                         │   │
│  │  • Static curated DB (10 grants)          │   │
│  │  • RSS feed parser (Grants.gov)           │   │
│  │  • Web scraper (Startup India, DST, etc.) │   │
│  │  • JSON cache (data/grants_cache.json)    │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Matching Engine                          │   │
│  │  • TF-IDF cosine similarity (offline)    │   │
│  │  • Rule-based stage/domain/location bonus│   │
│  │  • IBM Granite AI re-ranking (60% blend) │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Proposal Generator                       │   │
│  │  • IBM Granite LLM prompt engineering    │   │
│  │  • Structured section parsing             │   │
│  │  • Template fallback (offline)            │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  IBM Granite AI Service                   │   │
│  │  • ibm-watsonx-ai SDK integration         │   │
│  │  • Stub mode (no API key needed for demo) │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
AICTE-AI Grant And Funding Finder For Startups/
├── app.py                          # Flask WSGI entry point
├── requirements.txt                # Python dependencies
├── .env                            # IBM credentials & config (not committed)
├── env.example                     # .env template
│
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── routes/
│   │   ├── __init__.py
│   │   └── grants.py               # REST API endpoints
│   └── services/
│       ├── __init__.py
│       ├── granite_service.py      # IBM Granite AI integration
│       ├── grant_aggregator.py     # Multi-source grant data aggregation
│       ├── matching_engine.py      # TF-IDF + AI personalised matching
│       └── proposal_generator.py  # AI grant proposal drafting
│
├── static/
│   ├── index.html                  # Single-page frontend
│   ├── css/
│   │   └── style.css               # IBM Design System inspired styles
│   └── js/
│       └── app.js                  # Frontend logic & API calls
│
├── data/
│   └── grants_cache.json           # Auto-generated grant cache
└── logs/
    └── app.log                     # Application logs
```

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- IBM Cloud account (free Lite tier): https://cloud.ibm.com/registration
- IBM watsonx.ai project (free): https://dataplatform.cloud.ibm.com/

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure IBM Credentials
Edit `.env` and fill in your real values:
```env
IBM_API_KEY=your_ibm_cloud_api_key_here
IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com
IBM_PROJECT_ID=your_watsonx_project_id_here
IBM_GRANITE_MODEL_ID=ibm/granite-13b-instruct-v2
```

**How to get IBM credentials:**
1. Sign up at https://cloud.ibm.com (free Lite tier)
2. Create a watsonx.ai service instance
3. Navigate to **Manage → Access (IAM) → API Keys** to create an API key
4. Open watsonx.ai → Create a project → Copy the **Project ID**

### 3. Run the Application
```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/grants` | List/search grants (supports `q`, `domain`, `stage`, `location`, `type`, `page`) |
| `GET` | `/api/grants/<id>` | Get single grant by ID |
| `POST` | `/api/grants/match` | AI-powered grant matching for a startup profile |
| `POST` | `/api/grants/propose` | Generate AI grant proposal |
| `POST` | `/api/grants/summarize` | Summarise raw grant text with IBM Granite |

### Example: AI Match Request
```json
POST /api/grants/match
{
  "startup_profile": {
    "name": "MedAI Solutions",
    "domain": "healthtech",
    "stage": "early-stage",
    "location": "Bangalore, India",
    "problem": "Lack of accessible diagnostic tools in rural India",
    "solution": "AI-powered mobile diagnostic platform using IBM Watson",
    "team_size": "6",
    "keywords": "AI, rural health, diagnostics"
  },
  "use_ai": true,
  "top_n": 10
}
```

### Example: Generate Proposal
```json
POST /api/grants/propose
{
  "startup_profile": { "name": "MedAI Solutions", "domain": "healthtech", ... },
  "grant_id": "dst_nidhi_prayas"
}
```

---

## 🛡️ Features

| Feature | Implementation |
|---|---|
| **Multi-source aggregation** | RSS feeds, web scraping, curated static DB with 10 grants |
| **Real-time search** | Keyword + domain + stage + location filters |
| **AI matching** | TF-IDF + IBM Granite 60/40 hybrid scoring |
| **Proposal generation** | IBM Granite structured prompts → downloadable `.txt` |
| **Grant summarisation** | IBM Granite NLU distills key facts from raw text |
| **Eligibility extraction** | IBM Granite extracts structured JSON from unstructured text |
| **Offline fallback** | Works without IBM API keys (stub mode) for local dev |
| **Cache layer** | 60-min TTL JSON cache — survives restarts |

---

## ⚠️ Disclaimer

This application is for educational and research purposes under AICTE's challenge. Always verify grant details on official portals before submitting any application. AI-generated proposals must be reviewed and validated by a human expert before submission. The application respects public data only and does not attempt to access restricted or confidential portals.

---

## 📄 License

MIT License — developed for AICTE Problem Statement #18.
