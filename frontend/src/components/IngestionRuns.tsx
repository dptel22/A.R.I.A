import React from 'react';
import { Activity, ArrowRight, CheckCircle2, Clock, Download, Globe, RefreshCw } from 'lucide-react';
import { BackendHealth, DerivedRun, RoadCase } from '../types';

interface IngestionRunsProps {
  cases: RoadCase[];
  health: BackendHealth | null;
  onRefresh: () => Promise<void>;
}

function deriveRuns(cases: RoadCase[]): DerivedRun[] {
  const grouped = new Map<string, RoadCase[]>();

  cases.forEach((item) => {
    const day = item.created.slice(0, 10);
    const bucket = grouped.get(day) || [];
    bucket.push(item);
    grouped.set(day, bucket);
  });

  return Array.from(grouped.entries())
    .sort((left, right) => right[0].localeCompare(left[0]))
    .map(([day, dayCases]) => ({
      id: `RUN-${day}`,
      name: 'Derived Inspection Batch',
      timestamp: `${day} 02:00`,
      status: 'Successful' as const,
      inspections: dayCases.length,
      detections: dayCases.reduce((total, item) => total + item.totalDetections, 0),
      dlpActiveCases: dayCases.filter((item) => item.dlpStatus === 'Active').length,
      duration: `${Math.max(1, dayCases.length * 2)}m`,
      region: dayCases[0]?.zoneId || 'UNKNOWN',
      load: Math.min(95, Math.max(20, dayCases.length * 12)),
    }));
}

function buildDailyBars(cases: RoadCase[]) {
  const byDay = new Map<string, number>();
  cases.forEach((item) => {
    const day = item.created.slice(0, 10);
    byDay.set(day, (byDay.get(day) || 0) + 1);
  });

  const today = new Date();
  return Array.from({ length: 7 }).map((_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    const key = date.toISOString().slice(0, 10);
    return {
      key,
      label: date.toLocaleDateString(undefined, { month: 'short', day: '2-digit' }),
      value: byDay.get(key) || 0,
    };
  });
}

export default function IngestionRuns({ cases, health, onRefresh }: IngestionRunsProps) {
  const runs = deriveRuns(cases);
  const bars = buildDailyBars(cases);
  const maxBarValue = Math.max(...bars.map((item) => item.value), 1);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-civic-blue mb-1">Ingestion Run Overview</h1>
          <p className="text-slate-500 text-sm">
            Derived from the current inspection archive until dedicated ingestion-run endpoints are added.
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={onRefresh}>
          <RefreshCw size={14} />
          Refresh Data
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6 mb-8">
        <div className="col-span-8 surface-base p-6 relative overflow-hidden">
          <div className="grid-bg absolute inset-0"></div>
          <div className="relative z-10">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">7-Day Inspection Volume</h3>
              <span className="text-[10px] font-mono font-bold text-civic-blue bg-blue-50 px-2 py-0.5 rounded">
                TOTAL: {cases.length} INSPECTIONS
              </span>
            </div>
            <div className="h-48 flex items-end gap-3 px-4">
              {bars.map((item, index) => (
                <div key={item.key} className="flex-1 flex flex-col items-center gap-2">
                  <div
                    className={`w-full rounded-t-sm transition-all duration-500 ${index === bars.length - 1 ? 'bg-civic-blue' : 'bg-stone-200'}`}
                    style={{ height: `${Math.max(8, (item.value / maxBarValue) * 100)}%` }}
                  ></div>
                  <span className="text-[8px] font-mono text-slate-400">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-4 bg-civic-blue text-white p-6 rounded-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Activity size={18} className="text-blue-300" />
              <h3 className="text-[10px] font-bold uppercase tracking-widest opacity-70">Ingestion Engine</h3>
            </div>
            <div className="text-3xl font-bold mb-1">{health?.status === 'ok' ? 'Operational' : 'Checking'}</div>
            <div className="flex items-center gap-2 text-[10px] font-medium text-blue-200">
              <div className={`w-2 h-2 rounded-full ${health?.model_loaded ? 'bg-green-400 animate-pulse' : 'bg-orange-300'}`}></div>
              {health?.model_loaded ? 'Detection model ready' : 'Model not loaded'}
            </div>
          </div>

          <div className="space-y-3 pt-6 border-t border-white/10">
            <div className="flex justify-between text-[10px]">
              <span className="opacity-60">Backend Version</span>
              <span className="font-mono font-bold">{health?.version || 'N/A'}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="opacity-60">Recent Runs</span>
              <span className="font-mono font-bold">{runs.length}</span>
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Recent Derived Runs</h3>
      <div className="grid grid-cols-3 gap-6 mb-8">
        {runs.slice(0, 3).map((run) => (
          <div key={run.id} className="surface-base p-5 border-l-4 border-civic-blue">
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="text-[10px] font-mono font-bold text-civic-blue mb-1">{run.id}</div>
                <div className="text-sm font-bold text-slate-900">{run.name}</div>
              </div>
              <span className="badge bg-green-50 text-green-600 border-green-100">{run.status}</span>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-6">
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Inspections</div>
                <div className="text-xs font-mono font-bold">{run.inspections.toLocaleString()}</div>
              </div>
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Detections</div>
                <div className="text-xs font-mono font-bold">{run.detections.toLocaleString()}</div>
              </div>
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">DLP Active</div>
                <div className="text-xs font-mono font-bold">{run.dlpActiveCases}</div>
              </div>
              <div className="surface-nested p-2 bg-blue-50 border-blue-100">
                <div className="text-[8px] font-bold text-blue-600 uppercase mb-1">Region</div>
                <div className="text-xs font-mono font-bold text-blue-700">{run.region}</div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-stone-100 text-[10px] text-slate-400 font-mono">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {run.timestamp.slice(11)}
                </span>
                <span className="flex items-center gap-1">
                  <Activity size={12} /> {run.duration}
                </span>
              </div>
              <span className="text-civic-blue font-bold flex items-center gap-1">
                View Queue <ArrowRight size={12} />
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-8 surface-base overflow-hidden">
          <div className="px-4 py-3 bg-stone-100 border-b border-stone-200 flex justify-between items-center">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Run Logs</h3>
            <button className="text-[10px] font-bold text-slate-400 flex items-center gap-1" disabled>
              <Download size={12} /> Export CSV
            </button>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[9px] font-bold uppercase text-slate-400 border-b border-stone-100">
                <th className="px-4 py-2">Identifier</th>
                <th className="px-4 py-2">Source Region</th>
                <th className="px-4 py-2">Processing Load</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="text-[10px] font-mono">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                    No archived inspections yet.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.id} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-3 font-bold text-civic-blue">{run.id}</td>
                    <td className="px-4 py-3 text-slate-600">{run.region}</td>
                    <td className="px-4 py-3">
                      <div className="w-24 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                        <div className="h-full bg-civic-blue" style={{ width: `${run.load}%` }}></div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-green-600">
                        <CheckCircle2 size={10} /> OK
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="col-span-4 surface-base p-6 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Globe size={14} className="text-civic-blue" />
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Source Coverage</h3>
          </div>
          <div className="flex-1 bg-stone-200 rounded-sm relative overflow-hidden min-h-[200px]">
            <div className="grid-bg absolute inset-0"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative">
                <div className="w-32 h-32 border-2 border-civic-blue/20 rounded-full absolute -inset-0"></div>
                <div className="w-32 h-32 bg-civic-blue/5 rounded-full border border-civic-blue/30 flex items-center justify-center">
                  <div className="text-xs font-bold text-civic-blue uppercase">{cases[0]?.zoneId || 'No data'}</div>
                </div>
              </div>
            </div>
            <div className="absolute bottom-3 left-3 bg-white/80 p-2 rounded-sm text-[8px] font-bold uppercase border border-stone-200">
              Derived from stored inspection coordinates
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 surface-base p-6 bg-slate-900 text-blue-100 rounded-sm font-mono text-[10px]">
        <div className="flex items-center gap-2 mb-4 opacity-50">
          <Activity size={12} />
          <span className="uppercase tracking-widest font-bold">Engine Log Stream</span>
        </div>
        <div className="space-y-1">
          <div>
            <span className="text-blue-400">[LIVE]</span> Backend health endpoint reports status{' '}
            <span className="font-bold">{health?.status || 'unknown'}</span>.
          </div>
          <div>
            <span className="text-blue-400">[MODEL]</span> Detection model{' '}
            <span className="font-bold">{health?.model_loaded ? 'available' : 'not loaded'}</span>.
          </div>
          <div>
            <span className="text-blue-400">[QUEUE]</span> Stored inspections in archive: {cases.length}.
          </div>
          <div>
            <span className="text-blue-400">[CASES]</span> Total detected defects across archive:{' '}
            {cases.reduce((total, item) => total + item.totalDetections, 0)}.
          </div>
        </div>
      </div>
    </div>
  );
}
