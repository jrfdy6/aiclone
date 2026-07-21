import { NextRequest, NextResponse } from 'next/server';
import { SESSION_COOKIE, verifySessionValue } from '@/lib/control-session';


const PUBLIC_PATHS = new Set(['/login', '/api/auth/login', '/health', '/neo']);
const PUBLIC_PREFIXES = ['/api/neo/'];

export async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (path.startsWith('/neo/')) {
    const neo = request.nextUrl.clone();
    neo.pathname = '/neo';
    return NextResponse.redirect(neo);
  }
  if (PUBLIC_PATHS.has(path) || PUBLIC_PREFIXES.some((prefix) => path.startsWith(prefix))) return NextResponse.next();

  const valid = await verifySessionValue(
    request.cookies.get(SESSION_COOKIE)?.value,
    process.env.CONTROL_PLANE_SESSION_SECRET,
  );
  if (valid) return NextResponse.next();

  if (path.startsWith('/api/')) {
    return NextResponse.json({ status: 'error', message: 'Authentication required.' }, { status: 401 });
  }
  const login = request.nextUrl.clone();
  login.pathname = '/login';
  login.searchParams.set('next', `${path}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt).*)'],
};
