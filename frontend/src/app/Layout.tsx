import React from 'react';
import { Activity, FileCheck, History, LayoutGrid, Map, Inbox } from 'lucide-react';

import { AppTab, BackendHealth, NavItem } from '../shared/types/app';

const NAV_ITEMS: NavItem[] = [
  { id: 'queue',    label: 'Review Queue',     icon: LayoutGrid },
  { id: 'detail',   label: 'Case Detail',       icon: FileCheck },
  { id: 'history',  label: 'Decision History',  icon: History },
  { id: 'runs',     label: 'Archive Summary',   icon: Activity },
  { id: 'intake',   label: 'Intake',            icon: Inbox },
  { id: 'segments', label: 'Road Segments',     icon: Map },
];

interface LayoutProps {
  children: React.ReactNode;
  activeTab: AppTab;
  setActiveTab: (tab: AppTab) => void;
  health: BackendHealth | null;
}

export default function Layout({ children, activeTab, setActiveTab, health }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-60 bg-paper border-r border-hairline flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-hairline">
          <div
            className="text-lg font-headline font-bold tracking-tighter uppercase"
            style={{ color: 'var(--color-authority-blue)' }}
          >
            A.R.I.A.
          </div>
          <div className="text-[9px] text-ink-soft uppercase tracking-widest font-bold mt-0.5">
            District Operations
          </div>
        </div>

        <nav className="flex-1 py-3 overflow-y-auto">
          <ul className="space-y-0.5 px-2">
            {NAV_ITEMS.map((item) => {
              const isActive = activeTab === item.id ||
                (activeTab === 'detail' && item.id === 'queue');
              return (
                <li key={item.id}>
                  <button
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-sm transition-colors text-xs font-medium ${
                      isActive
                        ? 'bg-stone-200 font-bold border-l-2'
                        : 'text-ink-soft hover:bg-stone-100 hover:text-ink'
                    }`}
                    style={isActive ? {
                      color: 'var(--color-authority-blue)',
                      borderColor: 'var(--color-authority-blue)',
                    } : {}}
                  >
                    <item.icon size={15} />
                    <span>{item.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* System health — no fake persona */}
        <div className="p-4 border-t border-hairline">
          <div className="flex items-center justify-between px-1 text-xs text-ink-soft">
            <div className="flex items-center gap-2">
              <Activity size={13} />
              <span className="text-[10px] font-medium uppercase tracking-wider">System</span>
            </div>
            <span
              className="text-[9px] font-bold uppercase tracking-wider"
              style={{ color: health?.model_loaded ? '#2d6a4f' : 'var(--color-hazard-amber)' }}
            >
              {health ? (health.model_loaded ? 'Ready' : 'Archive Only') : '—'}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-12 bg-white border-b border-hairline flex items-center justify-between px-6 shrink-0">
          <span
            className="text-[10px] font-headline font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-authority-blue)' }}
          >
            {NAV_ITEMS.find((n) => n.id === activeTab || (activeTab === 'detail' && n.id === 'queue'))?.label ?? ''}
          </span>

          <div className="flex items-center gap-2 text-[9px] uppercase tracking-widest">
            <span className="rounded-sm border border-hairline bg-paper px-2 py-0.5 text-ink-soft">
              API Protected
            </span>
            <span
              className="rounded-sm border px-2 py-0.5 font-bold"
              style={health?.model_loaded
                ? { borderColor: '#b7e4c7', background: '#d8f3dc', color: '#2d6a4f' }
                : { borderColor: 'var(--color-hairline)', background: 'var(--color-paper)', color: 'var(--color-hazard-amber)' }}
            >
              {health?.model_loaded ? 'Model Ready' : 'Archive Only'}
            </span>
            <span className="rounded-sm border border-hairline bg-paper px-2 py-0.5 text-ink-soft mono-text">
              {health?.version ?? 'N/A'}
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-paper">{children}</main>
      </div>
    </div>
  );
}
