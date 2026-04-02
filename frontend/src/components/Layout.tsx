import React from 'react';
import {
  Activity,
  Bell,
  Construction,
  FileCheck,
  HelpCircle,
  History,
  LayoutGrid,
  Search,
  Settings,
  User,
} from 'lucide-react';
import { AppTab, BackendHealth, NavItem } from '../types';

const NAV_ITEMS: NavItem[] = [
  { id: 'queue', label: 'Review Queue', icon: LayoutGrid },
  { id: 'detail', label: 'Case Detail', icon: FileCheck },
  { id: 'history', label: 'Decision History', icon: History },
  { id: 'runs', label: 'Ingestion Runs', icon: Activity },
  { id: 'repair', label: 'Future Repair Queue', icon: Construction, disabled: true },
];

const TOP_TABS: Array<{ id: AppTab; label: string }> = [
  { id: 'queue', label: 'Review Operations' },
  { id: 'history', label: 'Decision History' },
  { id: 'runs', label: 'Ingestion Runs' },
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
                  disabled={item.disabled}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-sm transition-colors text-sm font-medium ${
                    activeTab === item.id
                      ? 'bg-stone-200 text-civic-blue font-bold border-r-2 border-civic-blue'
                      : item.disabled
                        ? 'text-slate-400 cursor-not-allowed opacity-50'
                        : 'text-slate-600 hover:bg-stone-200 hover:text-civic-blue'
                  }`}
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                  {item.disabled && <span className="ml-auto text-[8px] bg-stone-300 px-1 rounded">SOON</span>}
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
          <button className="w-full flex items-center gap-3 px-3 py-2 text-slate-500 hover:text-civic-blue text-sm transition-colors">
            <Settings size={16} />
            <span>Settings</span>
          </button>

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
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3 bg-stone-100 px-3 py-1.5 rounded-sm border border-stone-200">
              <Search size={16} className="text-slate-400" />
              <input
                type="text"
                placeholder="Search case ID, road, or ward..."
                className="bg-transparent border-none text-xs focus:ring-0 w-64 text-slate-900 placeholder:text-slate-400"
                readOnly
              />
            </div>
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
          </div>

          <div className="flex items-center gap-4 text-slate-500">
            <button className="hover:text-civic-blue transition-colors">
              <Bell size={18} />
            </button>
            <button className="hover:text-civic-blue transition-colors">
              <HelpCircle size={18} />
            </button>
            <button className="hover:text-civic-blue transition-colors">
              <User size={18} />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-stone-50">{children}</main>
      </div>
    </div>
  );
}
