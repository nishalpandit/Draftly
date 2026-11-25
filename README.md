# Draftly

A lightweight collaborative rich-text document editor built with Django, Bootstrap 5, plain JavaScript, and Quill.

## Project Links

- **Live Application**: https://draftly-ys6e.onrender.com
- **GitHub Repository**: https://github.com/nishalpandit/Draftly

## Features

- **Authentication**: Sign up (with unique email), log in, and log out.
- **Document Dashboard**: View owned documents and documents shared with you, search by title, create new documents, or delete owned documents.
- **Rich-Text Editor & Autosave**: Quill-based editor with debounced CSRF-protected JSON autosave, inline title editing, and server-side HTML sanitization (`bleach` + `tinycss2`).
- **File Import**: Securely import UTF-8 `.txt` and `.md` files (up to 2 MB) directly into sanitized documents.
- **Document Sharing**: Share documents with registered users by email as **Viewer** (read-only) or **Editor** (edit & save), update roles, and revoke access.

## Local Setup

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv env
   # Windows (PowerShell)
   .\env\Scripts\Activate.ps1
   # macOS / Linux
   source env/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply database migrations**:
   ```bash
   python manage.py migrate
   ```

4. **Create a local admin account (optional)**:
   ```bash
   python manage.py createsuperuser
   ```

5. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

6. Open `http://127.0.0.1:8000/` in your browser, register at `/signup/`, and start drafting.

## Running Tests & Checks

```bash
python manage.py check
python manage.py test
```

---

## Deploying to Render

1. **Create a PostgreSQL Database on Render** and copy its **Internal Database URL** (for `DATABASE_URL`).
2. **Create a Web Service on Render** connected to your repository with the following settings:
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput
     ```
   - **Start Command**:
     ```bash
     python manage.py migrate --noinput && gunicorn config.wsgi:application
     ```

3. **Configure Environment Variables in Render**:

   | Variable | Required | Purpose | Example |
   |---|---|---|---|
   | `DJANGO_SECRET_KEY` | Yes | Cryptographic key used for sessions, CSRF, and signing (must not start with `django-insecure-` when `DJANGO_DEBUG=False`) | Output of `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DJANGO_DEBUG` | Yes | Disables debug mode and enables production HTTPS security headers | `False` |
   | `DATABASE_URL` | Yes | PostgreSQL connection URL provided by Render | `postgresql://user:pass@host:5432/dbname` |
   | `DJANGO_ALLOWED_HOSTS` | Recommended | Comma-separated hostnames allowed to serve the app (`RENDER_EXTERNAL_HOSTNAME` is also added automatically) | `your-app.onrender.com` |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | Recommended | Comma-separated HTTPS origins for CSRF verification (`https://<RENDER_EXTERNAL_HOSTNAME>` is also added automatically) | `https://your-app.onrender.com` |
   | `DJANGO_SECURE_SSL_REDIRECT` | Optional | Redirect HTTP to HTTPS (defaults to `True` when `DJANGO_DEBUG=False`) | `True` |
   | `DJANGO_SECURE_HSTS_SECONDS` | Optional | HSTS max-age in seconds (defaults to `31536000`) | `31536000` |

4. **Create the First Admin Account**:
   Open the **Render Shell** for your Web Service and run:
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to set the admin username, email, and password. (Alternatively, set `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` temporarily and run `python manage.py createsuperuser --noinput`.)

---

## Known Limitations

Real-time simultaneous collaborative editing is not currently implemented. Document sharing supports Viewer and Editor permissions.
