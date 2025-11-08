# YouTube Smart Comment Moderator

YouTube creators can now auto-regulate comments using intelligent, flexible rules. This website uses Sentence Transformers like MiniLM & ChromaDB to detect violations according to rules you define and it can instantly delete offending comments from your channel through secure integration with the YouTube Data API.

---

## Features

- **Custom Rule Editor:** Define your own moderation rules.
- **Bulk Moderation:** Fetch all comments from your videos, check for violations, and see actionable summaries.
- **Direct Deletion:** Delete violating comments from your YouTube channel with a single click or in bulk.
- **Smart Filtering:** Powerful semantic analysis - no need to retrain or update code for new rules.
- **Explained Moderation:** See which rule was triggered and an explaination via Llama model for each flagged comment.
- **Secure:** Sign in with Google; your credentials and tokens are safely managed with OAuth2.

---

## Demo

<img width="1920" height="1020" alt="Screenshot (136)" src="https://github.com/user-attachments/assets/731da485-8af6-45db-b190-212be8d33996" />
<img width="1920" height="1015" alt="Screenshot (137)" src="https://github.com/user-attachments/assets/76ff9cb6-bdb0-425e-b95e-053bce05ba97" />
<img width="1920" height="1019" alt="Screenshot (138)" src="https://github.com/user-attachments/assets/cb07c1ca-986e-4d7d-871a-0797db39bef4" />
<img width="1920" height="1008" alt="Screenshot (139)" src="https://github.com/user-attachments/assets/902c5d6c-cb12-4313-af3d-1fd018acfe3e" />

---

## Table of Contents

- [Setup](#setup)
- [Folder Structure](#folder-structure)
- [YouTube Data API Setup](#youtube-data-api-setup)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Usage](#usage)
- [Security & Permissions](#security--permissions)
- [Contributing](#contributing)
- [License](#license)

---

## Setup

### 1. Prerequisites

- Python 3.8+
- Grok API Key
- Google Cloud Developer account (for API keys)

### 2. Clone & Install

```
git clone https://github.com/KAnanyaK/youtube-comment-moderator.git
cd youtube-comment-moderator/backend
pip install -r requirements.txt
cd ../frontend
```

### 3. API Keys & Environment Variables

- Get `client_secret.json` from [Google Cloud Console](https://console.developers.google.com/)
- Place in `backend/`
- Add your YouTube Data API key and OAuth details to `.env` (see sample below):

```
YOUTUBE_CLIENT_ID=your-client-id
YOUTUBE_CLIENT_SECRET=your-secret
YOUTUBE_REDIRECT_URI=http://localhost:8000/oauth2callback
GROK_API_KEY=your-grok-key
FRONTEND_URL=http://localhost:3000
```

---

## Folder Structure

```
youtube-comment-moderator/
├── backend.py
├── frontend.py
├── requirements.txt
├── .env
└── README.md
```

---

## YouTube Data API Setup

1. Create a project in [Google Cloud Console](https://console.developers.google.com/).
2. Enable **YouTube Data API v3**.
3. Set OAuth2 credentials with the correct redirect URI (matching with your backend).
4. Download `client_secret.json` and configure environment variables.

---

## Architecture

- **Frontend:** Streamlit; interacts with backend via POST requests.
- **Backend:** Flask server exposing endpoints for:
    - Authentication (OAuth2 with YouTube)
    - Fetching video comments
    - Submitting rules for moderation
    - Assessing comments based on set rules
    - Deleting comments directly (YouTube API)
    - Managing user rules (CRUD)
- **ML Modules:**
    - `MiniLM by HuggingFace`: Sentence embedding for rules/comments
    - `ChromaDB`: Similarity searches and vector storage
    - `Llama-3.1-8b-instant by Grok`: Semantic Analysis

---

## How It Works

1. **Authenticate:** Sign in with your Google (YouTube) account—handled via OAuth2.
2. **Set Rules:** Add your moderation rules in the web dashboard.
3. **Import Comments:** Fetch comments from any video/channel of your choice.
4. **AI Moderation:** The backend checks each comment against your rules via semantic similarity.
5. **Review/Moderate:** See flagged comments, understand which rule was triggered, then delete directly from the UI.

---

## Usage

- **Start backend:**
  Open a terminal and execute the following command: 
  `python backend.py` (insert entire file path in place of 'backend.py')
- **Start frontend:**
  Open another terminal and execute the following command:
  `streamlit run frontend.py` 
- **Visit frontend:**  
  Go to `http://localhost:8501`
- **Moderate:**  
  - Authenticate → import comments → run AI filter → view/delete violations.

---

## Security & Permissions

- OAuth2 ensures only channel owners/moderators can delete their own and others' comments.
- Tokens are securely stored and never exposed to third parties.
- All API calls use HTTPS in production.

---

## Contributing

- Fork and submit pull requests!
- Ideas: scheduled auto-moderation, notification emails, multi-language support.

---

## License

Apache License

---
