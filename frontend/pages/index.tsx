import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Target, Users, Loader2, CheckCircle2, AlertCircle, TrendingUp, MapPin } from 'lucide-react';
import SearchForm from '../components/SearchForm';
import StatusBadge from '../components/StatusBadge';
import { apiFetch } from '../lib/api';
import toast from 'react-hot-toast';

export default function Home() {
  const router = useRouter();
  const [status, setStatus] = useState<any>(null);
  const [polling, setPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  const handleStart = (data: { campaign_id: number; status: string }) => {
    setStatus(null);
    setPolling(true);
    intervalRef.current = setInterval(async () => {
      try {
        const res = await apiFetch('/api/search/' + data.campaign_id);
        if (!res.ok) throw new Error('Could not get search status.');
        const result = await res.json();
        setStatus(result);
        if (result.status === 'completed' || result.status === 'failed') {
          if (intervalRef.current) clearInterval(intervalRef.current);
          intervalRef.current = null;
          setPolling(false);
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
        intervalRef.current = null;
        setPolling(false);
        toast.error('Connection lost. Check your API endpoint.');
      }
    }, 2000);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center py-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-ember/10 border border-ember/20 text-ember text-xs font-medium mb-4">
          <Zap className="w-3 h-3" />
          LocalWeb Studio · Lead Finder
        </div>
        <h1 className="text-3xl lg:text-4xl font-bold text-pearl mb-2">Find local businesses without a website listed</h1>
        <p className="text-muted text-sm max-w-lg mx-auto">
          Search by business category in a US city or a broader state/region, review the Maps listings and append new leads to one Google Sheet.
        </p>
      </motion.div>

      <SearchForm onStart={handleStart} />

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="grid grid-cols-3 gap-3">
        {[
          { icon: Target, label: 'Search filters', value: 'Category + Area', desc: 'US businesses' },
          { icon: TrendingUp, label: 'Result limit', value: 'Up to 120', desc: 'per search' },
          { icon: Users, label: 'Duplicate check', value: 'Global', desc: 'Place ID' },
        ].map((stat, index) => (
          <div key={index} className="glass-panel-light p-4 text-center">
            <stat.icon className="w-5 h-5 text-ember mx-auto mb-2" />
            <p className="text-xs font-semibold text-pearl">{stat.value}</p>
            <p className="text-[10px] text-muted mt-0.5">{stat.label}</p>
            <p className="text-[10px] text-muted/70 mt-0.5">{stat.desc}</p>
          </div>
        ))}
      </motion.div>

      <AnimatePresence>
        {polling && status && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="glass-panel p-5 overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-ember animate-spin" />
                <div>
                  <p className="text-sm font-medium text-pearl">Searching for "{status.query}" in {status.location}</p>
                  <p className="text-xs text-muted mt-0.5 flex items-center gap-1"><MapPin className="w-3 h-3" /> Google Places search in progress</p>
                </div>
              </div>
              <StatusBadge status={status.status} />
            </div>
            <div className="progress">
              <div className="progress-fill" style={{ width: Math.min((status.total_leads || 0) / Math.max(status.max_results || 100, 1) * 100, 100) + '%' }} />
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-muted">
              <span>{status.total_leads || 0} new businesses found</span>
              {status.status === 'running' && <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-ember animate-pulse" /> Searching...</span>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {status?.status === 'completed' && !polling && (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-8 text-center border-jade/30">
            <div className="w-14 h-14 rounded-full bg-jade/10 mx-auto mb-4 flex items-center justify-center"><CheckCircle2 className="w-7 h-7 text-jade" /></div>
            <h2 className="text-xl font-bold text-pearl mb-1">Search Complete</h2>
            <p className="text-sm text-muted mb-6">
              Found <span className="text-pearl font-semibold">{status.total_leads}</span> new businesses without a website listed in {status.location}
            </p>
            <div className="flex items-center justify-center gap-3">
              <motion.button whileTap={{ scale: 0.95 }} className="btn-primary" onClick={() => router.push('/campaigns/' + status.id)}>
                <Users className="w-4 h-4" /> Review Leads
              </motion.button>
              <motion.button whileTap={{ scale: 0.95 }} className="btn-secondary" onClick={() => router.push('/export/' + status.id)}>
                <Zap className="w-4 h-4" /> Add to Google Sheets
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {status?.status === 'failed' && !polling && (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-6 text-center border-danger/30">
            <AlertCircle className="w-10 h-10 text-danger mx-auto mb-3" />
            <p className="text-sm text-muted">Search failed. Check your API key and location, then try again.</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
