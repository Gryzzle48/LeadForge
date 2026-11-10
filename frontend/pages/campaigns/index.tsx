import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { motion } from 'framer-motion';
import { Search, MapPin, Clock, ArrowRight, Loader2, Target } from 'lucide-react';
import StatusBadge from '../../components/StatusBadge';
import { apiFetch, readBody } from '../../lib/api';

export default function CampaignsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch('/api/campaigns');
        const data = await readBody(res);
        if (res.ok && Array.isArray(data)) {
          setCampaigns(data);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-6 h-6 text-ember animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-ember/10 flex items-center justify-center">
          <Target className="w-5 h-5 text-ember" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-pearl">Campaign History</h1>
          <p className="text-xs text-muted">All your past lead generation searches</p>
        </div>
      </div>

      {campaigns.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <Search className="w-12 h-12 text-muted/30 mx-auto mb-4" />
          <p className="text-muted text-sm">No campaigns yet. Start a search to begin.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {campaigns.map((c, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="glass-panel-light p-4 flex items-center justify-between cursor-pointer hover:bg-edge/20 transition-colors"
              onClick={() => router.push(`/campaigns/${c.id}`)}
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-shadow/50 flex items-center justify-center flex-shrink-0">
                  <Search className="w-4 h-4 text-ember" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-pearl truncate">{c.query}</p>
                  <p className="text-xs text-muted flex items-center gap-1 mt-0.5">
                    <MapPin className="w-3 h-3 flex-shrink-0" />
                    <span className="truncate">{c.location}</span>
                    <span className="mx-1">·</span>
                    <Clock className="w-3 h-3 flex-shrink-0" />
                    {c.total_leads || 0} leads
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <StatusBadge status={c.status} />
                <ArrowRight className="w-4 h-4 text-muted" />
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
