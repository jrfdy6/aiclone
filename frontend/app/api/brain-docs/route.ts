import { NextRequest, NextResponse } from 'next/server';
import { readBrainDocContent } from '../../brain/docSources';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function GET(request: NextRequest) {
  const docPath = request.nextUrl.searchParams.get('path') ?? '';
  const doc = readBrainDocContent(docPath);
  if (!doc) {
    return NextResponse.json({ error: 'Document not found' }, { status: 404 });
  }
  return NextResponse.json(doc, {
    headers: {
      'Cache-Control': 'no-store, max-age=0',
    },
  });
}
