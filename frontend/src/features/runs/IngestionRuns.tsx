import React from 'react';
import { Activity, CalendarRange, FileStack, RefreshCw, ShieldCheck } from 'lucide-react';
import { BackendHealth, RoadCase } from '../../shared/types/app';
import { formatDate, pipelineLabel, pipelineStatusClass, sourceLabel } from '../../shared/lib/caseDisplay';

interface IngestionRunsProps {
  cases: RoadCase[];
  health: BackendHealth | null;
  onRefresh: () => Promise<void>;
}

interface DailyArchiveSummary {
  day: string;
  inspections: number;
  detections: number;
  noticeReady: number;
  failed: number;
}

interface SegmentSummary {
  roadSegment: string;
  inspections: number;
  detections: number;
}

function summarizeByDay(cases: RoadCase[]): DailyArchiveSummary[] {
  const grouped = new Map<string, RoadCase[]>();
  cases.forEach((item) => {
    const day = item.created.slice(0, 10);
    grouped.set(day, [...(grouped.get(day) || []), item]);
  });

  return Array.from(grouped.entries())
    .sort((l, r) => r[0].localeCompare(l[0]))
    .map(([day, dayCases]) => ({
      day,
      inspections: dayCases.length,
      detections:  dayCases.reduce((t, c) => t + c.totalDetections, 0),
      noticeReady: dayCases.filter((c) => Boolean(c.noticeUrl)).length,
      failed:      dayCases.filter((c) => c.pipelineStatus === 'FAILED').length,
    }));
}

function summarizeBySegment(cases: RoadCase[]): SegmentSummary[] {
  const grouped = new Map<string, SegmentSummary>();
  cases.forEach((item) => {
    const cur = grouped.get(item.roadSegment) || { roadSegment: item.roadSegment, inspections: 0, detections: 0 };
    cur.inspections += 1;
    cur.detections  += item.totalDetections;
    grouped.set(item.roadSegment, cur);
  });
  return Array.from(grouped.values())
    .sort((l, r) => r.inspections - l.inspections || r.detections - l.detections)
    .slice(0, 5);
}

function buildDailyBars(cases: RoadCase[]) {
  const byDay = new Map<string, number>();
  cases.forEach((c) => {
    const day = c.created.slice(0, 10);
    byDay.set(day, (byDay.get(day) || 0) + 1);
  });
  const today = new Date();
  return Array.from({ length: 7 }).map((_, i) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - i));
    const key = date.toISOString().slice(0, 10);
    return { key, label: date.toLocaleDateString(undefined, { month: 'short', day: '2-digit' }), value: byDay.get(key) || 0 };
  });
}

export default function IngestionRuns({ cases, health, onRefresh }: IngestionRunsProps) {
  const dailySummary  = summarizeByDay(cases);
  const segmentSummary = summarizeBySegment(cases);
  const bars          = buildDailyBars(cases);
  const maxBarValue   = Math.max(...bars.map((b) => b.value), 1);
  const noticeReady   = cases.filter((c) => Boolean(c.noticeUrl)).length;
  const failedInsp    = cases.filter((c) => c.pipelineStatus === 'FAILED').length;

  // Most recent 8 cases for the "Recent Ingestions" table
  const recentCases = [...cases]
    .sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime())
    .slice(0, 8);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-headline font-bold tracking-tight mb-1"
              style={{ color: 'var(--color-authority-blue)' }}>
            Archive Summary
          </h1>
          <p className="text-ink-soft text-sm">
            Summarised view of stored inspections from the backend archive.
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={onRefresh}>
          <RefreshCw size={13} />
          Refresh Data
        </button>
      </div>

      {/* Chart + health panel */}
      <div className="grid grid-cols-12 gap-6 mb-8">
        <div className="col-span-8 surface-base p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">7-Day Inspection Volume</h3>
            <span className="text-[9px] mono-text font-bold px-2 py-0.5 border border-hairline rounded-sm text-ink-soft">
              TOTAL: {cases.length}
            </span>
          </div>
          <div className="h-44 flex items-end gap-3 px-2">
            {bars.map((item, i) => (
              <div key={item.key} className="flex-1 flex flex-col items-center gap-2">
                <div
                  className="w-full rounded-t-sm transition-all duration-500"
                  style={{
                    height: `${Math.max(6, (item.value / maxBarValue) * 100)}%`,
                    background: i === bars.length - 1 ? 'var(--color-authority-blue)' : 'var(--color-hairline)',
                  }}
                />
                <span className="text-[8px] mono-text text-ink-soft">{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-4 text-white p-5 rounded-sm flex flex-col justify-between"
             style={{ background: 'var(--color-authority-blue)' }}>
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Activity size={16} className="opacity-60" />
              <h3 className="text-[9px] font-bold uppercase tracking-widest opacity-60">Backend Readiness</h3>
            </div>
            <div className="text-3xl font-headline font-bold mb-1">
              {health?.status === 'ok' ? 'Operational' : 'Checking'}
            </div>
            <div className="flex items-center gap-2 text-[9px] font-medium opacity-70">
              <div className={`w-1.5 h-1.5 rounded-full ${health?.model_loaded ? 'bg-green-300 animate-pulse' : 'bg-orange-300'}`} />
              {health?.model_loaded ? 'Detection model ready' : 'Archive available without model'}
            </div>
          </div>
          <div className="space-y-2 pt-5 border-t border-white/10">
            {[
              { label: 'Version',     value: health?.version ?? 'N/A' },
              { label: 'Active Days', value: dailySummary.length },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between text-[9px]">
                <span className="opacity-60">{label}</span>
                <span className="mono-text font-bold">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {[
          { icon: FileStack,    label: 'Archive Health',     value: cases.length,  desc: 'Stored inspections available for review.' },
          { icon: ShieldCheck,  label: 'Notice Ready',       value: noticeReady,   desc: 'Inspections qualifying for notice generation.' },
          { icon: CalendarRange,label: 'Pipeline Failures',  value: failedInsp,    desc: 'Logged failures visible for manual follow-up.' },
        ].map(({ icon: Icon, label, value, desc }) => (
          <div key={label} className="surface-base p-5 border-l-4" style={{ borderColor: 'var(--color-authority-blue)' }}>
            <div className="flex items-center gap-2 mb-3 text-[9px] font-bold uppercase tracking-widest text-ink-soft">
              <Icon size={13} style={{ color: 'var(--color-authority-blue)' }} />
              {label}
            </div>
            <div className="text-3xl font-bold mono-text mb-2" style={{ color: 'var(--color-authority-blue)' }}>{value}</div>
            <div className="text-xs text-ink-soft">{desc}</div>
          </div>
        ))}
      </div>

      {/* Daily archive groups */}
      <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-4">Daily Archive Groups</h3>
      <div className="grid grid-cols-3 gap-6 mb-8">
        {dailySummary.slice(0, 3).map((day) => (
          <div key={day.day} className="surface-base p-5 border-l-4" style={{ borderColor: 'var(--color-authority-blue)' }}>
            <div className="text-[9px] mono-text font-bold mb-1" style={{ color: 'var(--color-authority-blue)' }}>{day.day}</div>
            <div className="text-sm font-bold text-ink mb-4">Activity Snapshot</div>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Inspections', value: day.inspections },
                { label: 'Detections',  value: day.detections  },
                { label: 'Notice Ready',value: day.noticeReady },
                { label: 'Failed',      value: day.failed      },
              ].map(({ label, value }) => (
                <div key={label} className="surface-nested p-2">
                  <div className="text-[7px] font-bold text-ink-soft uppercase mb-0.5">{label}</div>
                  <div className="text-xs mono-text font-bold">{value}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Main table + scope note */}
      <div className="grid grid-cols-12 gap-6 mb-8">
        <div className="col-span-8 surface-base overflow-hidden">
          <div className="px-4 py-3 bg-stone-100 border-b border-hairline">
            <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Most Active Road Segments</h3>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[8px] font-bold uppercase text-ink-soft border-b border-hairline">
                <th className="px-4 py-2">Road Segment</th>
                <th className="px-4 py-2">Inspections</th>
                <th className="px-4 py-2">Detections</th>
              </tr>
            </thead>
            <tbody className="text-[10px] mono-text">
              {segmentSummary.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-8 text-center text-ink-soft">No archived inspections yet.</td></tr>
              ) : (
                segmentSummary.map((s) => (
                  <tr key={s.roadSegment} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-3 font-bold" style={{ color: 'var(--color-authority-blue)' }}>{s.roadSegment}</td>
                    <td className="px-4 py-3 text-ink-soft">{s.inspections}</td>
                    <td className="px-4 py-3 text-ink-soft">{s.detections}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="col-span-4 surface-base p-5 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={13} style={{ color: 'var(--color-authority-blue)' }} />
            <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">View Scope</h3>
          </div>
          <div className="surface-nested p-4 text-xs text-ink-soft leading-relaxed flex-1">
            <p className="mb-3">This tab summarises stored inspections rather than pretending there is a backend ingestion-run system.</p>
            <p className="mb-3">Use it to sanity-check archive volume, notice-ready cases, and segment concentration.</p>
            <p>A future backend release can replace this summary with first-class ingestion entities without changing the rest of the review console.</p>
          </div>
        </div>
      </div>

      {/* Recent Ingestions — with Source column */}
      <div className="surface-base overflow-hidden">
        <div className="px-4 py-3 bg-stone-100 border-b border-hairline">
          <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Recent Ingestions</h3>
        </div>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="text-[8px] font-bold uppercase text-ink-soft border-b border-hairline">
              <th className="px-4 py-2">Case ID</th>
              <th className="px-4 py-2">Road Segment</th>
              <th className="px-4 py-2">Pipeline</th>
              <th className="px-4 py-2">Severity</th>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Created</th>
            </tr>
          </thead>
          <tbody className="text-xs">
            {recentCases.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-soft">No recent ingestions.</td></tr>
            ) : (
              recentCases.map((c) => (
                <tr key={c.inspectionId} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                  <td className="px-4 py-3 mono-text font-bold" style={{ color: 'var(--color-authority-blue)' }}>{c.id}</td>
                  <td className="px-4 py-3 font-medium">{c.roadSegment}</td>
                  <td className="px-4 py-3">
                    <span className={pipelineStatusClass(c.pipelineStatus)}>
                      <span className="pipeline-dot" />
                      {pipelineLabel(c.pipelineStatus)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge badge-${c.severity.toLowerCase()}`}>{c.severity}</span>
                  </td>
                  <td className="px-4 py-3 text-ink-soft text-[10px]">{sourceLabel(c.source)}</td>
                  <td className="px-4 py-3 text-ink-soft mono-text">{formatDate(c.created)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
