# arcade

## Deploying on Render and Supabase

The `render.yaml` Blueprint defines a free Render web service for the Django
API, a free static site for the frontend, and a free web service for the game
round controller. Render checks `/health/` to verify the engine process is
serving requests; `/ready/` reports whether Django initialization and database
migrations have completed. The frontend rewrites client-side routes to
`index.html`, so links such as `/login` work on direct visits. Render may spin
down free web services after inactivity, so rounds are not guaranteed to run
continuously.

To deploy:

1. Use the Supabase project's Supavisor **session-pooler** PostgreSQL connection
   string. Do not use transaction-pooler mode: the game engine relies on a
   PostgreSQL advisory lock that must remain on one database session. Render's
   direct connection to Supabase may also be unavailable over IPv4.
2. In Render, create a Blueprint from this repository and select `render.yaml`.
   Enter the same Supabase connection string in both `DATABASE_URL` prompts,
   and set `CORS_ALLOWED_ORIGINS` to the frontend's HTTPS origin (for example,
   `https://arcade-frontend.onrender.com`). Render generates the Django
   `SECRET_KEY`.
3. Wait for the API, engine, and frontend services to finish their initial
   deploys, then open the frontend URL. The engine service applies Django
   migrations before starting the round controller; verify its readiness at
   `/ready/`.

The frontend's `VITE_API_URL` is set to the API service's public URL;
the client adds `/api` when making requests.

The application also accepts `DATABASE_URL` locally; the existing `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` settings remain supported.
# arcade
# arcade
