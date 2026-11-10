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

For initial setup, set `BOOTSTRAP_ADMIN_USERNAME`,
`BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` as temporary API
service environment variables in Render. The API startup command creates the
platform superuser once, marks it as a platform administrator, and requires a
password change. After the deploy logs confirm creation, remove all three
variables and redeploy; the command will not reset or modify the existing
administrator. Keep the password out of source control and chat.

The API build collects Django static assets for WhiteNoise, including the
ARCADE-themed Django admin login and operations dashboard. Open `/admin/` on
the API service to manage platform accounts and operations.

After migrations complete, the game engine initializes the zero-balance
platform reserve wallet before it starts creating rounds. The engine creates
rounds continuously while it is running; Render's free plan may spin it down
after inactivity. The API uses `GAME_ENGINE_URL` to ping the engine readiness
endpoint when its heartbeat is stale, waking the engine on demand. The client
may briefly show that the engine is starting while a free service wakes and
reinitializes.

The Windows game client checks `/api/devices/client-update/` with its active
device credential. To publish an update, increment `game-client/package.json`,
set `GAME_CLIENT_RELEASE_TAG` in `render.yaml` to the corresponding
`game-client-v<version>` tag, then push that tag. The Windows GitHub Actions
workflow builds and publishes the installer and its SHA-256 manifest, plus an
Android TV APK. The client downloads and verifies the Windows installer through
the manifest, then silently installs and restarts at the next non-running round.

The Windows installer includes and starts the Raw Input mouse bridge locally.
Move each physical mouse once after launching the client to assign its player
slot; the bridge is stopped when the client exits.

The Android APK targets Android TV and Google TV, captures Android mouse device
IDs natively, and assigns each connected physical mouse its own player slot.
Move each mouse once after launch to register it. The APK is debug-signed by
CI; because that signing key is temporary, a later APK may require uninstalling
the earlier version first. APKs are not installable on Tizen or webOS TVs.

The application also accepts `DATABASE_URL` locally; the existing `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` settings remain supported.

### Keeping the Render game engine awake

The backend starts a best-effort keep-alive monitor from its WSGI workers. It
uses the existing `GAME_ENGINE_URL`, checks the engine's `/health/` endpoint
every five minutes, applies short retries with backoff, and coordinates backend
workers using a PostgreSQL advisory lock. No Celery, Redis, or new environment
variables are required. The API's Free instance can also sleep, so this monitor
cannot guarantee the engine stays awake by itself.

Configure an independent external uptime monitor (for example, UptimeRobot) to
send an HTTP GET every five minutes to:

`https://arcade-game-engine.onrender.com/health/`

In UptimeRobot, create an HTTP(s) monitor using that URL and set its monitoring
interval to five minutes. A `200` response indicates the engine web process is
reachable; `/ready/` remains the controller-readiness endpoint. Do not monitor
`/ready/` for the keep-alive check because it reports application readiness
rather than just web-process health.

On Render, keep the engine's existing internal health check path set to
`/health/` and deploy the backend and engine from the updated Blueprint. Render
internal checks are for service health and do not replace the external monitor
on a Free plan. No production database reset or additional service is needed.
After deploying, verify both the external monitor's `200` response and the
engine logs for the controller-start/recovery messages and subsequent rounds.
# arcade
# arcade
