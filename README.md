# Reweave

[![CI](https://github.com/alyfarghali/reweave/actions/workflows/ci.yml/badge.svg)](https://github.com/alyfarghali/reweave/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Live demo: [reweave.alyfarghali.com](https://reweave.alyfarghali.com)** (sign in with a [demo account](#demo-accounts))

Reweave is a B2B marketplace for textile manufacturing byproducts. A factory worker photographs a table of fabric offcuts; computer vision segments every piece, identifies its color and fiber, estimates its weight, and sorts it into bins. Each bin becomes a priced marketplace lot that recyclers and makers can claim. Every listing carries its estimated environmental impact (kilograms diverted from landfill, CO₂ and water saved), so waste becomes a tracked raw-material input instead of a disposal cost.

<p align="center"><img src="docs/media/live-scan.gif" width="320" alt="Factory portal live scan: pieces are outlined, sorted into lettered bins, and listed as lots while totals for weight, value, CO2 and water rise"></p>

<p align="center"><sub>The factory portal's live-scan demo. Its 1,000 pieces are generated, not photographed, but they are listed through the same <code>/api/lots/from-scan</code> endpoint as real scans.</sub></p>

| Buyer marketplace | Admin operations | Impact report |
|---|---|---|
| ![Buyer marketplace with fabric lots, prices per kg and quantity sliders](docs/media/buyer-marketplace.png) | ![Admin dashboard with inventory value, kg diverted, CO2 prevented and the latest scan](docs/media/admin-dashboard.png) | ![Impact page with CO2, water, fabric and energy totals and everyday equivalents](docs/media/admin-impact.png) |

## Engineering highlights

- **Pixels to centimeters.** Every measurement depends on scale, so [`ScaleDetector`](backend/app/scanning/scale.py) tries a printed ArUco marker first, then a marker-like square, a ruler strip, and finally a table-width estimate. Each scan reports which method it used and how confident it is.
- **Cleaning up Segment Anything.** SAM over-segments fabric texture. [`MaskFilter`](backend/app/scanning/mask_filter.py) splits masks into connected components, smooths them, rejects masks for reasons such as size or overlap with the scale marker, and removes duplicates by IoU (0.62) and containment (0.78).
- **A vision LLM that can fail safely.** [`MaterialClassifier`](backend/app/scanning/materials.py) sends the photo plus a contact sheet of piece crops to an ordered list of models. If every model fails, a color and pattern heuristic still finishes the scan.
- **Concurrency-safe partial claims.** A claim locks the lot row (`SELECT … FOR UPDATE`) and splits the claimed weight into a new lot, with price and impact divided proportionally ([`Lot.claim`](backend/app/marketplace/models.py)).
- **Prices that decay without rewriting history.** Only the base price is stored; the markdown is applied when a lot is read ([`PriceDecay`](backend/app/valuation/pricing.py)).
- **A pipeline you can test.** [`ScanPipeline`](backend/app/scanning/pipeline.py) takes its collaborators through its constructor, so the test suite runs it end to end on a synthetic 12-piece scene with SAM and the LLM stubbed out.

The full walkthrough of the scan pipeline is in [docs/pipeline.md](docs/pipeline.md).

## Features

**Factory portal**
- **Scan:** upload or capture a photo of a scrap table. The pipeline returns an annotated sorting plan, per-piece measurements, and sort bins.
- **Live Bins:** a worker-facing view showing which bin each piece goes in.
- **Destination engine:** for each bin, ranks reuse pathways (upcycling, fiber reclamation, insulation, wiping cloths, landfill) by revenue, CO₂ saved, and buyer demand, and suggests matching buyers.

**Buyer portal**
- **Marketplace:** filter lots by fabric, color, and price; full-text search; supplier map with distance and freight estimates; partial-quantity purchases. Equivalent lots from different scans (same fabric, composition, and color) appear as one listing, and checkout claims each underlying lot.
- **My Orders:** claimed lots with an aggregate impact certificate.

**Admin portal**
- **Operations dashboard:** revenue, estimated gross margin (costs are assumed to be 28% of revenue), inventory value, claim rate, scan history, and fabric mix.
- **Impact:** total kg diverted, CO₂ and water saved, with everyday equivalents.
- **Inventory:** delist, relist, or delete lots.
- **Network:** projected impact once the pipeline runs across a full multi-facility supply chain.

**Platform**
- Automatic pricing with time-based markdown (see [Pricing](#pricing)).
- Reweave Assistant: an in-app chatbot that knows the product.
- Role-based access control across all three portals.

## Architecture

```
┌──────────────────────────┐        /api/*        ┌─────────────────────────────────────┐
│  React + Vite SPA        │ ───────────────────▶ │  FastAPI (backend/app)              │
│  factory · buyer · admin │   JWT bearer auth    │  domain packages, SQLAlchemy ORM    │
└──────────────────────────┘                      └───────┬───────────────┬─────────────┘
                                                          │               │
                                            Postgres / SQLite    Replicate (SAM) · OpenRouter (vision LLM, chat)
```

The backend is organized by business domain. Each package owns its models, schemas, service logic, and router:

| Package | Responsibility |
|---|---|
| `scanning/` | Photo → sorted bins: scale detection (ArUco marker or ruler), SAM segmentation, mask filtering, color and pattern analysis, vision-LLM material classification, weight estimation, bin grouping, annotated output |
| `marketplace/` | Lots and scan runs: listing a scan as one lot per bin, partial claims, delist/relist, search |
| `valuation/` | Base-price model, time decay, and CO₂/water/energy factors with everyday equivalents |
| `destinations/` | Buyer profiles, reuse-pathway scoring, and buyer matching |
| `admin/` | Operations dashboard report |
| `auth/` | Users, roles, login, and the `require_*` access guards |
| `assistant/` | Reweave Assistant chat endpoint |
| `core/` | Settings, database, schema upgrades, password and token security, OpenRouter client |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the request flow, data model, conventions for adding a domain, and the scaling roadmap.

## Getting started

### Prerequisites

- Python 3.11 or 3.12 (the pinned NumPy 1.26 has no wheels for 3.13)
- Node.js 18+
- Docker, for the local Postgres database (optional: without it the backend falls back to SQLite)
- API keys for [OpenRouter](https://openrouter.ai) and [Replicate](https://replicate.com) (needed for scanning and the assistant; the marketplace and dashboards work without them)
- Optional: a [Mapbox](https://www.mapbox.com) token for the buyer supplier map

### Backend

```bash
docker compose up -d db              # Postgres 16 on localhost:5433
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # DATABASE_URL already points at the db container; fill in keys and SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

Without Docker, leave `DATABASE_URL` unset and the API uses a SQLite file, `backend/scraps.db`, instead. To move an existing SQLite database into Postgres, run `python scripts/sqlite_to_postgres.py sqlite:///./scraps.db postgresql://reweave:reweave@localhost:5433/reweave` before the API's first start against Postgres. On first start it seeds three demo logins and a catalog of buyer profiles. No inventory is seeded: every lot comes from a scan, either a real photo or the factory portal's synthetic live-scan demo, which uses the same listing endpoint. Interactive API docs are served at <http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env                 # optional: Mapbox token
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api/*` to the backend on port 8000.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Factory | `factory@demo.com` | `factory123` |
| Admin | `admin@demo.com` | `admin123` |
| Buyer | `buyer@demo.com` | `buyer123` |

Set `SEED_DEMO_DATA=false` to skip seeding in shared environments.

### Tests

```bash
cd backend
pip install pytest
python -m pytest                      # in-memory SQLite

# The same suite against Postgres (a dedicated, throwaway database):
docker compose exec db psql -U reweave -c "CREATE DATABASE reweave_test"
TEST_DATABASE_URL=postgresql://reweave:reweave@localhost:5433/reweave_test python -m pytest
```

The suite covers pricing, impact figures, the lot lifecycle (one lot per bin, partial claims), authorization rules, password hashing, serving the built frontend, and the scan pipeline end to end against a synthetic 12-piece scene with stubbed SAM and LLM calls. [CI](.github/workflows/ci.yml) runs it on both SQLite and Postgres, plus the frontend and Docker builds, on every push and pull request.

## Configuration

All backend settings are environment variables, read in `backend/app/core/config.py` and documented in [backend/.env.example](backend/.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./scraps.db` | SQLAlchemy URL. `.env.example` points it at the local Postgres container |
| `SECRET_KEY` | development key | JWT signing key. **Must be set** outside local development |
| `TOKEN_EXPIRE_HOURS` | `8` | Access-token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173`, `http://127.0.0.1:5173` | Comma-separated origins for split-origin deployments |
| `SEED_DEMO_DATA` | `true` | Seed demo logins and buyers into an empty database |
| `FRONTEND_DIST_DIR` | — | Serve the built frontend from the API (set by the Dockerfile) |
| `DISPLAY_TIMEZONE` | `America/New_York` | Timezone for dashboard timestamps |
| `OPENROUTER_API_KEY` | — | Vision material classifier, destination naming, assistant |
| `OPENROUTER_VISION_MODELS` | Gemini 2.5 Flash, Claude Sonnet 4.6, GPT-4o | Ordered fallback list |
| `OPENROUTER_TIMEOUT_S` | `60` | Per-request timeout for OpenRouter calls |
| `REPLICATE_API_TOKEN` | — | SAM segmentation |
| `REPLICATE_SAM_MODEL` | `lucataco/segment-anything-2` | Public SAM model |
| `REPLICATE_DEPLOYMENT` | — | Optional always-warm deployment to avoid cold starts |
| `ARUCO_MARKER_SIZE_CM` / `ARUCO_MARKER_ID` | `5.0` / `23` | Printed scale marker |
| `VISION_MAX_IMAGE_DIMENSION` | `1600` | Longest side, in pixels, of the working copy of each photo |
| `VISION_MAX_PIECES` | `35` | Most pieces kept per scan after mask filtering |

Frontend: `VITE_MAPBOX_TOKEN` in `frontend/.env`.

## API overview

All routes are under `/api`. "Operator" means a factory or admin user.

| Method & path | Access | Description |
|---|---|---|
| `POST /auth/login` | public | Exchange email and password for a bearer token |
| `GET /auth/me`, `PUT /auth/me/location` | signed in | Current user; save the buyer's map location |
| `POST /vision/detect` | operator | Run the scan pipeline on an uploaded photo and return pieces and sort bins |
| `POST /vision/scan` | operator | Scan a photo and list every bin as a lot in one call (used by the [scanning station](station/README.md)) |
| `POST /vision/warmup` | operator | Pre-boot the SAM container in the background |
| `GET /vision/lab`, `GET /vision/aruco-marker` | public | Pipeline test page; printable scale marker |
| `GET /lots` | public | Browse and search inventory (`status`, `fabric_type`, `color_name`, `claimed_by`, `min_price`, `max_price`, `q`) |
| `POST /lots/from-scan` | operator | Record a reviewed scan and list each of its bins as a lot |
| `POST /lots/{id}/claim` | buyer, admin | Claim all or part of a lot (buyers always claim as themselves) |
| `PATCH /lots/{id}/delist`, `/relist`, `DELETE /lots/{id}` | admin | Inventory management |
| `POST /destinations/analyze` | operator | Rank reuse pathways for a bin and match buyers |
| `GET /admin/metrics` | admin | Operations dashboard data |
| `POST /admin/reset-demo` | operator | Delete all lots and scan runs (users and buyers are kept) |
| `POST /chat` | signed in | Reweave Assistant |
| `GET /health` | public | Liveness check |

The running API also serves interactive OpenAPI docs at `/docs`.

## Pricing

Implemented in `backend/app/valuation/pricing.py`. A lot's base price is computed when it is listed, entirely from what the camera measured:

```
base_price = base_per_kg(fabric) × purity × color × weight_tier × piece_tier × weight_kg
```

A lot with any weight and pieces is never priced below $0.01.

**Base price per kg.** The first keyword found in the fabric name, in this order, sets the rate, so "cotton twill" prices as twill and "cotton jersey" as cotton.

| Silk | Wool | Linen | Denim | Twill | Cotton | Jersey | Spandex | Nylon | Polyester | Other |
|---|---|---|---|---|---|---|---|---|---|---|
| $14.00 | $6.50 | $4.50 | $3.80 | $3.50 | $3.20 | $2.80 | $2.20 | $1.80 | $1.20 | $2.00 |

**Multipliers.**

| Factor | Rule | Multiplier |
|---|---|---|
| Purity (dominant fiber %) | ≥95% · 85–94% · 70–84% · <70% · no % given | ×1.20 · ×1.10 · ×1.00 · ×0.85 · ×1.00 |
| Color | white, natural · cream, ivory · beige · grey, black · navy, blue · red, green · yellow · mixed · anything else | ×1.15 · ×1.12 · ×1.10 · ×1.05 · ×1.00 · ×0.97 · ×0.95 · ×0.85 · ×1.00 |
| Weight | ≤1 kg · 1–3 kg · 3–8 kg · 8–15 kg · ≥15 kg | ×1.20 · ×1.10 · ×1.00 · ×0.95 · ×0.88 |
| Pieces | <10 · 10–30 · 31–50 · >50 | ×1.20 · ×1.05 · ×1.00 · ×0.90 |

Unsold lots are marked down at read time, never in storage, so turnover is rewarded without rewriting history:

```
current_price = base_price × max(0.35, e^(−0.015 × max(0, days_listed − 7)))
```

There is a 7-day grace period, then about 1.5% decay per day (a half-life of roughly 46 days), with a floor at 35% of base.

## Environmental impact

Implemented in `backend/app/valuation/impact.py`. Each kilogram diverted from landfill is credited with **2.1 kg CO₂e**, **2,700 L of water** (a cotton-weighted estimate), and **15 kWh** of production energy. Totals are translated into everyday equivalents such as car miles, phone charges, and showers. Every screen that shows impact uses these factors, which live in one dataclass so they can be refined per fiber.

These are estimates in two ways: the weight itself is estimated from the photo (piece area × the fabric density the vision model estimates, falling back to a per-fabric catalog value), and the factors are global averages, not per-fiber life-cycle data.

## Accuracy

Weight and piece-count accuracy against a real scale has **not been measured yet**. The method is ready:

1. Scan a real table, then weigh each resulting bin and count its pieces by hand.
2. Add one row per lot to [docs/evaluation/ground_truth.csv](docs/evaluation/ground_truth.csv) (`lot_id,measured_kg,counted_pieces`).
3. Run `python scripts/evaluate_estimates.py ../docs/evaluation/ground_truth.csv` from `backend/` against the running API. It prints weight error, bias, and piece-count accuracy as Markdown for this section.

## Deployment

The [Dockerfile](Dockerfile) builds the React app and serves it from FastAPI, so the whole product runs as one container behind one URL. `docker compose up --build` runs it locally with its Postgres database on <http://localhost:8000> (set `APP_PORT` to use another port).

The live site runs on a single Ubuntu VM that hosts several portfolio projects ([deploy/](deploy)):

```
GitHub push to main ─▶ CI: tests, frontend build, Docker build
                     ─▶ publish image to ghcr.io/alyfarghali/reweave
                     ─▶ SSH to the VM: docker compose pull + up
VM: Caddy (HTTPS, one subdomain per project) ─▶ reweave container ─▶ reweave-db (Postgres)
```

- [deploy/setup.sh](deploy/setup.sh) prepares a fresh server once: Docker, a firewall allowing only SSH and web traffic, key-only SSH, automatic security updates, a `deploy` user for CI, generated secrets, nightly database backups, and weekly image cleanup.
- [deploy/compose.yml](deploy/compose.yml) and [deploy/Caddyfile](deploy/Caddyfile) define the stack. Caddy obtains and renews certificates on its own.
- The `publish` and `deploy` jobs in [CI](.github/workflows/ci.yml) run only for pushes to `main` after every check passes, and only once the `DEPLOY_HOST` repository variable is set. They need the `DEPLOY_SSH_KEY` and `DEPLOY_KNOWN_HOSTS` secrets.

To run the image on any other container host, set `SECRET_KEY` and a Postgres `DATABASE_URL` (without one the container falls back to a SQLite file, which is lost on restart), plus the AI keys if scans should run. Pass `--build-arg VITE_MAPBOX_TOKEN=...` to enable the supplier map.

## Repository layout

```
backend/
  app/            FastAPI application, one package per domain (see above)
  tests/          pytest suite
  scripts/        ArUco marker generator, estimate-accuracy evaluation, SQLite-to-Postgres copy
frontend/
  src/app/        routing, role guards, lazy-loaded portals
  src/features/   one folder per domain: scanning (factory), marketplace (buyer), admin, auth, assistant, landing, demo
  src/shared/     HTTP client (api.js), formatters, brand assets
station/          Raspberry Pi scanning station (see its README)
docs/             pipeline walkthrough, accuracy evaluation, README media
Dockerfile        single-container build (frontend served by the API)
docker-compose.yml  Postgres for development; the full app with `--build`
deploy/           production stack, server setup script
```

## License

[MIT](LICENSE)
