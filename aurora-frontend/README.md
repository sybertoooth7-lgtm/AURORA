# AURORA — Space Intelligence Dashboard

Customer-facing frontend for the AURORA Space Intelligence Platform backend:
a public landing page plus the authenticated dashboard. Register/log in,
submit an area of interest, watch it get processed, and see the
satellite-derived NDVI/change-score readout, history, and alerts.

Routing: `/` is the public landing page (no auth), `/login` and `/register`
are the auth pages, and the whole dashboard lives under `/app` (`/app`,
`/app/areas/new`, `/app/areas/:id`) behind `RequireAuth` in `App.tsx`.

## Stack

- React + TypeScript, built with Vite
- Tailwind CSS v4 (CSS-based theme, see `src/index.css` for the design tokens)
- react-router-dom for routing
- react-leaflet + OpenStreetMap tiles for the area map (no API key needed)

## Setup

```bash
npm install
cp .env.example .env.local   # point VITE_API_BASE_URL at your backend if not localhost:8000
npm run dev
```

Requires the AURORA backend running and reachable at `VITE_API_BASE_URL`
(defaults to `http://localhost:8000`). The backend's `CORS_ORIGINS` needs to
include this app's origin — `http://localhost:5173` for the Vite dev server
default — which is already set correctly in the backend's `.env.example`.

The backend also needs its worker process running (`python worker.py`) —
without it, submitted areas will sit at "pending" forever. See the backend
README for the full local setup.

## Structure

```
src/
  lib/
    api.ts       # fetch wrapper + typed endpoints, JWT attached from localStorage
    auth.tsx      # AuthContext -- login/register/logout, decodes the JWT for the session user
    colors.ts     # NDVI/severity -> color mapping, shared by the map and badges
    types.ts       # mirrors backend/app/schemas/*.py -- keep in sync when the API changes
  components/
    Layout.tsx     # sidebar shell (area list + nav) wrapping the authenticated routes
    AreaMap.tsx     # Leaflet map, colors the area circle by its latest NDVI reading
    LocationPicker.tsx # click/drag-to-place map used on the New Area form; syncs with the typed lat/lon fields
  pages/
    LandingPage.tsx      # public marketing page at "/" -- no auth required
    LoginPage.tsx / RegisterPage.tsx
    DashboardPage.tsx   # redirects to the first area, or shows an empty state
    NewAreaPage.tsx      # map picker + form to submit a new area for monitoring
    AreaDetailPage.tsx    # map + telemetry strip + alerts + history, polls while pending/processing
```

## Design notes

The visual language is a field-survey / instrument-panel aesthetic rather
than a generic SaaS dashboard: a cool paper background, Space Grotesk for
headings, IBM Plex Mono for every number/coordinate/timestamp (so they read
like instrument output and line up in a column), and the only saturated
colors on the page are the ones that mean something — the NDVI health scale
(healthy green / stress amber / critical brick) used consistently across the
map, the telemetry strip, alerts, and the history table.

## Not built yet
- `/auth/me` doesn't exist on the backend yet, so the session user's display
  name comes from decoding the JWT client-side rather than a profile fetch
- No password reset / email verification flow
- No address/place search on the map picker (click/drag only -- no
  geocoding lookup, since that needs a separate API key)
