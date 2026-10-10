# 📸 Pictor – Social Media Platform on Microsoft Azure

Pictor is a full-stack social media platform that connects **creators** with **consumers**. It was built with Flask and **deployed and hosted on Microsoft Azure**, using Azure cloud services for hosting, data storage and AI features.

> Developed as MSc coursework at Ulster University.

---

## ☁️ Hosted on Microsoft Azure

The whole application ran in the cloud on Azure. Every part of the system used an Azure service:

| Layer | Azure service | What it did |
|-------|---------------|-------------|
| Web hosting | **Azure App Service** (France Central) | Hosted the Flask app (frontend templates + REST API) |
| Database | **Azure Cosmos DB** (NoSQL API) | Stored users, posts, likes, comments, follows |
| Media storage | **Azure Blob Storage** | Stored uploaded images, served with SAS URLs |
| Image captioning | **Azure AI Vision** (Computer Vision) | Generated captions for uploaded images |
| Sentiment analysis | **Azure AI Language** | Classified comments as positive or negative |
| Translation | **Azure AI Translator** | Translated comments into the user's language |
| Configuration | **App Service Application Settings** | Held all keys and connection strings (no secrets in code) |

**Live deployment URL:** https://pictor-app-byaadwf8awd0ach8.francecentral-01.azurewebsites.net

> ⚠️ The Azure deployment was temporary for assessment and demonstration, so the link may now be offline. A full recorded walkthrough of the hosted app is included in this repo: **`Poudel-E1 Scalable.mp4`**.

### Architecture

```
 Browser
    │  HTTPS
    ▼
 Azure App Service  ──  Flask (app.py) + HTML templates
    │
    ├── Azure Cosmos DB ........ users, posts, comments, likes, follows
    ├── Azure Blob Storage ..... uploaded images
    ├── Azure AI Vision ........ auto image captions
    ├── Azure AI Language ...... comment sentiment
    └── Azure AI Translator .... comment translation
```

---

## ✨ Features

**Consumers**
- Content feed (For You / Following)
- Like, save and comment on posts
- Follow and search creators
- Dark / light theme

**Creators**
- Upload images with AI-generated captions and hashtags
- Edit and delete posts
- View engagement stats (likes, comments, saves)

**AI (Azure)**
- 🤖 Auto image captioning – Azure AI Vision
- 📊 Comment sentiment analysis – Azure AI Language
- 🌐 Comment translation – Azure AI Translator

**Security**
- 🔐 JWT authentication with 24-hour expiry
- 🔒 Role-based access (consumer / creator)
- 🧂 SHA-256 password hashing
- 🗝️ All secrets kept in environment variables / Azure App Settings

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript (Flask templates) |
| Database | Azure Cosmos DB |
| Storage | Azure Blob Storage |
| AI | Azure AI Vision, Language, Translator |
| Auth | JWT (PyJWT) |
| Hosting | Azure App Service |

---

## 🔧 Environment Variables

All keys are read from environment variables. Locally they come from a `.env` file; on Azure they were set in **App Service → Configuration → Application settings**.

Copy `.env.example` to `.env` and replace each `****` with your own values:

```env
COSMOS_CONNECTION_STRING=****
BLOB_CONNECTION_STRING=****
BLOB_CONTAINER_NAME=media
AZURE_SENTIMENT_KEY=****
AZURE_SENTIMENT_ENDPOINT=****
TRANSLATOR_KEY=****
TRANSLATOR_REGION=global
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
CV_KEY=****
CV_ENDPOINT=****
JWT_SECRET_KEY=****
FLASK_ENV=production
PORT=5000
```

> The real `.env` is excluded by `.gitignore` and is never committed.

---

## 🚀 How It Was Deployed to Azure

1. **Created the Azure resources** – App Service (Python), Cosmos DB (NoSQL), Storage account with a `media` container, and AI services (Vision, Language, Translator).
2. **Configured App Settings** – added every variable from `.env.example` under App Service → Configuration → Application settings.
3. **Deployed the code** to App Service with Git:
   ```bash
   git remote add azure https://<app-name>.scm.azurewebsites.net/<app-name>.git
   git push azure main
   ```
4. **Served over HTTPS** on the `*.azurewebsites.net` domain. Flask serves both the HTML and the API from the same origin, so the frontend uses `window.location.origin` and needed no URL changes.

---

## 🏃 Run Locally

```bash
git clone https://github.com/Eru0705/Pictor.git
cd Pictor
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your Azure values
python app.py
```

Open http://127.0.0.1:5000

Generate a JWT secret with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`checking.py` seeds two test users (one consumer, one creator) into Cosmos DB.

---

## 🔄 API Endpoints

| Endpoint | Method | JWT | Role |
|----------|--------|-----|------|
| `/api/login` | POST | ❌ | All |
| `/api/register` | POST | ❌ | All |
| `/api/feed` | GET | ✅ | Consumer |
| `/api/like` | POST | ✅ | Consumer |
| `/api/save` | POST | ✅ | Consumer |
| `/api/follow` | POST | ✅ | Consumer |
| `/api/creator/upload` | POST | ✅ | Creator |
| `/api/creator/posts` | GET | ✅ | Creator |
| `/api/user/profile` | GET | ✅ | Both |
| `/api/user/saved` | GET | ✅ | Consumer |
| `/api/user/liked` | GET | ✅ | Consumer |

---

## 📁 Project Structure

```
Pictor/
├── Templates/                 # Frontend pages
│   ├── login.html
│   ├── consumer.html
│   ├── consumer_registration.html
│   ├── consumer_profile.html
│   ├── consumer_search.html
│   ├── creator.html
│   └── creator_registration.html
├── app.py                     # Flask app + Azure integrations
├── checking.py                # Seeds test users into Cosmos DB
├── requirements.txt
├── .env.example               # Env template (keys masked as ****)
├── Poudel-E1 Scalable.mp4     # Demo video of the Azure-hosted app
└── README.md
```

---

## 👨‍💻 Author

**Eru Poudel** ([@Eru0705](https://github.com/Eru0705)) · MSc Computer Science, Ulster University
