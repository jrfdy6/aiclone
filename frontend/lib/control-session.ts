const SESSION_COOKIE = 'ai_clone_session';
const SESSION_SECONDS = 60 * 60 * 24 * 7;

function toHex(bytes: ArrayBuffer) {
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function signature(secret: string, expiresAt: string) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  return toHex(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(expiresAt)));
}

function constantTimeTextEqual(left: string, right: string) {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

export async function createSessionValue(secret: string) {
  const expiresAt = String(Math.floor(Date.now() / 1000) + SESSION_SECONDS);
  return `${expiresAt}.${await signature(secret, expiresAt)}`;
}

export async function verifySessionValue(value: string | undefined, secret: string | undefined) {
  if (!value || !secret) return false;
  const [expiresAt, suppliedSignature, extra] = value.split('.');
  if (!expiresAt || !suppliedSignature || extra) return false;
  const parsedExpiry = Number(expiresAt);
  if (!Number.isSafeInteger(parsedExpiry) || parsedExpiry <= Math.floor(Date.now() / 1000)) return false;
  return constantTimeTextEqual(suppliedSignature, await signature(secret, expiresAt));
}

export { SESSION_COOKIE, SESSION_SECONDS };
