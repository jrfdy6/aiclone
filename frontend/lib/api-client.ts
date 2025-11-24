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
      return 'http://localhost:8080';
    }
    return '';
  }
  
  // If URL already has protocol, return as-is
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  
  // If URL doesn't have protocol, assume https
  return `https://${url}`;
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

