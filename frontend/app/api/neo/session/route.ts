import { NextRequest } from 'next/server';
import { neoBackendFetch, passThrough } from '@/lib/neo-guest-server';

export async function GET(request: NextRequest) {
  const upstream = await neoBackendFetch(request, '/api/neo/guest/session');
  return passThrough(upstream);
}
