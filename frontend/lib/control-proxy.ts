export function isSupportedControlProxyRequest(path: string, method: string) {
  return (path === 'health' && method === 'GET') || path.startsWith('api/');
}
