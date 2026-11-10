import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, MapPin } from 'lucide-react';
import ResultsTable from '../../components/ResultsTable';
import StatusBadge from '../../components/StatusBadge';
import { apiFetch, errorMessage, readBody } from '../../lib/api';
import toast from 'react-hot-toast';

export default function CampaignPage() {
  const router = useRouter();
  const { id } = router.query;
  const [campaign, setCampaign] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    if (!id) return;
    try {
      const [campRes, leadsRes] = await Promise.all([
        apiFetch(`/api/search/${id}`),
        apiFetch(`/api/campaigns/${id}/leads`),
      ]);
      const campaignData = await readBody(campRes);
      const leadsData = await readBody(leadsRes);
      if (!campRes.ok) {
        toast.error(errorMessage(campaignData, 'Failed to load campaign data'));
      } else {
        setCampaign(campaignData);
      }
      setLeads(Array.isArray(leadsData) ? leadsData : []);
    } catch (e) {
      console.error(e);
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
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-6 h-6 text-ember animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/')}
            className="btn-icon btn-ghost"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-pearl">
                {campaign?.query || 'Campaign'}
              </h1>
              <StatusBadge status={campaign?.status} />
            </div>
            <p className="text-xs text-muted flex items-center gap-1 mt-0.5">
              <MapPin className="w-3 h-3" />
              {campaign?.location}
            </p>
            {campaign?.status_detail && (
              <p className="text-xs text-muted mt-1 max-w-xl">{campaign.status_detail}</p>
            )}
          </div>
        </div>

        <button
          onClick={() => router.push(`/export/${id}`)}
          className="btn-primary text-sm"
        >
          Export to Sheets
        </button>
      </div>

      {/* Results */}
      <ResultsTable leads={leads} campaignId={id as string} />
    </div>
  );
}
