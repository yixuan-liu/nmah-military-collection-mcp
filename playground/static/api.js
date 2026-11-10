export async function api(path, body, onRequestId) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  onRequestId?.(response.headers.get('X-Request-ID'));
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    const message = typeof result?.error === 'string' && result.error.trim()
      ? result.error
      : `Request failed (HTTP ${response.status}).`;
    throw new Error(message);
  }
  return response.json();
}
