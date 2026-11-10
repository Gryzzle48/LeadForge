import { useState } from 'react';
import { motion } from 'framer-motion';
import { Search, MapPin, SlidersHorizontal, Loader2, Target } from 'lucide-react';
import { apiFetch, errorMessage, readBody } from '../lib/api';
import toast from 'react-hot-toast';

interface SearchFormProps {
  onStart: (data: { campaign_id: number; status: string }) => void;
}

export default function SearchForm({ onStart }: SearchFormProps) {
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [targetLeads, setTargetLeads] = useState('');
  const [minRating, setMinRating] = useState('');
  const [minReviews, setMinReviews] = useState('');
  const [maxReviews, setMaxReviews] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query || !location) return;
    const minReviewCount = minReviews === '' ? null : Number(minReviews);
    const maxReviewCount = maxReviews === '' ? null : Number(maxReviews);
    if ((minReviewCount !== null && Number.isNaN(minReviewCount)) || (maxReviewCount !== null && Number.isNaN(maxReviewCount))) {
      toast.error('Review filters must be whole numbers.');
      return;
    }
    if (minReviewCount !== null && maxReviewCount !== null && minReviewCount > maxReviewCount) {
      toast.error('Min reviews cannot be greater than max reviews.');
      return;
    }
    const target = targetLeads === '' ? null : Number(targetLeads);
    if (target !== null && (!Number.isInteger(target) || target < 1)) {
      toast.error('Target leads must be a whole number, or leave it blank to search the whole city.');
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          location,
          target_leads: target,
          min_rating: minRating ? parseFloat(minRating) : null,
          min_reviews: minReviewCount,
          max_reviews: maxReviewCount,
        }),
      });
      const data = await readBody(res);
      if (!res.ok || !data || typeof data !== 'object' || !('campaign_id' in data)) {
        toast.error(errorMessage(data, 'Search did not start. Check the backend and the maps scraper.'));
        return;
      }
      onStart(data as { campaign_id: number; status: string });
    } catch (err) {
      console.error(err);
      toast.error('Search failed. Check that the maps scraper is running.');
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
          <p className="text-sm text-muted">Search the whole city for businesses without a website</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <label className="input-label">Business Type</label>
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              className="input pl-10"
              placeholder="e.g. restaurant, plumber, dentist"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>
        </div>

        <div>
          <label className="input-label">Location</label>
          <div className="relative">
            <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              className="input pl-10"
              placeholder="e.g. Austin, TX"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-6 mb-3">
        <SlidersHorizontal className="w-3.5 h-3.5 text-muted" />
        <span className="text-xs font-medium text-muted uppercase tracking-wider">Filters</span>
        <div className="flex-1 h-px bg-edge/30" />
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <label className="input-label">Target leads with no website (optional)</label>
          <input
            className="input"
            type="number"
            min="1"
            step="1"
            placeholder="Blank = search until the city is covered"
            value={targetLeads}
            onChange={(e) => setTargetLeads(e.target.value)}
          />
        </div>

        <div>
          <label className="input-label">Min. Rating (optional)</label>
          <input
            className="input"
            type="number"
            min="1"
            max="5"
            step="0.5"
            placeholder="e.g. 4.0"
            value={minRating}
            onChange={(e) => setMinRating(e.target.value)}
          />
        </div>

        <div>
          <label className="input-label">Min. Reviews (optional)</label>
          <input
            className="input"
            type="number"
            min="0"
            step="1"
            placeholder="e.g. 5"
            value={minReviews}
            onChange={(e) => setMinReviews(e.target.value)}
          />
        </div>

        <div>
          <label className="input-label">Max. Reviews (optional)</label>
          <input
            className="input"
            type="number"
            min="0"
            step="1"
            placeholder="e.g. 200"
            value={maxReviews}
            onChange={(e) => setMaxReviews(e.target.value)}
          />
        </div>
      </div>

      <motion.button
        type="submit"
        disabled={loading}
        className="btn-primary w-full mt-6 py-3 text-base"
        whileTap={{ scale: 0.98 }}
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Scanning...
          </>
        ) : (
          <>
            <Search className="w-4 h-4" />
            Find Leads
          </>
        )}
      </motion.button>
    </motion.form>
  );
}
