import React from 'react';
import { Activity, FileCheck, History, LayoutGrid } from 'lucide-react';

import { AppTab, BackendHealth, NavItem } from '../shared/types/app';

const NAV_ITEMS: NavItem[] = [
  { id: 'queue', label: 'Review Queue', icon: LayoutGrid },
  { id: 'detail', label: 'Case Detail', icon: FileCheck },
  { id: 'history', label: 'Decision History', icon: History },
  { id: 'runs', label: 'Archive Summary', icon: Activity },
];

const TOP_TABS: Array<{ id: AppTab; label: string }> = [
  { id: 'queue', label: 'Review Operations' },
  { id: 'history', label: 'Decision History' },
  { id: 'runs', label: 'Archive Summary' },
];

interface LayoutProps {
  children: React.ReactNode;
  activeTab: AppTab;
  setActiveTab: (tab: AppTab) => void;
  health: BackendHealth | null;
}

export default function Layout({ children, activeTab, setActiveTab, health }: LayoutProps) {
  const activeTopTab: AppTab = activeTab === 'detail' ? 'queue' : activeTab;

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-64 bg-stone-100 border-r border-stone-200 flex flex-col shrink-0">
        <div className="p-6 border-b border-stone-200">
          <div className="text-xl font-bold tracking-tighter text-civic-blue uppercase">A.R.I.A.</div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">District Operations</div>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          <ul className="space-y-1 px-3">
            {NAV_ITEMS.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-sm transition-colors text-sm font-medium ${
                    activeTab === item.id
                      ? 'bg-stone-200 text-civic-blue font-bold border-r-2 border-civic-blue'
                      : 'text-slate-600 hover:bg-stone-200 hover:text-civic-blue'
                  }`}
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-stone-200 space-y-1">
          <div className="w-full flex items-center justify-between px-3 py-2 text-sm text-slate-500">
            <div className="flex items-center gap-3">
              <Activity size={16} />
              <span>System Health</span>
            </div>
            <span
              className={`text-[10px] font-bold uppercase tracking-wider ${
                health?.model_loaded ? 'text-green-600' : 'text-orange-600'
              }`}
            >
              {health ? (health.model_loaded ? 'Model Ready' : 'Model Offline') : 'Checking'}
            </span>
          </div>
          <div className="mt-4 pt-4 border-t border-stone-200 flex items-center gap-3">
            <div className="w-8 h-8 bg-civic-blue rounded-sm flex items-center justify-center text-[10px] text-white font-bold">ME</div>
            <div>
              <div className="text-xs font-bold text-slate-900">M. Engineer</div>
              <div className="text-[10px] text-slate-500 mono-text">ID: OPS-8842</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 bg-white border-b border-stone-200 flex items-center justify-between px-6 shrink-0">
          <nav className="flex gap-6">
            {TOP_TABS.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`text-xs font-medium transition-colors ${
                  activeTopTab === item.id ? 'text-civic-blue font-bold' : 'text-slate-500 hover:text-civic-blue'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-3 text-[10px] uppercase tracking-widest">
            <span className="rounded-sm border border-stone-200 bg-stone-100 px-2 py-1 text-slate-500">API Protected</span>
            <span className={`rounded-sm border px-2 py-1 font-bold ${health?.model_loaded ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-orange-200 bg-orange-50 text-orange-700'}`}>
              {health?.model_loaded ? 'Model Ready' : 'Archive Only'}
            </span>
            <span className="rounded-sm border border-stone-200 bg-stone-100 px-2 py-1 text-slate-500">
              Version {health?.version || 'N/A'}
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-stone-50">{children}</main>
      </div>
    </div>
  );
}
