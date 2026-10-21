# Reweave

Reweave is a B2B marketplace for textile manufacturing byproducts. A factory worker photographs a table of fabric offcuts; computer vision segments every piece, identifies its color, fiber, and weight, and sorts it into bins. Each bin becomes a priced marketplace lot that recyclers and makers can claim. Every listing carries measured environmental impact (kilograms diverted from landfill, CO₂ and water saved), so waste becomes a tracked raw-material input instead of a disposal cost.

## Features

**Factory portal**
- **Scan:** upload or capture a photo of a scrap table. The pipeline returns an annotated sorting plan, per-piece measurements, and sort bins.
- **Live Bins:** a worker-facing view showing which bin each piece goes in.
- **Destination engine:** for each bin, ranks reuse pathways (upcycling, fiber reclamation, insulation, wiping cloths, landfill) by revenue, CO₂ saved, and buyer demand, and suggests matching buyers.

**Buyer portal**
- **Marketplace:** filter lots by fabric, color, and price; full-text search; supplier map with distance and freight estimates; partial-quantity purchases.
- **My Orders:** claimed lots with an aggregate impact certificate.

**Admin portal**
- **Operations dashboard:** revenue, gross margin, inventory value, claim rate, scan history, and fabric mix.
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
| `inventory/` | Lots and scan runs: listing, merging matching lots, partial claims, delist/relist, search |
| `marketplace/` | Buyer profiles, recent-deals feed, impact totals |
| `pricing/` | Base-price model and time decay |
| `impact/` | CO₂ and water factors and everyday equivalents |
| `destinations/` | Reuse-pathway scoring and buyer matching |
| `admin/` | Operations dashboard report |
| `auth/` | Users, roles, login, and the `require_*` access guards |
| `assistant/` | Reweave Assistant chat endpoint |
| `core/` | Settings, database, schema upgrades, password and token security, OpenRouter client |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the request flow, data model, conventions for adding a domain, and the scaling roadmap.

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- API keys for [OpenRouter](https://openrouter.ai) and [Replicate](https://replicate.com) (needed for scanning and the assistant; the marketplace and dashboards work without them)
- Optional: a [Mapbox](https://www.mapbox.com) token for the buyer supplier map

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then fill in keys and SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

With no `DATABASE_URL`, the API creates `backend/scraps.db` (SQLite). On first start it seeds three demo logins and a catalog of buyer profiles. There is no sample inventory: every lot comes from a real scan. Interactive API docs are served at <http://localhost:8000/docs>.

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
python -m pytest
```

The suite covers pricing, the lot lifecycle (merging, partial claims), authorization rules, password hashing, and the scan pipeline end to end against a synthetic 12-piece scene with stubbed SAM and LLM calls.

## Configuration

All backend settings are environment variables, read in `backend/app/core/config.py` and documented in [backend/.env.example](backend/.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./scraps.db` | SQLAlchemy URL; use Postgres in production |
| `SECRET_KEY` | development key | JWT signing key. **Must be set** outside local development |
| `TOKEN_EXPIRE_HOURS` | `8` | Access-token lifetime |
| `CORS_ORIGINS` | `localhost:5173` | Comma-separated origins for split-origin deployments |
| `SEED_DEMO_DATA` | `true` | Seed demo logins and buyers into an empty database |
| `DISPLAY_TIMEZONE` | `America/New_York` | Timezone for dashboard timestamps |
| `OPENROUTER_API_KEY` | — | Vision material classifier, destination naming, assistant |
| `OPENROUTER_VISION_MODELS` | Gemini 2.5 Flash, Claude Sonnet 4.6, GPT-4o | Ordered fallback list |
| `REPLICATE_API_TOKEN` | — | SAM segmentation |
| `REPLICATE_SAM_MODEL` | `lucataco/segment-anything-2` | Public SAM model |
| `REPLICATE_DEPLOYMENT` | — | Optional always-warm deployment to avoid cold starts |
| `ARUCO_MARKER_SIZE_CM` / `ARUCO_MARKER_ID` | `5.0` / `23` | Printed scale marker |

Frontend: `VITE_MAPBOX_TOKEN` in `frontend/.env`.

## API overview

All routes are under `/api`. "Operator" means a factory or admin user.

| Method & path | Access | Description |
|---|---|---|
| `POST /auth/login` | public | Exchange email and password for a bearer token |
| `GET /auth/me`, `PUT /auth/me/location` | signed in | Current user; save the buyer's map location |
| `POST /vision/detect` | operator | Run the scan pipeline on an uploaded photo |
| `POST /vision/warmup` | operator | Pre-boot the SAM container in the background |
| `GET /vision/lab`, `GET /vision/aruco-marker` | public | Pipeline test page; printable scale marker |
| `GET /lots`, `GET /lots/{id}`, `GET /lots/filters` | public | Browse and search inventory |
| `POST /lots`, `POST /lots/scan-runs` | operator | List a sorted bin as a lot; record a scan |
| `POST /lots/{id}/claim` | buyer, admin | Claim all or part of a lot (buyers always claim as themselves) |
| `PATCH /lots/{id}/delist`, `/relist`, `DELETE /lots/{id}` | admin | Inventory management |
| `GET /marketplace/buyers`, `GET /marketplace/activity`, `GET /impact` | public | Buyer catalog, recent deals, impact totals |
| `POST /marketplace/buyers` | admin | Add a buyer profile |
| `POST /destinations/analyze` | operator | Rank reuse pathways for a bin |
| `GET /admin/metrics` | admin | Operations dashboard data |
| `POST /admin/reset-demo` | operator | Delete all lots and scan runs (users and buyers are kept) |
| `POST /chat` | signed in | Reweave Assistant |

## Pricing

Implemented in `backend/app/pricing/model.py`. A lot's base price is computed when it is listed, entirely from what the camera measured:

```
base_price = base_per_kg(fabric) × purity × color × weight_tier × piece_count × weight_kg
```

| Fabric | $/kg | | Factor | Rule | Multiplier |
|---|---|---|---|---|---|
| Silk | 14.00 | | Purity | ≥95% single fiber | ×1.20 |
| Wool | 6.50 | | | 85–94% | ×1.10 |
| Linen | 4.50 | | | <70% | ×0.85 |
| Denim | 3.80 | | Color | white / natural | ×1.15 |
| Twill | 3.50 | | | cream / ivory | ×1.12 |
| Cotton | 3.20 | | | mixed | ×0.85 |
| Jersey | 2.80 | | Weight | ≥15 kg | ×0.88 |
| Spandex | 2.20 | | | ≤1 kg | ×1.20 |
| Nylon | 1.80 | | Pieces | <10 | ×1.20 |
| Polyester | 1.20 | | | >50 | ×0.90 |
| Other | 2.00 | | | | |

Unsold lots are marked down at read time, never in storage, so turnover is rewarded without rewriting history:

```
current_price = base_price × max(0.35, e^(−0.015 × max(0, days_listed − 7)))
```

There is a 7-day grace period, then about 1.5% decay per day (a half-life of roughly 46 days), with a floor at 35% of base.

## Environmental impact

Implemented in `backend/app/impact/calculator.py`. Each kilogram diverted from landfill is credited with **2.1 kg CO₂e** and **2,700 L of water** (a cotton-weighted estimate). Totals are translated into everyday equivalents such as car miles, phone charges, and showers. The factors live in one dataclass so they can be refined per fiber.

## Repository layout

```
backend/
  app/            FastAPI application, one package per domain (see above)
  tests/          pytest suite
  scripts/        utilities (printable ArUco marker generator)
frontend/
  src/pages/      factory/, buyer/, admin/ portals plus the landing page
  src/components/ shared UI (chat, lot detail, supplier map, destination analysis)
  src/context/    auth and cart state
  src/api.js      the only module that talks to the backend
arduino-scanner/  experimental fixed-camera capture station (see its README)
```
