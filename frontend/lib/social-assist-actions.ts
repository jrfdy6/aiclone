export type AssistedSocialPlatform = 'linkedin' | 'instagram';

const PLATFORM_HOSTS: Record<AssistedSocialPlatform, ReadonlySet<string>> = {
  linkedin: new Set(['linkedin.com', 'www.linkedin.com', 'm.linkedin.com']),
  instagram: new Set(['instagram.com', 'www.instagram.com']),
};

export type SocialBrowserActionDependencies = {
  writeClipboard: (text: string) => Promise<void> | void;
  openWindow: (url: string, target: string, features: string) => unknown;
};

export function validateNativeSocialSurface(platform: AssistedSocialPlatform, nativeUrl: string): string {
  const parsed = new URL(nativeUrl);
  if (
    parsed.protocol !== 'https:'
    || !PLATFORM_HOSTS[platform].has(parsed.hostname.toLowerCase())
    || parsed.username
    || parsed.password
  ) {
    throw new Error(`Native surface URL must belong to ${platform}.`);
  }
  return parsed.toString();
}

export function openNativeSocialSurface(
  platform: AssistedSocialPlatform,
  nativeUrl: string,
  openWindow: SocialBrowserActionDependencies['openWindow'],
) {
  const verifiedUrl = validateNativeSocialSurface(platform, nativeUrl);
  openWindow(verifiedUrl, '_blank', 'noopener,noreferrer');
  return verifiedUrl;
}

export async function copyDraftAndOpenNativeSurface({
  platform,
  nativeUrl,
  draftText,
  dependencies,
}: {
  platform: AssistedSocialPlatform;
  nativeUrl: string;
  draftText: string;
  dependencies: SocialBrowserActionDependencies;
}) {
  if (!draftText.trim()) {
    throw new Error('Prepared draft is empty.');
  }
  const verifiedUrl = validateNativeSocialSurface(platform, nativeUrl);
  const clipboardWrite = Promise.resolve(dependencies.writeClipboard(draftText));
  dependencies.openWindow(verifiedUrl, '_blank', 'noopener,noreferrer');
  await clipboardWrite;
  return {
    copied: true,
    openRequested: true,
    nativeUrl: verifiedUrl,
    externalMutationPerformed: false,
  };
}
