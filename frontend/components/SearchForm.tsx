import { useState } from 'react';
import { motion } from 'framer-motion';
import { Search, MapPin, SlidersHorizontal, Loader2, Target } from 'lucide-react';
import { apiFetch } from '../lib/api';
import toast from 'react-hot-toast';

interface SearchFormProps {
  onStart: (data: { campaign_id: number; status: string }) => void;
  disabled?: boolean;
}

export default function SearchForm({ onStart, disabled = false }: SearchFormProps) {
  const [query, setQuery] = useState('');
  const [locationScope, setLocationScope] = useState<'city' | 'region'>('city');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [maxResults, setMaxResults] = useState('50');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || disabled) return;
    if (!query.trim() || !state.trim() || (locationScope === 'city' && !city.trim())) {
      toast.error(locationScope === 'city'
        ? 'Enter a business category, city and state.'
        : 'Enter a business category and region/state.');
      return;
    }

    const count = Number(maxResults);
    if (!Number.isInteger(count) || count < 1 || count > 120) {
      toast.error('Target businesses must be between 1 and 120.');
      return;
    }

    setLoading(true);
    try {
      const res = await apiFetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          location_scope: locationScope,
          city: locationScope === 'city' ? city.trim() : null,
          state: state.trim(),
          country: 'United States',
          max_results: count,
          radius: 50000,
        }),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || 'Search request failed.');
      }
      const data = await res.json();
      onStart(data);
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : 'Search failed. Check the local scraper and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass-panel p-6 lg:p-8"
    >
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-ember/10 flex items-center justify-center">
          <Target className="w-5 h-5 text-ember" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-pearl">New Lead Search</h2>
          <p className="text-sm text-muted">Find businesses without a website listed in Google Maps</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <label className="input-label">Business Category</label>
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              className="input pl-10"
              placeholder="e.g. coffee shop, barbershop, auto detailing"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="md:col-span-2">
          <label className="input-label">Search Area</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              aria-pressed={locationScope === 'city'}
              onClick={() => setLocationScope('city')}
              className={`rounded-xl border px-4 py-3 text-sm font-medium transition-colors ${
                locationScope === 'city'
                  ? 'border-ember bg-ember/10 text-pearl'
                  : 'border-edge/40 bg-shadow/20 text-muted hover:text-pearl'
              }`}
            >
              City
            </button>
            <button
              type="button"
              aria-pressed={locationScope === 'region'}
              onClick={() => setLocationScope('region')}
              className={`rounded-xl border px-4 py-3 text-sm font-medium transition-colors ${
                locationScope === 'region'
                  ? 'border-ember bg-ember/10 text-pearl'
                  : 'border-edge/40 bg-shadow/20 text-muted hover:text-pearl'
              }`}
            >
              State / Region
            </button>
          </div>
        </div>

        {locationScope === 'city' && (
          <div>
            <label className="input-label">City</label>
            <div className="relative">
              <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input
                className="input pl-10"
                placeholder="e.g. Miami"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                required
              />
            </div>
          </div>
        )}

        <div className={locationScope === 'region' ? 'md:col-span-2' : ''}>
          <label className="input-label">{locationScope === 'city' ? 'State' : 'Region / State'}</label>
          <input
            className="input"
            placeholder={locationScope === 'city'
              ? 'e.g. Florida or FL'
              : 'e.g. Florida, Southern California, New England'}
            value={state}
            onChange={(e) => setState(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="input-label">Target Businesses to Return (1–120)</label>
          <input
            className="input"
            type="number"
            min="1"
            max="120"
            step="1"
            value={maxResults}
            onChange={(e) => setMaxResults(e.target.value)}
            required
          />
        </div>
      </div>

      <div className="flex items-center gap-2 mt-6 mb-3">
        <SlidersHorizontal className="w-3.5 h-3.5 text-muted" />
        <span className="text-xs font-medium text-muted uppercase tracking-wider">Search settings</span>
        <div className="flex-1 h-px bg-edge/30" />
      </div>

      <div className="rounded-xl bg-shadow/30 border border-edge/20 p-4 text-xs text-muted flex items-start gap-2">
        <MapPin className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <span>Country: United States. Choose a city for a local search or a state/region for a broader search. The target is the number of unique businesses to return after filtering out listed websites and duplicates. Regional searches are broad Maps queries, not a guarantee that every business in a large area will be found.</span>
      </div>

      <motion.button
        type="submit"
        disabled={loading || disabled}
        className="btn-primary w-full mt-6 py-3 text-base"
        whileTap={{ scale: 0.98 }}
      >
        {loading || disabled ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {loading ? 'Starting search...' : 'Search in progress...'}
          </>
        ) : (
          <>
            <Search className="w-4 h-4" />
            Find Businesses
          </>
        )}
      </motion.button>
    </motion.form>
  );
}
