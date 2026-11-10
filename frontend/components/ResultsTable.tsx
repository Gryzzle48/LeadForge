import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Mail, MapPin, MessageSquare, Phone, Instagram, Search, Pencil, Save, X } from 'lucide-react';
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
}

interface ContactDraft {
  phone: string;
  email: string;
  instagram_url: string;
}

interface ResultsTableProps {
  leads: Lead[];
  campaignId: string | number;
  city?: string;
  state?: string;
}

const emptyDraft: ContactDraft = { phone: '', email: '', instagram_url: '' };

const googleSearch = (query: string) =>
  'https://www.google.com/search?q=' + encodeURIComponent(query);

export default function ResultsTable({ leads, campaignId, city, state }: ResultsTableProps) {
  const [localLeads, setLocalLeads] = useState<Lead[]>(leads);
  const [editingLeadId, setEditingLeadId] = useState<number | null>(null);
  const [contactDraft, setContactDraft] = useState<ContactDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLocalLeads(leads);
  }, [leads]);

  const beginEdit = (lead: Lead) => {
    setEditingLeadId(lead.id);
    setContactDraft({
      phone: lead.phone || '',
      email: lead.email || '',
      instagram_url: lead.instagram_url || '',
    });
  };

  const cancelEdit = () => {
    setEditingLeadId(null);
    setContactDraft(emptyDraft);
  };

  const saveContacts = async (leadId: number) => {
    setSaving(true);
    try {
      const response = await apiFetch('/api/leads/' + leadId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(contactDraft),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || 'Could not save contact details.');
      }
      setLocalLeads((current) =>
        current.map((lead) => lead.id === leadId ? payload : lead)
      );
      setEditingLeadId(null);
      setContactDraft(emptyDraft);
      toast.success('Contact details saved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not save contact details');
    } finally {
      setSaving(false);
    }
  };

  const location = [city, state].filter(Boolean).join(', ');

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
        <p className="text-xs text-muted">Search contacts manually and save verified details</p>
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
                const isEditing = editingLeadId === lead.id;
                const emailQuery = '"' + lead.name + '" ' + location + ' business email contact';
                const instagramQuery = 'site:instagram.com "' + lead.name + '" ' + location;
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
                      {isEditing ? (
                        <div className="flex flex-col gap-2 min-w-[190px]">
                          <input
                            className="input text-xs py-2"
                            placeholder="Phone"
                            value={contactDraft.phone}
                            onChange={(e) => setContactDraft((draft) => ({ ...draft, phone: e.target.value }))}
                          />
                          <input
                            className="input text-xs py-2"
                            type="email"
                            placeholder="Email"
                            value={contactDraft.email}
                            onChange={(e) => setContactDraft((draft) => ({ ...draft, email: e.target.value }))}
                          />
                          <input
                            className="input text-xs py-2"
                            placeholder="Instagram profile URL"
                            value={contactDraft.instagram_url}
                            onChange={(e) => setContactDraft((draft) => ({ ...draft, instagram_url: e.target.value }))}
                          />
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => saveContacts(lead.id)}
                              disabled={saving}
                              className="inline-flex items-center gap-1 text-jade hover:underline disabled:opacity-50"
                            >
                              <Save className="w-3 h-3" /> {saving ? 'Saving…' : 'Save'}
                            </button>
                            <button
                              type="button"
                              onClick={cancelEdit}
                              disabled={saving}
                              className="inline-flex items-center gap-1 text-muted hover:underline"
                            >
                              <X className="w-3 h-3" /> Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-1 text-xs text-muted min-w-[150px]">
                          {lead.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" />{lead.phone}</span>}
                          {lead.email && <span className="inline-flex items-center gap-1"><Mail className="w-3 h-3" />{lead.email}</span>}
                          {lead.instagram_url && (
                            <a href={lead.instagram_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                              <Instagram className="w-3 h-3" />Instagram
                            </a>
                          )}
                          {!lead.phone && !lead.email && !lead.instagram_url && <span>Not added yet</span>}
                          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
                            <a
                              href={googleSearch(emailQuery)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-frost hover:underline"
                            >
                              <Search className="w-3 h-3" />Find email
                            </a>
                            <a
                              href={googleSearch(instagramQuery)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-frost hover:underline"
                            >
                              <Search className="w-3 h-3" />Find Instagram
                            </a>
                          </div>
                          <button
                            type="button"
                            onClick={() => beginEdit(lead)}
                            className="inline-flex items-center gap-1 text-muted hover:text-frost hover:underline mt-1 self-start"
                          >
                            <Pencil className="w-3 h-3" />Edit contacts
                          </button>
                        </div>
                      )}
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
