# AURORA — Space Intelligence Dashboard

Customer-facing frontend for the AURORA Space Intelligence Platform backend.
Register/log in, submit an area of interest, watch it get processed, and
see the satellite-derived NDVI/change-score readout, history, and alerts.

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
  pages/
    LoginPage.tsx / RegisterPage.tsx
    DashboardPage.tsx   # redirects to the first area, or shows an empty state
    NewAreaPage.tsx      # form to submit a new area for monitoring
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

- Public marketing/landing page (this is the authenticated dashboard only)
- `/auth/me` doesn't exist on the backend yet, so the session user's display
  name comes from decoding the JWT client-side rather than a profile fetch
- No password reset / email verification flow
- Map picker for choosing a location by clicking (currently lat/lon typed in)
