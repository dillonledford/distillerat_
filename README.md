# distillerat_
<img width="1720" height="1210" alt="Image" src="https://github.com/user-attachments/assets/77c28e87-ee67-4999-8720-6ad4abe0601a" />

> Aggregate GitHub and Google Drive activity into AI-powered project briefings.

**Live at [distillerat.com](https://distillerat.com)**

---

## What it does

distillerat_ connects your GitHub repositories and Google Drive folders and uses AI to generate plain-English project briefings — so you always know what changed, without reading through everything yourself.

- **Full Briefing** — detailed summary grouped by project and area of work
- **Quick Summary** — 5–7 bullet points covering only what matters most
- Custom source labels, saved reports, and date range filtering

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask, SQLAlchemy, SQLite |
| Auth | GitHub OAuth, Google OAuth 2.0 (Flask-Dance) |
| APIs | GitHub REST API, GitHub Atom/RSS, Google Drive API v3, Google Docs API v1, Google Picker API |
| AI | Google Gemini API (gemini-2.5-flash, gemini-2.5-flash-lite) |
| Frontend | HTML, CSS, Jinja2 |
| Hosting | Render, Porkbun (distillerat.com) |

---

## Features

- Sign in with GitHub — no password required
- Connect Google Drive folders via Google Picker
- Monitor GitHub repos for releases and commits
- Read Google Docs content and summarize with AI
- Save and revisit reports with source labels and date ranges
- Mobile responsive

---

## Setup

```bash
git clone https://github.com/dillonledford/Aggregator-WebApp.git
cd Aggregator-WebApp
pip install -r requirements.txt
```

Create a `.env` file:

```
FLASK_ENV=development
SECRET_KEY=your_secret_key
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_API_KEY=your_google_api_key
GEMINI_API_KEY=your_gemini_api_key
```

```bash
python gapp.py
```

---

## Notes

Google Drive integration requires OAuth verification. The app is currently in Testing — contact the developer to be added as a test user for full Drive functionality. GitHub integration works for all users without restrictions.

> [!NOTE]
> **Google Sign-In may show an "unverified app" warning.** This is expected — the app requests read-only access to Google Drive and Docs, which triggers Google's verification requirement regardless of whether access is read-only or read/write.
>
> **What the app can do:** View your Drive files and read the contents of your Google Docs.
> **What the app cannot do:** Create, edit, move, delete, download, or share anything.
>
> The relevant scopes are `drive.readonly` and `documents.readonly`
>
> To proceed past the warning: click **Advanced** → **Go to distillerat_ (unsafe)**
>
> Contact [admin@distillerat.com](mailto:admin@distillerat.com) with any questions.

---

Developer's Comment

"I designed a pipeline where GitHub and Google Drive activity feeds into Gemini to generate plain-English briefings. Every integration is load-bearing — remove any one of them and the core function breaks."

---

## License

MIT
