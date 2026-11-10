import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, CheckCircle, ExternalLink, FileCode, Terminal } from 'lucide-react';
import toast from 'react-hot-toast';

interface ScriptDisplayProps {
  sheetUrl?: string;
}

export default function ScriptDisplay({ sheetUrl }: ScriptDisplayProps) {
  const [copied, setCopied] = useState(false);
  const [script, setScript] = useState('Loading script…');

  useEffect(() => {
    let cancelled = false;
    fetch('/apps_script.gs')
      .then((res) => {
        if (!res.ok) throw new Error('missing script');
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setScript(text);
      })
      .catch(() => {
        if (!cancelled) setScript('Could not load the script. It is also saved in the repo at scripts/apps_script.gs.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(script);
      setCopied(true);
      toast.success('Script copied');
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error('Failed to copy');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5"
    >
      {sheetUrl && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-panel p-5 border-jade/30 flex items-center gap-4"
        >
          <div className="w-10 h-10 rounded-xl bg-jade/10 flex items-center justify-center shrink-0">
            <CheckCircle className="w-5 h-5 text-jade" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-pearl">Sheet created</p>
            <a
              href={sheetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-frost hover:underline inline-flex items-center gap-1 mt-0.5"
            >
              Open in Google Sheets <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </motion.div>
      )}

      <div className="glass-panel overflow-hidden">
        <div className="p-5 border-b border-edge/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-frost/10 flex items-center justify-center">
              <FileCode className="w-4.5 h-4.5 text-frost" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-pearl">Draft script</h2>
              <p className="text-xs text-muted">Optional. Creates Gmail drafts. It does not send them.</p>
            </div>
          </div>
          <motion.button
            onClick={handleCopy}
            className="btn-primary text-sm"
            whileTap={{ scale: 0.95 }}
          >
            {copied ? (
              <><CheckCircle className="w-4 h-4" /> Copied</>
            ) : (
              <><Copy className="w-4 h-4" /> Copy Script</>
            )}
          </motion.button>
        </div>

        <div className="relative">
          <div className="flex items-center gap-2 px-5 py-2 bg-[#050508] border-b border-edge/10">
            <Terminal className="w-3.5 h-3.5 text-muted" />
            <span className="text-[11px] text-muted font-mono">apps_script.gs</span>
          </div>
          <pre className="code-block max-h-[420px] overflow-y-auto rounded-none border-0">
            <code>{script}</code>
          </pre>
        </div>
      </div>

      <div className="glass-panel-light p-5">
        <h3 className="text-sm font-semibold text-pearl mb-3 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-ember" />
          Make drafts, then send them yourself
        </h3>
        <ol className="space-y-2 text-sm text-muted">
          {[
            'Open the Google Sheet and type each business email into the Email column. Google does not provide these.',
            'Go to Extensions → Apps Script',
            'Delete the sample code and paste this script',
            'Change SENDER_NAME to your name and save',
            'Run createDrafts. If Google asks, allow it to create drafts.',
            'Open Gmail → Drafts, read each one, and send it yourself. This script never sends mail.',
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-ember/10 text-ember text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </motion.div>
  );
}
