import { formatSearchProgress } from '../lib/progress';

describe('formatSearchProgress', () => {
  it('shows tiles, places, and the target', () => {
    const text = formatSearchProgress({
      tiles_done: 2,
      tiles_total: 8,
      places_checked: 40,
      total_leads: 3,
      target_leads: 10,
    });
    expect(text.tiles).toBe('2/8 tiles');
    expect(text.places).toBe('40 places checked');
    expect(text.leads).toBe('3 of 10 leads');
  });

  it('shows a lead count when no target was set', () => {
    const text = formatSearchProgress({
      tiles_done: 4,
      tiles_total: 4,
      places_checked: 12,
      total_leads: 6,
      target_leads: null,
    });
    expect(text.leads).toBe('6 leads');
    expect(text.tiles).toBe('4/4 tiles');
  });
});