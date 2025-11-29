/**
 * API Client Utilities
 * 
 * Provides helper functions for API calls and URL configuration
 */

/**
 * Get the API URL from environment variables
 * Falls back to localhost for development
 */
export function getApiUrl(): string | undefined {
  if (typeof window !== 'undefined') {
    // Client-side: use environment variable or default
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }
  // Server-side: use environment variable
  return process.env.NEXT_PUBLIC_API_URL;
}

/**
 * Make a fetch request to the API with error handling
 */
export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const apiUrl = getApiUrl();
  
  if (!apiUrl) {
    throw new Error('NEXT_PUBLIC_API_URL is not configured');
  }

  const url = endpoint.startsWith('http') 
    ? endpoint 
    : `${apiUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, defaultOptions);

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(
      `API request failed: ${response.status} ${response.statusText} - ${errorText}`
    );
  }

  return response;
}

/**
 * Make a GET request and parse JSON response
 */
export async function apiGet<T = any>(endpoint: string): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'GET' });
  return response.json();
}

/**
 * Make a POST request and parse JSON response
 */
export async function apiPost<T = any>(
  endpoint: string,
  data?: any
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
  return response.json();
}

/**
 * Make a PUT request and parse JSON response
 */
export async function apiPut<T = any>(
  endpoint: string,
  data?: any
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
  });
  return response.json();
}

/**
 * Make a DELETE request and parse JSON response
 */
export async function apiDelete<T = any>(endpoint: string): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'DELETE' });
  return response.json();
}
