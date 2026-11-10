import { errorMessage } from '../lib/api';

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
