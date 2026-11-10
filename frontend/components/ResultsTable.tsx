import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Mail, MapPin, MessageSquare, Phone, Instagram, Search, Loader2 } from 'lucide-react';
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

interface ResultsTableProps {
  leads: Lead[];
  campaignId: string | number;
  city?: string;
  state?: string;
}

export default function ResultsTable({ leads, campaignId, city, state }: ResultsTableProps) {
  const [localLeads, setLocalLeads] = useState<Lead[]>(leads);
  const [enrichingIds, setEnrichingIds] = useState<number[]>([]);

  useEffect(() => {
    setLocalLeads(leads);
  }, [leads]);

  const enrichLead = async (leadId: number) => {
    setEnrichingIds((current) => [...current, leadId]);
    try {
      const response = await apiFetch('/api/leads/' + leadId + '/enrich', { method: 'POST' });
      const payload = await response.json();
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

  return (
    <motion.div
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
      </div>

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
                            disabled={isEnriching}
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
