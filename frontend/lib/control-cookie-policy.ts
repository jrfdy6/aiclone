type SessionCookiePolicyInput = {
  nodeEnv?: string;
  localBetaMode?: string;
  allowHttpCookie?: string;
  protocol: string;
  hostname: string;
};

function isPrivateLocalHost(hostname: string) {
  const raw = hostname.trim().toLowerCase();
  const bracketed = raw.match(/^\[([^\]]+)\](?::\d+)?$/);
  const normalized = (bracketed?.[1] ?? (raw.includes(':') && raw.split(':').length === 2
    ? raw.split(':')[0]
    : raw)).replace(/^\[/, '').replace(/\]$/, '');
  if (normalized === 'localhost' || normalized === '::1') return true;
  const octets = normalized.split('.').map(Number);
  if (octets.length !== 4 || octets.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
    return false;
  }
  return octets[0] === 127
    || octets[0] === 10
    || (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31)
    || (octets[0] === 192 && octets[1] === 168)
    || (octets[0] === 169 && octets[1] === 254);
}

export function shouldUseSecureSessionCookie(input: SessionCookiePolicyInput) {
  if (input.nodeEnv !== 'production') return false;
  if (input.protocol === 'https:') return true;
  const explicitLocalHttpBeta = input.localBetaMode === '1'
    && input.allowHttpCookie === '1'
    && input.protocol === 'http:'
    && isPrivateLocalHost(input.hostname);
  return !explicitLocalHttpBeta;
}
