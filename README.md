# arcade

## Deploying on Render and Supabase

The `render.yaml` Blueprint defines a free Render web service for the Django
API, a free static site for the frontend, and a free web service for the game
round controller. The game engine runs alongside a small health endpoint;
Render may spin down free web services after inactivity, so rounds are not
guaranteed to run continuously.

To deploy:

1. Create a Supabase project on the free plan and copy its PostgreSQL connection
   string. Use the Supavisor session-pooler connection string if the direct
   database endpoint is not reachable over IPv4.
2. In Render, create a Blueprint from this repository and select `render.yaml`.
   Enter the same Supabase connection string in both `DATABASE_URL` prompts,
   and set `CORS_ALLOWED_ORIGINS` to the frontend's HTTPS origin (for example,
   `https://arcade-frontend.onrender.com`). Render generates the Django
   `SECRET_KEY`.
3. Wait for the API, engine, and frontend services to finish their initial
   deploys, then open the frontend URL. The engine service applies Django
   migrations before starting the round controller.

The application also accepts `DATABASE_URL` locally; the existing `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` settings remain supported.
# arcade
# arcade
