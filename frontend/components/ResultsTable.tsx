import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Mail, MapPin, MessageSquare, Phone, Instagram, Search, Loader2, XCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';
import toast from 'react-hot-toast';

interface Lead {
  id: number;
  name: string;
  category?: string;
  phone?: string;
  email?: string;
  instagram_url?: string;
  google_maps_url?: string;
  contact_sources?: string[];
}

interface BatchProgress {
  completed: number;
  total: number;
  found: number;
  failed: number;
}

interface BatchFailure {
  id: number;
  name: string;
  message: string;
}

interface ResultsTableProps {
  leads: Lead[];
  campaignId: string | number;
  city?: string;
  state?: string;
}

// Slightly slower than the endpoint's 10/minute limit to leave room for
// clock jitter and avoid hitting the limit at exact six-second boundaries.
const REQUEST_START_INTERVAL_MS = 6500;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function ResultsTable({ leads, campaignId, city, state }: ResultsTableProps) {
  const [localLeads, setLocalLeads] = useState<Lead[]>(leads);
  const [enrichingIds, setEnrichingIds] = useState<number[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [batchFailures, setBatchFailures] = useState<BatchFailure[]>([]);
  const batchCancelRef = useRef(false);

  useEffect(() => {
    // The campaign page refreshes from the API periodically. Merge fresh database
    // values without dropping source links returned by a just-finished enrichment.
    setLocalLeads((current) => leads.map((incoming) => {
      const previous = current.find((lead) => lead.id === incoming.id);
      return {
        ...incoming,
        email: incoming.email || previous?.email,
        instagram_url: incoming.instagram_url || previous?.instagram_url,
        contact_sources: previous?.contact_sources || incoming.contact_sources,
      };
    }));
  }, [leads]);

  useEffect(() => {
    // Do not keep scheduling new searches after the user leaves this campaign.
    return () => { batchCancelRef.current = true; };
  }, []);

  const enrichLead = async (leadId: number) => {
    setEnrichingIds((current) => current.includes(leadId) ? current : [...current, leadId]);
    try {
      const response = await apiFetch('/api/leads/' + leadId + '/enrich', { method: 'POST' });
      let payload: any = {};
      try { payload = await response.json(); } catch { /* Empty or non-JSON error response. */ }
      if (!response.ok) throw new Error(payload.detail || 'Contact search failed.');
      setLocalLeads((current) => current.map((lead) => lead.id === leadId ? payload : lead));
      const found = Boolean(payload.email || payload.instagram_url);
      toast.success(found ? 'Public contacts updated' : 'No additional public contacts found');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Contact search failed');
    } finally {
      setEnrichingIds((current) => current.filter((id) => id !== leadId));
    }
  };

  const startBatchEnrichment = async () => {
    const candidates = localLeads.filter((lead) => !lead.email || !lead.instagram_url);
    if (!candidates.length) {
      toast.success('Every business already has an email and Instagram link.');
      return;
    }
    if (enrichingIds.length) return;

    batchCancelRef.current = false;
    setBatchRunning(true);
    setBatchFailures([]);
    setBatchProgress({ completed: 0, total: candidates.length, found: 0, failed: 0 });

    let nextIndex = 0;
    let nextStartAt = Date.now();
    let completedCount = 0;
    let foundCount = 0;
    let failedCount = 0;
    let stopReason: string | null = null;

    const worker = async () => {
      while (!batchCancelRef.current) {
        const index = nextIndex++;
        if (index >= candidates.length) return;

        const lead = candidates[index];
        const delay = Math.max(0, nextStartAt - Date.now());
        nextStartAt = Math.max(Date.now(), nextStartAt) + REQUEST_START_INTERVAL_MS;
        if (delay > 0) await wait(delay);
        if (batchCancelRef.current) return;

        setEnrichingIds((current) => current.includes(lead.id) ? current : [...current, lead.id]);
        let foundNewContact = false;

        try {
          const response = await apiFetch('/api/leads/' + lead.id + '/enrich', { method: 'POST' });
          let payload: any = {};
          try { payload = await response.json(); } catch { /* Handled below. */ }
          if (!response.ok) {
            const error: any = new Error(payload.detail || 'Contact search failed.');
            error.status = response.status;
            throw error;
          }

          foundNewContact = Boolean(
            (!lead.email && payload.email) ||
            (!lead.instagram_url && payload.instagram_url)
          );
          if (foundNewContact) foundCount += 1;
          setLocalLeads((current) => current.map((item) => item.id === lead.id ? payload : item));
        } catch (error: any) {
          const message = error instanceof Error ? error.message : 'Contact search failed';
          const providerStopped =
            error?.status === 429 ||
            /not configured|SERPAPI_API_KEY|provider.*HTTP (401|403|429|5\d\d)|contact search provider error|rate limit/i.test(message);

          failedCount += 1;
          setBatchFailures((current) => [
            ...current,
            { id: lead.id, name: lead.name, message },
          ]);
          if (providerStopped) {
            stopReason = message;
            batchCancelRef.current = true;
          }
        } finally {
          setEnrichingIds((current) => current.filter((id) => id !== lead.id));
          completedCount += 1;
          setBatchProgress({
            completed: completedCount,
            total: candidates.length,
            found: foundCount,
            failed: failedCount,
          });
        }
      }
    };

    try {
      // Two workers, with globally spaced request starts to stay under the
      // single-lead endpoint's 10-requests-per-minute limit.
      await Promise.all([worker(), worker()]);
    } finally {
      setBatchRunning(false);
      setEnrichingIds([]);
    }

    if (stopReason) {
      toast.error('Bulk search stopped: ' + stopReason);
    } else if (batchCancelRef.current) {
      toast('Bulk search stopped. Completed results have been saved.');
    } else {
      toast.success(
        'Bulk search finished. Newly found contacts: ' +
        foundCount + '. Errors: ' + failedCount + '.'
      );
    }
  };

  const needsEnrichmentCount = localLeads.filter((lead) => !lead.email || !lead.instagram_url).length;
  const progressPercent = batchProgress?.total
    ? Math.round((batchProgress.completed / batchProgress.total) * 100)
    : 0;

  return (
    <motion.div
      data-campaign-id={campaignId}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel overflow-hidden"
    >
      <div className="p-5 border-b border-edge/20 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-jade/10 flex items-center justify-center">
            <MapPin className="w-4.5 h-4.5 text-jade" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-pearl">Businesses without a website listed</h2>
            <p className="text-xs text-muted">{localLeads.length} new businesses found</p>
          </div>
        </div>

        {needsEnrichmentCount > 0 && (
          <div className="flex items-center gap-2">
            {batchRunning ? (
              <button
                type="button"
                onClick={() => { batchCancelRef.current = true; }}
                className="btn-secondary text-sm inline-flex items-center gap-2"
              >
                <XCircle className="w-4 h-4" /> Stop search
              </button>
            ) : (
              <button
                type="button"
                onClick={startBatchEnrichment}
                disabled={enrichingIds.length > 0}
                className="btn-primary text-sm inline-flex items-center gap-2 disabled:opacity-50"
              >
                <Search className="w-4 h-4" />
                Find contacts for all ({needsEnrichmentCount})
              </button>
            )}
          </div>
        )}
      </div>

      {batchProgress && (
        <div className="px-5 py-3 border-b border-edge/20">
          <div className="flex items-center justify-between gap-3 text-xs text-muted mb-2">
            <span>
              {batchRunning
                ? 'Searching public contacts…'
                : batchCancelRef.current
                  ? 'Bulk search stopped'
                  : 'Last bulk search'}
              {' · '}{batchProgress.completed}/{batchProgress.total}
              {' · '}found {batchProgress.found}
              {' · '}errors {batchProgress.failed}
            </span>
            <span>{progressPercent}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-shadow overflow-hidden">
            <div
              className="h-full rounded-full bg-jade transition-all duration-300"
              style={{ width: progressPercent + '%' }}
            />
          </div>
          <p className="text-[11px] text-muted mt-2">
            One external search per business with a missing email or Instagram link. Requests are spaced to stay below the server limit.
            {batchCancelRef.current && !batchRunning
              ? ' Unstarted businesses were left in the queue.'
              : ''}
          </p>
          {batchFailures.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-xs font-medium text-pearl">Businesses with errors</p>
              {batchFailures.slice(0, 5).map((failure) => (
                <p key={failure.id} className="text-[11px] text-muted break-words">
                  <span className="text-pearl">{failure.name}:</span> {failure.message}
                </p>
              ))}
              {batchFailures.length > 5 && (
                <p className="text-[11px] text-muted">
                  And {batchFailures.length - 5} more. See the error count above.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {localLeads.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 px-4">
          <MessageSquare className="w-12 h-12 text-muted/30 mb-4" />
          <p className="text-muted text-sm">No new businesses found for this search.</p>
        </div>
      ) : (
        <div className="table-wrap border-0 rounded-none">
          <table>
            <thead>
              <tr>
                <th style={{ width: 60 }}>#</th>
                <th>Business Name</th>
                <th>Category</th>
                <th>Google Maps</th>
                <th>Contacts</th>
                <th>City</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {localLeads.map((lead, index) => {
                const isEnriching = enrichingIds.includes(lead.id);
                const hasSearchableContacts = !lead.email || !lead.instagram_url;
                return (
                  <motion.tr
                    key={lead.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(index * 0.02, 0.3) }}
                  >
                    <td className="text-muted text-xs">{index + 1}</td>
                    <td className="font-medium">{lead.name}</td>
                    <td>
                      <span className="text-xs text-muted bg-shadow/50 px-2 py-1 rounded-md">
                        {lead.category || '—'}
                      </span>
                    </td>
                    <td>
                      {lead.google_maps_url ? (
                        <a
                          href={lead.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-frost hover:underline"
                        >
                          Open Maps <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : '—'}
                    </td>
                    <td>
                      <div className="flex flex-col gap-1 text-xs text-muted">
                        {lead.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" />{lead.phone}</span>}
                        {lead.email && <span className="inline-flex items-center gap-1"><Mail className="w-3 h-3" />{lead.email}</span>}
                        {lead.instagram_url && <a href={lead.instagram_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline"><Instagram className="w-3 h-3" />Instagram</a>}
                        {!lead.phone && !lead.email && !lead.instagram_url && <span>Not found yet</span>}
                        {lead.contact_sources?.length ? (
                          <a href={lead.contact_sources[0]} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-frost hover:underline">
                            Contact source <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : null}
                        {hasSearchableContacts && (
                          <button
                            type="button"
                            onClick={() => enrichLead(lead.id)}
                            disabled={isEnriching || batchRunning}
                            className="inline-flex items-center gap-1 text-frost hover:underline disabled:opacity-50"
                          >
                            {isEnriching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                            {isEnriching ? 'Searching…' : 'Find email / Instagram'}
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="text-xs text-muted">{city || '—'}</td>
                    <td className="text-xs text-muted">{state || '—'}</td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
