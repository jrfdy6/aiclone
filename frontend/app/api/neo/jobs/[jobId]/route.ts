import { NextRequest } from 'next/server';
import { neoBackendFetch, passThrough } from '@/lib/neo-guest-server';

export async function GET(request: NextRequest, context: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await context.params;
  const upstream = await neoBackendFetch(request, `/api/neo/guest/jobs/${encodeURIComponent(jobId)}`);
  return passThrough(upstream);
}
