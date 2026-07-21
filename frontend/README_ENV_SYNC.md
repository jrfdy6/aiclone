# Railway Environment Contract

> Authority: frontend-specific operating note subordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) and [Railway API Usage](../SOPs/railway_api_sop.md).

The frontend is an authenticated private control plane. Browser JavaScript must call protected backend routes through the same-origin `/api/control/**` proxy. The proxy reads `CONTROL_PLANE_SERVICE_TOKEN` only on the Railway server and forwards it as a backend bearer token.

## Required boundaries

- Keep `CONTROL_PLANE_SERVICE_TOKEN`, session secrets, signing secrets, database URLs, service-account blobs, and provider credentials server-only.
- Never expose a bearer token through `NEXT_PUBLIC_*` variables or browser bundles.
- `NEXT_PUBLIC_API_URL` remains a compatibility setting for legacy public/unprotected clients; it is not the authentication path for Ops or Brain.
- Configure variables independently on the Railway frontend and backend services according to which process consumes them.
- Change variables through Railway’s protected environment management, then redeploy and verify; do not copy local secret files into the repository or deployment image.

## Verification

1. Confirm `/login` establishes the signed HTTP-only frontend session.
2. Confirm an authenticated request to `/api/control/api/brain/docs` succeeds.
3. Confirm a signed-out request cannot read private `/ops`, `/brain`, or proxy data.
4. Confirm direct unauthenticated requests to backend `/api` routes are rejected.
5. Run `./scripts/verify_frontend_release.sh` and `./scripts/verify_production.sh` from the repository root.

Do not print environment values during diagnosis. Compare variable names/presence with redacted output and use Railway logs for the specific failing service.
