# Safarnama Diaries: Backend

Flask + SQLite. One command serves the website and saves all form submissions.

## Run (local)

    pip install -r requirements.txt
    # Windows (PowerShell):  $env:ADMIN_PASSWORD="your-strong-password"; python server.py
    # Mac/Linux:             ADMIN_PASSWORD="your-strong-password" python server.py

Open http://127.0.0.1:5000  (site)  and  http://127.0.0.1:5000/admin  (login: `admin` / your password).
Don't open the .html files by double-clicking: forms only work when served by `server.py`.

## What's connected

| Form (page)              | Endpoint            | Saved to table |
|--------------------------|---------------------|----------------|
| Contact & Review         | POST /api/contact    | contacts       |
| Newsletter (home)        | POST /api/newsletter | subscribers    |
| Share Your Story + photo | POST /api/stories    | stories        |

Ticking "email updates" on the contact form also adds the email to subscribers.

## Data
- `data/safarnama.db`: SQLite database. `data/uploads/`: story photos. Back up the `data/` folder.
- Admin page lists everything and exports CSV. Photos open only for the logged-in admin.
- If `ADMIN_PASSWORD` is not set, `/admin` is disabled.

## Security built in
Server-side validation, 5 MB photo limit with real image-type check (JPG/PNG/WebP/GIF), random
file names, per-IP rate limiting, parameterised SQL, escaped admin output, and only `*.html`,
`css/`, `js/`, `images/` are public (never `server.py`, `data/`, or the .docx).

## Going live
Don't use `python server.py` in production. Use a host with Python and run:
`gunicorn -w 2 server:app`, behind HTTPS. Set `ADMIN_PASSWORD` as an environment variable and
keep `data/` on persistent storage. Basic auth over plain HTTP exposes the password, so use HTTPS.

## Not included (ideas for next)
Sending actual emails (newsletter / "story received"), approving stories and showing them on
stories.html automatically, CAPTCHA.
