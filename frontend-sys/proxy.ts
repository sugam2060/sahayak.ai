import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const normalizedPathname = pathname.endsWith('/') && pathname.length > 1 
    ? pathname.slice(0, -1) 
    : pathname;

  // Check if this is a shared product page route: /[org_slug]/[token]
  const segments = normalizedPathname.split('/').filter(Boolean);
  const isSharedProductPath = segments.length === 2 && ![
    'login', 'signup', 'privacy-policy', 'terms-of-service',
    'verify', 'track-your-order', 'track-your-ticket', 'api',
    'inbox', 'orders', 'ticket', 'products', 'connectors',
    'ai-config', 'team', 'analytics', 'org-settings'
  ].includes(segments[0]);

  // Define public paths that don't require authentication
  const isPublicPath = 
    normalizedPathname === '/login' || 
    normalizedPathname === '/signup' || 
    normalizedPathname === '/privacy-policy' ||
    normalizedPathname === '/terms-of-service' ||
    normalizedPathname.startsWith('/verify/') ||
    normalizedPathname.startsWith('/track-your-order/') ||
    normalizedPathname.startsWith('/track-your-ticket/') ||
    normalizedPathname.startsWith('/api/') || // Allow API routes (though they should have their own auth)
    normalizedPathname === '/favicon.ico' ||
    normalizedPathname.startsWith('/_next/') ||
    normalizedPathname.includes('.') || // Allow files with extensions (images, etc)
    isSharedProductPath;

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

      try {
        const data = await verifyResponse.clone().json();
        const user = data?.user;
        const role = user?.role?.toUpperCase();
        const permissions = user?.permissions || [];

        const routePermissions: { [key: string]: string } = {
          '/inbox': 'chats',
          '/orders': 'orders',
          '/ticket': 'tickets',
          '/products': 'products',
          '/connectors': 'connectors',
          '/ai-config': 'ai_config',
          '/team': 'teams',
          '/analytics': 'analytics',
        };

        if (role !== 'OWNER') {
          if (normalizedPathname === '/org-settings' || normalizedPathname.startsWith('/org-settings/')) {
            const response = NextResponse.redirect(new URL('/', request.url));
            const newCookies = verifyResponse.headers.getSetCookie();
            if (newCookies && newCookies.length > 0) {
              newCookies.forEach(cookie => {
                response.headers.append('Set-Cookie', cookie);
              });
            }
            return response;
          }

          for (const [route, permission] of Object.entries(routePermissions)) {
            if (normalizedPathname === route || normalizedPathname.startsWith(route + '/')) {
              if (!permissions.includes(permission)) {
                const response = NextResponse.redirect(new URL('/', request.url));
                // Propagate any refreshed cookies if present
                const newCookies = verifyResponse.headers.getSetCookie();
                if (newCookies && newCookies.length > 0) {
                  newCookies.forEach(cookie => {
                    response.headers.append('Set-Cookie', cookie);
                  });
                }
                return response;
              }
            }
          }
        }
      } catch (err) {
        console.error('Error parsing user permissions in middleware proxy:', err);
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
