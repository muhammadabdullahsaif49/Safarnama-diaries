# Docker Deployment: Safarnama Diaries

## Files to copy into the project folder (next to `server.py`)

```
safarnama-diaries/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example      -> copy to ".env" and edit
└── server.py ...
```

Also add `.env` to your `.gitignore` so the password is never pushed to GitHub.

## Run (easiest: Docker Compose)

1. Install Docker Desktop (Windows/Mac) or Docker Engine (Linux).
2. In the project folder, create the `.env` file:

   **Windows (PowerShell):** `copy .env.example .env`
   **Mac / Linux:** `cp .env.example .env`

   Open `.env` and set a strong `ADMIN_PASSWORD`.
3. Build and start:

   ```
   docker compose up -d --build
   ```
4. Open:
   - Website: http://localhost:5000
   - Admin: http://localhost:5000/admin  (user `admin`, password from `.env`)

## Useful commands

| Task | Command |
|---|---|
| See running containers | `docker compose ps` |
| View logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Rebuild after code changes | `docker compose up -d --build` |
| Open a shell inside | `docker compose exec web sh` |
| Check health | `docker inspect --format "{{.State.Health.Status}}" safarnama-diaries` |

## Run without Compose

```
docker build -t safarnama-diaries .
docker run -d --name safarnama-diaries -p 5000:5000 \
  -e ADMIN_PASSWORD="your-strong-password" \
  -v safarnama-data:/data \
  safarnama-diaries
```
(On Windows PowerShell write the command on one line without the `\`.)

## Your data (database and photos)

The database (`safarnama.db`) and uploaded photos are stored in the Docker volume `safarnama-data`, mounted at `/data`. They stay safe when you rebuild or restart the container.

Backup:
```
docker run --rm -v safarnama-data:/data -v "$PWD":/backup alpine tar czf /backup/safarnama-backup.tgz -C /data .
```

`docker compose down -v` **deletes the volume (and all data)**. Use plain `docker compose down` to keep it.

## Deploying on a server (VPS)

1. Install Docker on the server and copy the project (git clone or upload).
2. Create `.env` and run `docker compose up -d --build`.
3. Put a reverse proxy with **HTTPS** in front (Nginx, Caddy or Traefik) and forward to port 5000. The admin password is sent with HTTP Basic Auth, so HTTPS is required on a public site.
4. The app reads the visitor IP from the `X-Forwarded-For` header for rate limiting, so keep the container reachable **only through your proxy** (for example bind to localhost: change the compose port to `"127.0.0.1:5000:5000"`).

## Notes

- Runs with **gunicorn** (1 worker, 4 threads) as a non-root user.
- The rate limiter counts in memory, so keep `--workers 1`. For several workers you would need a shared store such as Redis.
- If the container shows an `unhealthy` status, check `docker compose logs`.
