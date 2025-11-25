/**
 * API Client Utilities
 * Handles API URL normalization and common fetch patterns
 */

/**
 * Get the API base URL, ensuring it's a complete absolute URL
 */
export function getApiUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL || '';
  
  if (!url) {
    // Fallback for local development
    if (typeof window !== 'undefined') {
      // Client-side: try to detect if we're in production
      const hostname = window.location.hostname;
      if (hostname.includes('railway.app')) {
        // In production but env var not set - this is a configuration error
        console.error('NEXT_PUBLIC_API_URL is not set! Please configure it in Railway.');
        return '';
      }
    }
    return 'http://localhost:8080';
  }
  
  // Remove trailing slash if present
  const cleanUrl = url.trim().replace(/\/$/, '');
  
  // If URL already has protocol, return as-is
  if (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) {
    return cleanUrl;
  }
  
  // If URL doesn't have protocol, assume https (for production)
  // This handles cases where Railway env var is set without protocol
  return `https://${cleanUrl}`;
}

/**
 * Make a fetch request to the API
 */
export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const apiUrl = getApiUrl();
  const url = endpoint.startsWith('http') 
    ? endpoint 
    : `${apiUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
}

