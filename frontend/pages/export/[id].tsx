import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, Upload, FileSpreadsheet, CheckCircle2 } from 'lucide-react';
import ScriptDisplay from '../../components/ScriptDisplay';
import StatusBadge from '../../components/StatusBadge';
import { apiFetch, errorMessage, readBody } from '../../lib/api';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';

export default function ExportPage() {
  const router = useRouter();
  const { id } = router.query;
  const [campaign, setCampaign] = useState(null);
  const [leads, setLeads] = useState([]);
  const [sheetUrl, setSheetUrl] = useState(null);
  const [warning, setWarning] = useState(null);
  const [exporting, setExporting] = useState(false);
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
      if (campRes.ok) setCampaign(campaignData);
      setLeads(Array.isArray(leadsData) ? leadsData : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await apiFetch(`/api/campaigns/${id}/export`, { method: 'POST' });
      const data = await readBody(res) as { sheet_url?: string; warning?: string; detail?: unknown };
      const url = data?.sheet_url;
      if (!res.ok || typeof url !== 'string' || !url.startsWith('https://')) {
        toast.error(errorMessage(data, 'Export failed'));
        return;
      }
      setSheetUrl(url);
      setWarning(data.warning || null);
      toast.success('Sheet created');
    } catch {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-6 h-6 text-ember animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => router.push('/')} className="btn-icon btn-ghost">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="text-lg font-semibold text-pearl">Export to Sheets</h1>
          <p className="text-xs text-muted">
            {campaign?.query} in {campaign?.location} &middot; {leads.length} leads
          </p>
        </div>
      </div>

      {!sheetUrl ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-panel p-12 text-center"
        >
          <div className="w-16 h-16 rounded-2xl bg-ember/10 mx-auto mb-6 flex items-center justify-center">
            <FileSpreadsheet className="w-8 h-8 text-ember" />
          </div>
          <h2 className="text-xl font-bold text-pearl mb-2">Ready for Export</h2>
          <p className="text-sm text-muted max-w-sm mx-auto mb-8">
            Add these leads to your Google Sheet. The columns are #, Name, Category, Google Maps, and Contacts. Draft emails stay in LeadForge. Nothing is sent automatically.
          </p>

          <div className="flex flex-col items-center gap-3">
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={handleExport}
              disabled={exporting}
              className="btn-primary text-base px-8 py-3"
            >
              {exporting ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Creating Sheet...</>
              ) : (
                <><Upload className="w-4 h-4" /> Create Sheet & Export</>
              )}
            </motion.button>

            <div className="flex items-center gap-2 text-xs text-muted mt-2">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              {leads.length} leads to export
            </div>
          </div>
        </motion.div>
      ) : (
        <>
          {warning && (
            <div className="glass-panel p-4 border-danger/30 text-sm text-pearl">{warning}</div>
          )}
          <ScriptDisplay sheetUrl={sheetUrl} />
        </>
      )}
    </div>
  );
}
