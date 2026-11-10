import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, MapPin } from 'lucide-react';
import ResultsTable from '../../components/ResultsTable';
import StatusBadge from '../../components/StatusBadge';
import { apiFetch } from '../../lib/api';
import toast from 'react-hot-toast';

export default function CampaignPage() {
  const router = useRouter();
  const { id } = router.query;
  const [campaign, setCampaign] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    if (!id) return;
    try {
      const [campRes, leadsRes] = await Promise.all([
        apiFetch('/api/search/' + id),
        apiFetch('/api/campaigns/' + id + '/leads'),
      ]);
      if (!campRes.ok || !leadsRes.ok) throw new Error('Could not load campaign data.');
      setCampaign(await campRes.json());
      setLeads(await leadsRes.json());
    } catch (error) {
      console.error(error);
      toast.error('Failed to load campaign data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [id]);

  if (loading) {
    return <div className="flex items-center justify-center py-32"><Loader2 className="w-6 h-6 text-ember animate-spin" /></div>;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/')} className="btn-icon btn-ghost">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-pearl">{campaign?.query || 'Campaign'}</h1>
              <StatusBadge status={campaign?.status} />
            </div>
            <p className="text-xs text-muted flex items-center gap-1 mt-0.5">
              <MapPin className="w-3 h-3" />
              {campaign?.location || [campaign?.city, campaign?.state, campaign?.country].filter(Boolean).join(', ')}
            </p>
          </div>
        </div>
        <button onClick={() => router.push('/export/' + id)} className="btn-primary text-sm">
          Add to Google Sheets
        </button>
      </div>

      <ResultsTable leads={leads} campaignId={id as string} city={campaign?.city} state={campaign?.state} />
    </div>
  );
}
