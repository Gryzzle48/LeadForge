import { errorMessage, isHtmlPage, readBody } from '../lib/api';

describe('errorMessage', () => {
  it('reads a string detail', () => {
    expect(errorMessage({ detail: 'Missing key' }, 'fallback')).toBe('Missing key');
  });

  it('reads field validation errors', () => {
    expect(errorMessage({
      detail: [{ loc: ['body', 'radius'], msg: 'Input should be less than or equal to 50000' }],
    }, 'fallback')).toBe('radius: Input should be less than or equal to 50000');
  });

  it('uses the fallback when the body is empty', () => {
    expect(errorMessage(null, 'fallback')).toBe('fallback');
    expect(errorMessage({}, 'fallback')).toBe('fallback');
  });
});

function fakeResponse(body, status, contentType) {
  return {
    status,
    headers: { get: (name) => (String(name).toLowerCase() === 'content-type' ? contentType : null) },
    text: async () => body,
  };
}

describe('readBody', () => {
  it('shows the status and text when the API returns a plain error', async () => {
    const body = await readBody(fakeResponse('Internal Server Error', 500, 'text/plain; charset=utf-8'));
    expect(body.detail).toBe('The server returned 500: Internal Server Error');
    expect(body.detail).not.toMatch(/NEXT_PUBLIC_API_URL/);
  });

  it('mentions the API URL only for an HTML page', async () => {
    const html = '<!DOCTYPE html><html><body>not found</body></html>';
    expect(isHtmlPage(html, 'text/html; charset=utf-8')).toBe(true);
    expect(isHtmlPage('Internal Server Error', 'text/html')).toBe(false);
    const body = await readBody(fakeResponse(html, 404, 'text/html; charset=utf-8'));
    expect(body.detail).toMatch(/NEXT_PUBLIC_API_URL/);
  });

  it('reads JSON error details', async () => {
    const payload = JSON.stringify({ detail: 'The server hit an unexpected error. The details are in the API logs.' });
    const body = await readBody(fakeResponse(payload, 500, 'application/json'));
    expect(body.detail).toMatch(/unexpected error/);
  });
});
