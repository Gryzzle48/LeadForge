import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, Upload, FileSpreadsheet, CheckCircle2, ExternalLink } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';

export default function ExportPage() {
  const router = useRouter();
  const { id } = router.query;
  const [campaign, setCampaign] = useState<any>(null);
  const [leads, setLeads] = useState<any[]>([]);
  const [sheetUrl, setSheetUrl] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    if (!id) return;
    try {
      const [campRes, leadsRes] = await Promise.all([
        apiFetch(\`/api/search/\${id}\`),
        apiFetch(\`/api/campaigns/\${id}/leads\`),
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

  useEffect(() => { fetchData(); }, [id]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await apiFetch(\`/api/campaigns/\${id}/export\`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Export failed.');
      if (data.sheet_url) {
        setSheetUrl(data.sheet_url);
        toast.success('New leads added to your Leads tab.');
      } else {
        throw new Error('Export did not return a Google Sheets URL.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center py-32"><Loader2 className="w-6 h-6 text-ember animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => router.push('/')} className="btn-icon btn-ghost">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="text-lg font-semibold text-pearl">Add to Google Sheets</h1>
          <p className="text-xs text-muted">
            {campaign?.query} in {campaign?.city || campaign?.location}, {campaign?.state || ''} · {leads.length} new businesses
          </p>
        </div>
      </div>

      {!sheetUrl ? (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-ember/10 mx-auto mb-6 flex items-center justify-center">
            <FileSpreadsheet className="w-8 h-8 text-ember" />
          </div>
          <h2 className="text-xl font-bold text-pearl mb-2">Ready to add leads</h2>
          <p className="text-sm text-muted max-w-md mx-auto mb-8">
            New businesses will be appended to your existing Leads tab. Existing records stay untouched and duplicates are skipped.
          </p>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={handleExport}
            disabled={exporting || leads.length === 0}
            className="btn-primary text-base px-8 py-3"
          >
            {exporting ? <><Loader2 className="w-4 h-4 animate-spin" /> Adding leads...</> : <><Upload className="w-4 h-4" /> Add to Leads</>}
          </motion.button>
          <div className="flex items-center justify-center gap-2 text-xs text-muted mt-4">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            {leads.length} new businesses ready
          </div>
        </motion.div>
      ) : (
        <div className="glass-panel p-6 border-jade/30 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-jade/10 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5 text-jade" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-pearl">Leads added to your permanent spreadsheet</p>
            <a href={sheetUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-frost hover:underline inline-flex items-center gap-1 mt-1">
              Open Google Sheets <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
