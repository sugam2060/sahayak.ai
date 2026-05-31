import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const normalizedPathname = pathname.endsWith('/') && pathname.length > 1 
    ? pathname.slice(0, -1) 
    : pathname;

  // Define public paths that don't require authentication
  const isPublicPath = 
    normalizedPathname === '/login' || 
    normalizedPathname === '/signup' || 
    normalizedPathname === '/privacy-policy' ||
    normalizedPathname === '/terms-of-service' ||
    pathname.startsWith('/verify/') ||
    pathname.startsWith('/track-your-order/') ||
    pathname.startsWith('/track-your-ticket/') ||
    pathname.startsWith('/api/') || // Allow API routes (though they should have their own auth)
    pathname === '/favicon.ico' ||
    pathname.startsWith('/_next/') ||
    pathname.includes('.'); // Allow files with extensions (images, etc)

  // Get tokens from cookies
  const accessToken = request.cookies.get('access_token')?.value;
  const refreshToken = request.cookies.get('refresh_token')?.value;
  const isAuthenticated = !!(accessToken || refreshToken);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  // 1. If trying to access public path while authenticated, redirect to home
  if (isAuthenticated && (normalizedPathname === '/login' || normalizedPathname === '/signup')) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  // 2. If trying to access private path while NOT authenticated, redirect to login
  if (!isAuthenticated && !isPublicPath) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // 3. If authenticated and accessing private path, verify token with backend
  if (isAuthenticated && !isPublicPath) {
    try {
      const verifyResponse = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          Cookie: request.headers.get('cookie') || ''
        }
      });

      if (!verifyResponse.ok) {
        // Token is invalid or expired
        const response = NextResponse.redirect(new URL('/login', request.url));
        response.cookies.delete('access_token');
        response.cookies.delete('refresh_token');
        return response;
      }

      // If tokens were refreshed by the backend (automatic refresh), 
      // we must propagate the new Set-Cookie headers to the browser.
      const newCookies = verifyResponse.headers.getSetCookie();
      if (newCookies && newCookies.length > 0) {
        const response = NextResponse.next();
        newCookies.forEach(cookie => {
          response.headers.append('Set-Cookie', cookie);
        });
        return response;
      }
    } catch (error) {
      console.error('Auth verification failed (Backend Offline):', error instanceof Error ? error.message : error);
      
      // If the backend is offline or any other network error occurs, 
      // we clear tokens and redirect to login for security.
      const response = NextResponse.redirect(new URL('/login', request.url));
      response.cookies.delete('access_token');
      response.cookies.delete('refresh_token');
      return response;
    }
  }

  return NextResponse.next();
}

// See "Matching Paths" below to learn more
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|logo.png).*)',
  ],
};
