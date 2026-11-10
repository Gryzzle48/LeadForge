import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Zap, Target, Users, Loader2, CheckCircle2, AlertCircle, TrendingUp, MapPin } from 'lucide-react';
import SearchForm from '../components/SearchForm';
import StatusBadge from '../components/StatusBadge';
import { apiFetch, errorMessage, readBody } from '../lib/api';
import { formatSearchProgress } from '../lib/progress';
import toast from 'react-hot-toast';

export default function Home() {
  const router = useRouter();
  const [campaign, setCampaign] = useState(null);
  const [status, setStatus] = useState(null);
  const [polling, setPolling] = useState(false);
  const [apiProblem, setApiProblem] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch('/api/health');
        const body = await readBody(res) as { database?: string };
        if (cancelled) return;
        if (!res.ok) {
          setApiProblem(errorMessage(body, 'The API is not reachable.'));
          return;
        }
        if (!body || body.database !== 'connected') {
          setApiProblem('The API is up, but the database is not connected. Check DATABASE_URL on the backend.');
        }
      } catch {
        if (!cancelled) {
          setApiProblem('Cannot reach the API. Set NEXT_PUBLIC_API_URL to the public backend address and redeploy.');
        }
      }
    })();
    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  const handleStart = (data) => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setCampaign(data);
    setStatus(null);
    setPolling(true);
    intervalRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/search/${data.campaign_id}`);
        const s = await readBody(res) as { status?: string; status_detail?: string };
        if (!res.ok || !s || !s.status) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setPolling(false);
          toast.error(errorMessage(s, 'Lost the search status. Check the API connection.'));
          return;
        }
        setStatus(s);
        if (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled') {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setPolling(false);
        }
      } catch {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        setPolling(false);
        toast.error('Connection lost. Check your API endpoint.');
      }
    }, 2000);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center py-4"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-ember/10 border border-ember/20 text-ember text-xs font-medium mb-4">
          <Zap className="w-3 h-3" />
          Lead Generation Engine
        </div>
        <h1 className="text-3xl lg:text-4xl font-bold text-pearl mb-2">
          Find businesses that need your help
        </h1>
        <p className="text-muted text-sm max-w-lg mx-auto">
          Search a city for businesses with no website. Save the list to a Google Sheet and draft outreach you send yourself.
        </p>
      </motion.div>

      {apiProblem && (
        <div className="glass-panel p-4 border-danger/30 text-sm text-pearl">
          {apiProblem}
        </div>
      )}

      {/* Search Form */}
      <SearchForm onStart={handleStart} />

      {/* Stats Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-3 gap-3"
      >
        {[
          { icon: Target, label: 'No-Website Filter', value: 'Automatic', desc: 'Local scraper' },
          { icon: TrendingUp, label: 'Per Category', value: '3 Angles', desc: 'Rotating copy' },
          { icon: Users, label: 'You send them', value: 'Drafts only', desc: 'Nothing auto-sends' },
        ].map((stat, i) => (
          <div key={i} className="glass-panel-light p-4 text-center">
            <stat.icon className="w-5 h-5 text-ember mx-auto mb-2" />
            <p className="text-xs font-semibold text-pearl">{stat.value}</p>
            <p className="text-[10px] text-muted mt-0.5">{stat.label}</p>
          </div>
        ))}
      </motion.div>

      {/* Progress */}
      <AnimatePresence>
        {polling && status && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-panel p-5 overflow-hidden"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-ember animate-spin" />
                <div>
                  <p className="text-sm font-medium text-pearl">
                    Searching for &ldquo;{status.query}&rdquo; in {status.location}
                  </p>
                  <p className="text-xs text-muted mt-0.5 flex items-center gap-1">
                    <MapPin className="w-3 h-3" /> Covering the whole city, one area at a time
                  </p>
                </div>
              </div>
              <StatusBadge status={status.status} />
            </div>

            <div className="progress">
              <div
                className="progress-fill"
                style={{ width: `${Math.min(status.tiles_total ? ((status.tiles_done || 0) / status.tiles_total) * 100 : 5, 100)}%` }}
              />
            </div>

            <div className="flex items-center justify-between gap-4 mt-3 text-xs text-muted">
              <span>
                {formatSearchProgress(status).tiles}
                {' · '}
                {formatSearchProgress(status).places}
                {' · '}
                {formatSearchProgress(status).leads}
              </span>
              {status.status === 'running' && (
                <button
                  className="btn-secondary text-xs"
                  disabled={status.cancel_requested}
                  onClick={async () => {
                    const res = await apiFetch(`/api/search/${status.id}/cancel`, { method: 'POST' });
                    const body = await readBody(res);
                    if (res.ok) setStatus(body);
                  }}
                >
                  {status.cancel_requested ? 'Stopping after this area' : 'Cancel'}
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Complete */}
      <AnimatePresence>
        {status?.status === 'completed' && !polling && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-panel p-8 text-center border-jade/30"
          >
            <div className="w-14 h-14 rounded-full bg-jade/10 mx-auto mb-4 flex items-center justify-center">
              <CheckCircle2 className="w-7 h-7 text-jade" />
            </div>
            <h2 className="text-xl font-bold text-pearl mb-1">Search Complete</h2>
            <div className="mb-6">
              <p className="text-sm text-muted">
                Found <span className="text-pearl font-semibold">{status.total_leads}</span> businesses without websites in {status.location}
              </p>
              {status.status_detail && (
                <p className="text-xs text-muted max-w-md mx-auto mt-2">{status.status_detail}</p>
              )}
            </div>
            <div className="flex items-center justify-center gap-3">
              <motion.button
                whileTap={{ scale: 0.95 }}
                className="btn-primary"
                onClick={() => router.push(`/campaigns/${status.id}`)}
              >
                <Users className="w-4 h-4" />
                View Leads & Generate Emails
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.95 }}
                className="btn-secondary"
                onClick={() => router.push(`/export/${status.id}`)}
              >
                <Zap className="w-4 h-4" />
                Export to Sheets
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      <AnimatePresence>
        {(status?.status === 'failed' || status?.status === 'cancelled') && !polling && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-panel p-6 text-center border-danger/30"
          >
            <AlertCircle className="w-10 h-10 text-danger mx-auto mb-3" />
            <p className="text-sm text-muted">{status.status_detail || 'Search failed. Check that the maps scraper is running.'}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
