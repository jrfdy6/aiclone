import { NextRequest } from 'next/server';
import { neoBackendFetch, passThrough } from '@/lib/neo-guest-server';

export async function POST(request: NextRequest) {
  const upstream = await neoBackendFetch(request, '/api/neo/guest/v2/meeting-requests', { method: 'POST', body: await request.text() });
  return passThrough(upstream);
}
