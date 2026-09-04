const API_BASE = (import.meta.env.VITE_ARIA_API_URL || '').replace(/\/$/, '');

function buildHeaders(extraHeaders: HeadersInit = {}): HeadersInit {
  return extraHeaders;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') {
      return payload.detail;
    }
    if (typeof payload?.detail?.detail === 'string') {
      return payload.detail.detail;
    }
    if (typeof payload?.message === 'string') {
      return payload.message;
    }
  } catch {
    // Fall through to status text.
  }

  return `${response.status} ${response.statusText}`.trim();
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<T>;
}

export async function fetchBinary(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.blob();
}

export function getApiBase(): string {
  return API_BASE;
}
