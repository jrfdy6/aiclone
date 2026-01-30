# Testing (Frontend + API)

This repo doesn’t currently have a single unified automated test suite; most verification is done via:
- **Swagger** (`/api/docs`)
- **curl smoke tests**
- manual UI validation in the Next.js app

### Quick API smoke test (recommended)

1) Ensure backend is running (default):
- `http://localhost:3001`

2) Run:

```bash
./test-phase6-simple.sh
```

By default, the script uses `API_URL=http://localhost:3001`. Override if needed:

```bash
API_URL="http://localhost:8080" ./test-phase6-simple.sh
```

### Manual checks

#### Backend

- **Health**: `GET /health`
- **Docs**: `GET /api/docs`

#### Frontend

- Set `NEXT_PUBLIC_API_URL` to match your backend.
- Open `http://localhost:3000` and confirm:
  - `/prospects` loads (requires Firestore configured)
  - `/knowledge` returns results (requires Firestore + some ingested docs)

