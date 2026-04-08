# A.R.I.A. Frontend

This is the React + Vite municipal review console for A.R.I.A. The source is organized into:

- `src/app/` for the app shell and layout
- `src/features/` for queue, detail, history, and archive screens
- `src/shared/api/` for fetch transport, backend contracts, and mappers
- `src/shared/types/` and `src/shared/lib/` for shared UI contracts and helpers

For the full setup and backend commands, start with the root [`README.md`](../README.md).

## Frontend Quickstart

```bash
npm install
copy .env.example .env.local
npm run dev
```

The Vite dev server runs on `http://localhost:3000` by default.

Set these variables in `.env.local`:

- `VITE_ARIA_API_URL`
- `VITE_ARIA_API_KEY`

The frontend expects the FastAPI backend to be running separately and uses authenticated fetches for queue, detail, upload, and notice access.
