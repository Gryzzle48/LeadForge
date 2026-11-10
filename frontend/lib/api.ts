const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

export async function apiFetch(url: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return fetch(url, { ...options, headers });
}

export function errorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        const loc = Array.isArray((item as { loc?: unknown }).loc)
          ? (item as { loc: unknown[] }).loc.filter((part) => part !== 'body').join('.')
          : '';
        const msg = String((item as { msg: unknown }).msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return String(item);
    }).filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

export function isHtmlPage(text: string, contentType: string | null): boolean {
  const type = (contentType || '').toLowerCase();
  if (!type.includes('text/html')) return false;
  return /<\s*html[\s>]/i.test(text) || /<\s*!doctype\s+html/i.test(text);
}

export function nonJsonDetail(status: number, text: string, contentType: string | null): string {
  if (isHtmlPage(text, contentType)) {
    return 'This site is not connected to the API. In Vercel, set NEXT_PUBLIC_API_URL to the public https address of the backend (not a private Railway hostname) and redeploy.';
  }
  const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 200);
  if (snippet) return `The server returned ${status}: ${snippet}`;
  return `The server returned ${status}.`;
}

export async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: nonJsonDetail(res.status, text, res.headers.get('content-type')) };
  }
}
