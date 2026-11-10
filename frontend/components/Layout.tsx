import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Users, FileSpreadsheet, Zap, Menu, ChevronRight, Clock } from 'lucide-react';
import { useState, ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
  campaignId?: string | null;
}

export default function Layout({ children, campaignId }: LayoutProps) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-obsidian flex">
      <aside className={`fixed lg:sticky top-0 left-0 z-50 h-screen w-64 bg-abyss border-r border-edge/30 flex flex-col transition-transform duration-300 lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-5 border-b border-edge/20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-ember to-amber-500 flex items-center justify-center">
              <Zap className="w-4 h-4 text-black" />
            </div>
            <div>
              <span className="font-display font-bold text-lg text-pearl">LocalWeb<span className="text-ember"> Leads</span></span>
              <span className="block text-[10px] text-muted uppercase tracking-widest mt-0.5">Business Finder</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          <button
            onClick={() => { router.push('/'); setSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${router.pathname === '/' ? 'bg-ember/10 text-ember border border-ember/20' : 'text-muted hover:text-pearl hover:bg-white/5'}`}
          >
            <Search className="w-4 h-4" />
            New Search
          </button>

          <button
            onClick={() => { router.push('/campaigns'); setSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${router.pathname === '/campaigns' ? 'bg-ember/10 text-ember border border-ember/20' : 'text-muted hover:text-pearl hover:bg-white/5'}`}
          >
            <Clock className="w-4 h-4" />
            Search History
          </button>

          {campaignId && (
            <>
              <button
                onClick={() => { router.push('/campaigns/' + campaignId); setSidebarOpen(false); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${router.pathname.includes('campaigns') ? 'bg-ember/10 text-ember border border-ember/20' : 'text-muted hover:text-pearl hover:bg-white/5'}`}
              >
                <Users className="w-4 h-4" />
                Leads
              </button>

              <button
                onClick={() => { router.push('/export/' + campaignId); setSidebarOpen(false); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${router.pathname.includes('export') ? 'bg-ember/10 text-ember border border-ember/20' : 'text-muted hover:text-pearl hover:bg-white/5'}`}
              >
                <FileSpreadsheet className="w-4 h-4" />
                Export
              </button>
            </>
          )}
        </nav>

        <div className="p-4 border-t border-edge/20">
          <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-shadow/50">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-jade to-emerald-500 flex items-center justify-center text-[10px] font-bold text-black">
              LW
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-pearl truncate">LocalWeb Studio</p>
              <p className="text-[10px] text-muted">Lead research workspace</p>
            </div>
            <div className="w-2 h-2 rounded-full bg-success" />
          </div>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <div className="flex-1 flex flex-col min-h-screen">
        <header className="sticky top-0 z-30 bg-obsidian/80 backdrop-blur-xl border-b border-edge/20">
          <div className="flex items-center justify-between px-4 lg:px-8 h-14">
            <button className="lg:hidden btn-icon btn-ghost" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-5 h-5" />
            </button>
            <div className="hidden lg:flex items-center gap-2 text-sm text-muted">
              <span className="text-pearl font-medium">LocalWeb Leads</span>
              {campaignId && <><ChevronRight className="w-3 h-3" /><span>Search #{campaignId}</span></>}
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-shadow/50 rounded-full border border-edge/20">
                <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-xs text-muted">Ready</span>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={router.asPath}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
