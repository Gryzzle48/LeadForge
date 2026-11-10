import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Edit3, Mail, Star, ChevronDown, ChevronUp, MessageSquare, Phone, RefreshCw } from 'lucide-react';
import StatusBadge from './StatusBadge';
import { apiFetch } from '../lib/api';
import toast from 'react-hot-toast';

interface Lead {
  id: number;
  name: string;
  category?: string;
  address?: string;
  maps_url?: string;
  website_uri?: string;
  rating?: number;
  review_count?: number;
  phone?: string;
  email?: string;
  email_subject?: string;
  email_body?: string;
}

interface ResultsTableProps {
  leads: Lead[];
  campaignId: number | string;
}

export default function ResultsTable({ leads, campaignId }: ResultsTableProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [localLeads, setLocalLeads] = useState<Lead[]>(leads);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    setLocalLeads(leads);
  }, [leads]);

  const handleEdit = (lead: Lead) => {
    setEditingId(lead.id);
    setEdits({
      email: lead.email || '',
      email_subject: lead.email_subject || '',
      email_body: lead.email_body || '',
    });
  };

  const handleSave = async (leadId: number) => {
    try {
      const res = await apiFetch(`/api/leads/${leadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(edits),
      });
      if (res.ok) {
        setLocalLeads((prev) =>
          prev.map((l) => (l.id === leadId ? { ...l, ...edits } : l))
        );
        setEditingId(null);
        toast.success('Saved');
      } else {
        toast.error('Save failed');
      }
    } catch {
      toast.error('Failed to save');
    }
  };

  const handleRegenerateEmail = async (leadId: number) => {
    try {
      const res = await apiFetch(`/api/leads/${leadId}/regenerate-email`, { method: 'POST' });
      if (res.ok) {
        const updated = await res.json();
        setLocalLeads((prev) =>
          prev.map((l) => (l.id === leadId ? { ...l, ...updated } : l))
        );
        toast.success('Email regenerated');
      } else {
        toast.error('Regeneration failed');
      }
    } catch {
      toast.error('Failed to regenerate email');
    }
  };

  const handleCancel = () => {
    setEditingId(null);
    setEdits({});
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
            <Mail className="w-4.5 h-4.5 text-jade" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-pearl">Leads</h2>
            <p className="text-xs text-muted">{localLeads?.length || 0} businesses with no website. Add an email in the sheet before creating a draft.</p>
          </div>
        </div>
      </div>

      {(!localLeads || localLeads.length === 0) ? (
        <div className="flex flex-col items-center justify-center py-20 px-4">
          <MessageSquare className="w-12 h-12 text-muted/30 mb-4" />
          <p className="text-muted text-sm">No leads yet. Start a new search above.</p>
        </div>
      ) : (
        <div className="table-wrap border-0 rounded-none">
          <table>
            <thead>
              <tr>
                <th style={{ width: 30 }} />
                <th>Business</th>
                <th>Category</th>
                <th>Rating</th>
                <th>Contact</th>
                <th>Email</th>
                <th>Subject / Body</th>
                <th style={{ width: 100 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {localLeads.map((lead, i) => (
                <motion.tr
                  key={lead.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <td>
                    <button
                      className="btn-icon btn-ghost"
                      onClick={() => setExpandedId(expandedId === lead.id ? null : lead.id)}
                    >
                      {expandedId === lead.id
                        ? <ChevronUp className="w-3.5 h-3.5" />
                        : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  </td>
                  <td className="font-medium">
                    <div>{lead.name}</div>
                    {lead.address && (
                      <div className="text-xs text-muted font-normal mt-0.5 max-w-xs">{lead.address}</div>
                    )}
                    <div className="text-[11px] mt-0.5">
                      {lead.maps_url ? (
                        <a href={lead.maps_url} target="_blank" rel="noopener noreferrer" className="text-frost hover:underline">Map</a>
                      ) : null}
                      <span className="text-muted">{lead.maps_url ? ' · ' : ''}No website</span>
                    </div>
                  </td>
                  <td>
                    <span className="text-xs text-muted bg-shadow/50 px-2 py-1 rounded-md">
                      {lead.category || '—'}
                    </span>
                  </td>
                  <td>
                    {lead.rating != null ? (
                      <span className="flex items-center gap-1 text-amber-400 text-sm">
                        <Star className="w-3.5 h-3.5 fill-current" />
                        {lead.rating}
                        {lead.review_count != null && (
                          <span className="text-muted text-xs ml-1">({lead.review_count})</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-muted text-xs">—</span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2 text-xs text-muted">
                      {lead.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="w-3 h-3" /> {lead.phone}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    {editingId === lead.id ? (
                      <input
                        type="email"
                        className="input text-xs w-40"
                        placeholder="email@example.com"
                        value={edits.email || ''}
                        onChange={(e) => setEdits({ ...edits, email: e.target.value })}
                      />
                    ) : (
                      <span className="text-xs text-muted">{lead.email || '—'}</span>
                    )}
                  </td>
                  <td className="max-w-xs">
                    {editingId === lead.id ? (
                      <div className="flex flex-col gap-1">
                        <input
                          className="input text-xs"
                          placeholder="Subject"
                          value={edits.email_subject || ''}
                          onChange={(e) => setEdits({ ...edits, email_subject: e.target.value })}
                        />
                        <textarea
                          className="input text-xs resize-none"
                          rows={2}
                          placeholder="Email body"
                          value={edits.email_body || ''}
                          onChange={(e) => setEdits({ ...edits, email_body: e.target.value })}
                        />
                      </div>
                    ) : (
                      <div className="text-xs text-muted truncate">
                        <span className="text-pearl">{lead.email_subject || 'No subject'}</span>
                      </div>
                    )}
                  </td>
                  <td>
                    {editingId === lead.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          className="btn-icon btn-ghost text-jade"
                          onClick={() => handleSave(lead.id)}
                          title="Save"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        </button>
                        <button
                          className="btn-icon btn-ghost text-muted"
                          onClick={handleCancel}
                          title="Cancel"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <button
                          className="btn-icon btn-ghost"
                          onClick={() => handleRegenerateEmail(lead.id)}
                          title="Regenerate Email"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                        <button
                          className="btn-icon btn-ghost"
                          onClick={() => handleEdit(lead)}
                          title="Edit"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
