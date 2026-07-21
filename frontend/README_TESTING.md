# Frontend Verification

> Authority: frontend-specific procedure subordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) and [Main Safety Release Flow](../SOPs/main_safety_release_sop.md).

## Local checks

```bash
cd frontend
./node_modules/.bin/tsc --noEmit
npm test
npm run build
```

The source-level Node tests are regression coverage, not rendered end-to-end proof. After a UI change, verify the actual authenticated flow in a browser, including loading, empty, degraded, error, and successful states.

## Repository release gate

```bash
./scripts/verify_main.sh
```

Run this from the repository root. It includes documentation authority, backend workspace smoke coverage, persona health, the frontend production build, repo hygiene, and surface-truth checks.

## Production checks

```bash
./scripts/verify_frontend_release.sh
./scripts/verify_production.sh
```

A green build does not prove Railway is serving that build. Verify the deployed release, authenticated same-origin API proxy, and the user-visible route after deployment.
