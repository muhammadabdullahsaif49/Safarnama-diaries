# Safarnama Diaries

A multi-page travel storytelling website about Pakistan. Visitors can read travel stories, explore destinations, browse a photo gallery, and share their own stories, reviews and newsletter signups. A small **Flask + SQLite** backend saves the submissions, and a password-protected admin page shows them.

> *Safarnama* means "travel diary" in Urdu/Persian.

## Features

- **11 pages** with a shared header, navigation and footer: Home, About, Stories, Destinations, Writers, Travel Tips, Share Your Story, Gallery, Events, Contact, Site Map
- **Semantic HTML5** and **responsive CSS3** (Flexbox, Grid, sticky header, hover effects)
- **3 working forms** connected to the backend:
  - Contact and Review
  - Newsletter signup
  - Share Your Story (with photo upload)
- **JavaScript** (`js/forms.js`) sends forms with `fetch()` and shows success or error messages without reloading the page
- **jQuery** category filter on the Gallery page
- **Admin dashboard** (`/admin`) to view all submissions, open uploaded photos and export CSV files
- **Security:** server-side validation, parameterised SQL, rate limiting, safe image upload, restricted static file serving

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3 |
| Client scripting | JavaScript (fetch API), jQuery 3.7.1 |
| Backend | Python 3, Flask (>= 3.0) |
| Database | SQLite 3 |

## Project Structure

```
safarnama-diaries/
├── server.py              # Flask backend (routes, validation, database, admin)
├── requirements.txt       # Python dependency (flask)
├── README-BACKEND.md      # Extra backend and deployment notes
├── index.html ... sitemap.html   # The 11 website pages
├── css/style.css          # Shared stylesheet
├── js/forms.js            # Connects the forms to the API
├── images/                # Local images
└── data/                  # Created automatically on first run (git-ignored)
    ├── safarnama.db       # SQLite database
    └── uploads/           # Uploaded story photos
```

## Getting Started

### Requirements

- Python 3
- pip

### Installation

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
pip install -r requirements.txt
```

### Run

Set an admin password and start the server.

**Windows (PowerShell):**
```powershell
$env:ADMIN_PASSWORD="your-strong-password"; python server.py
```

**macOS / Linux:**
```bash
ADMIN_PASSWORD="your-strong-password" python server.py
```

Then open:

- Website: <http://127.0.0.1:5000>
- Admin dashboard: <http://127.0.0.1:5000/admin> (username `admin`, password = the one you set)

> Do not open the `.html` files by double-clicking them. The forms only work when the pages are served by `server.py`.
> If `ADMIN_PASSWORD` is not set, the admin area is disabled.

## API Endpoints

| Method | Route | Purpose | Saved in |
|---|---|---|---|
| POST | `/api/contact` | Contact message and review | `contacts` |
| POST | `/api/newsletter` | Newsletter subscription | `subscribers` |
| POST | `/api/stories` | Travel story with optional photo | `stories` |
| GET | `/admin` | Admin dashboard (login required) | reads all tables |
| GET | `/admin/export/<table>.csv` | CSV export | - |
| GET | `/admin/uploads/<file>` | View an uploaded photo (admin only) | - |

## Database

SQLite file `data/safarnama.db` with three tables, created automatically on the first run:

- **contacts**: name, email, age, phone, education, profession, heard_from, visit_again, rating, comment, newsletter
- **subscribers**: email (unique), source
- **stories**: name, email, title, destination, travel_date, story, photo, consent

## Security Notes

- All SQL uses parameter placeholders (no SQL injection)
- Per-IP rate limiting on the form endpoints (HTTP 429 when exceeded)
- Uploaded photos: max 5 MB, real image type check (JPG, PNG, WebP, GIF), random file names, not publicly accessible
- Only `*.html` pages and the `css`, `js` and `images` folders are served; `server.py` and `data/` return 404
- Admin uses HTTP Basic Auth with the password from an environment variable

## Deployment

For a live site, use a production server behind HTTPS instead of the Flask development server, for example:

```bash
gunicorn -w 2 server:app
```

Keep the `data/` folder on persistent storage. See `README-BACKEND.md` for more details.



## Author

**Muhammad Abdullah Saif**  
Registration No: INFT231101003  
Course: Web Engineering (INFT-3235)

## License

This project was made for educational purposes as a university course project.
