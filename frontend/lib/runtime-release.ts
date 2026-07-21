export type RuntimeReleaseInfo = {
  release: string;
  environment: string;
  service: string;
};

function firstNonEmpty(values: Array<string | undefined>) {
  return values.find((value) => typeof value === 'string' && value.trim().length > 0)?.trim();
}

export function getRuntimeReleaseInfo(): RuntimeReleaseInfo {
  return {
    release:
      firstNonEmpty([
        process.env.NEXT_PUBLIC_APP_RELEASE,
        process.env.RAILWAY_DEPLOYMENT_ID,
        process.env.VERCEL_GIT_COMMIT_SHA,
        process.env.GITHUB_SHA,
      ]) ?? 'local-dev',
    environment:
      firstNonEmpty([
        process.env.NEXT_PUBLIC_APP_ENV,
        process.env.RAILWAY_ENVIRONMENT_NAME,
        process.env.VERCEL_ENV,
        process.env.NODE_ENV,
      ]) ?? 'development',
    service: firstNonEmpty([process.env.RAILWAY_SERVICE_NAME, process.env.NEXT_PUBLIC_APP_SERVICE]) ?? 'aiclone-frontend',
  };
}
