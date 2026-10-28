# Architecture

## End-to-end flow

```
Factory photo
  └─▶ POST /api/vision/detect           scanning/   ScanPipeline
        decode → ScaleDetector → ReplicateSamSegmenter → MaskFilter
        → ColorAnalyzer + PieceGeometry → MaterialClassifier (vision LLM)
        → WeightEstimator → SortGrouper → AnnotationRenderer
  └─▶ POST /api/lots/from-scan          marketplace/  one scan run plus one lot per bin, priced and credited with impact (valuation/)
Buyer
  └─▶ GET  /api/lots?…                  marketplace/  search, current decayed price
  └─▶ POST /api/lots/{id}/claim         marketplace/  full or partial claim, row-locked
Admin
  └─▶ GET  /api/admin/metrics           admin/      AdminMetricsReport over lots and scan runs
```

The scan pipeline is a single class whose collaborators (segmenter, material classifier, scale detector, and so on) are injected through its constructor. `ScanPipeline.from_settings()` wires the production implementations; tests pass fakes. If no vision LLM answers, `MaterialClassifier` falls back to a color and pattern heuristic, so a scan still completes.

## Backend layout

Each domain package follows the same shape. Not every package needs every file:

| File | Holds |
|---|---|
| `models.py` | SQLAlchemy models declared on `core.database.Base`, plus their lifecycle rules (`Lot.claim`, `Lot.delist`, `Lot.relist`, …) |
| `schemas.py` | Pydantic request and response models |
| `repository.py` | Queries only, with no business rules |
| `service.py` | Use cases that coordinate models and repositories and own the transaction (`commit`) |
| `router.py` | HTTP layer: dependencies, access guards, mapping domain errors to status codes |

Cross-cutting pieces live in `core/`:

- `config.py`: a frozen `Settings` dataclass built from environment variables. Use `get_settings()`; never call `os.getenv` elsewhere.
- `database.py`: the `Database` object (engine and session factory) and the `get_db` request dependency. Postgres in development and production; SQLite when `DATABASE_URL` is unset.
- `schema_upgrades.py`: additive `ALTER TABLE … ADD COLUMN` upgrades that run at startup.
- `security.py`: PBKDF2 password hashing (legacy SHA-256 hashes verify and are upgraded on login) and JWT issuing and verification.
- `openrouter.py`: sync and async OpenRouter clients with typed errors.
- `frontend.py`: serves the built React app from the API when `FRONTEND_DIST_DIR` is set, for single-container deploys.

### Access control

`auth/dependencies.py` exposes `get_current_user` and role guards:

| Guard | Roles |
|---|---|
| `require_operator` | factory, admin |
| `require_admin` | admin |
| `require_purchaser` | buyer, admin |

Attach a guard per route, either `dependencies=[Depends(require_admin)]` or as a parameter when the handler needs the user. Identity always comes from the token, never the request body. For example, a buyer's claim is recorded under their own name whatever `buyer_name` says.

### Adding a domain

1. Create `backend/app/<domain>/` with `__init__.py`, plus `models.py`, `schemas.py`, `service.py`, and `router.py` as needed.
2. Declare models on `core.database.Base`. Importing the router from `main.py` registers them, and `create_all` creates any new tables.
3. Add the router to `ROUTERS` in `app/main.py`.
4. Add a test module under `backend/tests/`. `tests/support.py` provides `ApiHarness`, an isolated database (in-memory SQLite, or Postgres when `TEST_DATABASE_URL` is set) with a factory, admin, and buyer user and a token for each.

## Data model

| Table | Key fields | Notes |
|---|---|---|
| `users` | email, password_hash, role, name, lat/lng | Portal logins. `role` ∈ factory, admin, buyer |
| `buyers` | name, type, location, interested_materials | Marketplace profiles used for buyer matching. Separate from logins |
| `scan_runs` | annotated image, totals, summary JSON | One per photo scanned |
| `lots` | fabric, composition, color, weight, price_usd, impact, status, claimed_by, scan_run_id, origin lat/lng | Status ∈ available, claimed, unlisted. A partial claim splits off a new claimed row |

`lot_key` (`fabric::composition::color`) identifies equivalent material. Every scan creates its own lots; the buyer marketplace groups lots with the same key into one listing, and checkout claims each underlying lot.

## Frontend

- `src/shared/api.js` is the HTTP client; each feature's `api.js` declares its endpoints on top of it. It attaches the bearer token, raises `ApiError` with `.status` and the server's `detail` message, and fires `auth:expired` on a rejected token, which `AuthContext` handles by signing the user out.
- Portal pages are lazy-loaded per route (`app/App.jsx`), so the landing page doesn't download the charting libraries. The supplier map is lazy-loaded again inside the marketplace, so Mapbox only downloads when a buyer opens the map view.
- `ProtectedRoute` gates each portal by role in the UI. The backend enforces the same rules independently.

## Scaling roadmap

The current design is correct at pilot scale. These are the known limits and the planned replacements, roughly in priority order:

| Area | Today | Next step |
|---|---|---|
| Image storage | Piece crops and annotated scans are stored as base64 data URLs in `lots.piece_images` and `scan_runs.annotated_image_data_url` | Upload to object storage (S3 or Supabase Storage) and store URLs. This is the largest contributor to row size and response payloads |
| Scan execution | `/vision/detect` runs SAM and the LLM inline (30–90 s per request) | Move to a job queue (e.g. RQ or Celery), return a job id, and poll or push results |
| Migrations | `SchemaUpgrader` can only add columns | Adopt Alembic for versioned, reversible migrations |
| Orders | A claim marks a lot `claimed_by = <buyer name>`. There is no order or payment entity | Add `orders` and `order_lines` tables keyed by user id. Integrate payments and fulfillment status |
| Listing queries | `GET /lots` returns every match, and price filters use base price | Add cursor pagination. Filter and sort on a computed current-price column |
| Dashboard | `AdminMetricsReport` loads every lot into memory | Compute aggregates in SQL, or keep a materialized summary updated on write |
| Abuse controls | Paid AI endpoints are role-gated but not rate-limited | Per-user rate limits and spend caps on `/vision/detect`, `/vision/scan`, `/destinations/analyze`, `/chat` |
| Impact factors | One global CO₂ and water factor in `ImpactFactors`, used by every backend surface | Per-fiber factors from published LCA data |
| Tokens | 8-hour JWTs in `localStorage` with no refresh or revocation | Short-lived access tokens plus refresh tokens in httpOnly cookies |
