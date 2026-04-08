import React from 'react';
import { Activity, CalendarRange, FileStack, RefreshCw, ShieldCheck } from 'lucide-react';
import { BackendHealth, RoadCase } from '../types';

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
    const bucket = grouped.get(day) || [];
    bucket.push(item);
    grouped.set(day, bucket);
  });

  return Array.from(grouped.entries())
    .sort((left, right) => right[0].localeCompare(left[0]))
    .map(([day, dayCases]) => ({
      day,
      inspections: dayCases.length,
      detections: dayCases.reduce((total, item) => total + item.totalDetections, 0),
      noticeReady: dayCases.filter((item) => Boolean(item.noticeUrl)).length,
      failed: dayCases.filter((item) => item.pipelineStatus === 'FAILED').length,
    }));
}

function summarizeBySegment(cases: RoadCase[]): SegmentSummary[] {
  const grouped = new Map<string, SegmentSummary>();
  cases.forEach((item) => {
    const current = grouped.get(item.roadSegment) || {
      roadSegment: item.roadSegment,
      inspections: 0,
      detections: 0,
    };
    current.inspections += 1;
    current.detections += item.totalDetections;
    grouped.set(item.roadSegment, current);
  });

  return Array.from(grouped.values())
    .sort((left, right) => right.inspections - left.inspections || right.detections - left.detections)
    .slice(0, 5);
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
  const dailySummary = summarizeByDay(cases);
  const segmentSummary = summarizeBySegment(cases);
  const bars = buildDailyBars(cases);
  const maxBarValue = Math.max(...bars.map((item) => item.value), 1);
  const noticeReady = cases.filter((item) => Boolean(item.noticeUrl)).length;
  const failedInspections = cases.filter((item) => item.pipelineStatus === 'FAILED').length;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-civic-blue mb-1">Archive Summary</h1>
          <p className="text-slate-500 text-sm">
            This view summarizes stored inspections from the backend archive. A.R.I.A. does not yet expose first-class ingestion run tracking.
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
              <h3 className="text-[10px] font-bold uppercase tracking-widest opacity-70">Backend Readiness</h3>
            </div>
            <div className="text-3xl font-bold mb-1">{health?.status === 'ok' ? 'Operational' : 'Checking'}</div>
            <div className="flex items-center gap-2 text-[10px] font-medium text-blue-200">
              <div className={`w-2 h-2 rounded-full ${health?.model_loaded ? 'bg-green-400 animate-pulse' : 'bg-orange-300'}`}></div>
              {health?.model_loaded ? 'Detection model ready' : 'Archive available without model'}
            </div>
          </div>

          <div className="space-y-3 pt-6 border-t border-white/10">
            <div className="flex justify-between text-[10px]">
              <span className="opacity-60">Backend Version</span>
              <span className="font-mono font-bold">{health?.version || 'N/A'}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="opacity-60">Active Days</span>
              <span className="font-mono font-bold">{dailySummary.length}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="surface-base p-5 border-l-4 border-civic-blue">
          <div className="flex items-center gap-2 mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            <FileStack size={14} className="text-civic-blue" />
            Archive Health
          </div>
          <div className="text-3xl font-bold text-civic-blue mb-2">{cases.length}</div>
          <div className="text-xs text-slate-600">Stored inspections currently available for review.</div>
        </div>

        <div className="surface-base p-5 border-l-4 border-civic-blue">
          <div className="flex items-center gap-2 mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            <ShieldCheck size={14} className="text-civic-blue" />
            Notice Ready
          </div>
          <div className="text-3xl font-bold text-civic-blue mb-2">{noticeReady}</div>
          <div className="text-xs text-slate-600">Inspections that currently qualify for contractor notice generation.</div>
        </div>

        <div className="surface-base p-5 border-l-4 border-civic-blue">
          <div className="flex items-center gap-2 mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            <CalendarRange size={14} className="text-civic-blue" />
            Pipeline Failures
          </div>
          <div className="text-3xl font-bold text-civic-blue mb-2">{failedInspections}</div>
          <div className="text-xs text-slate-600">Logged failures remain visible for manual follow-up.</div>
        </div>
      </div>

      <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Daily Archive Groups</h3>
      <div className="grid grid-cols-3 gap-6 mb-8">
        {dailySummary.slice(0, 3).map((day) => (
          <div key={day.day} className="surface-base p-5 border-l-4 border-civic-blue">
            <div className="text-[10px] font-mono font-bold text-civic-blue mb-1">{day.day}</div>
            <div className="text-sm font-bold text-slate-900 mb-4">Archive Activity Snapshot</div>
            <div className="grid grid-cols-2 gap-3">
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Inspections</div>
                <div className="text-xs font-mono font-bold">{day.inspections}</div>
              </div>
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Detections</div>
                <div className="text-xs font-mono font-bold">{day.detections}</div>
              </div>
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Notice Ready</div>
                <div className="text-xs font-mono font-bold">{day.noticeReady}</div>
              </div>
              <div className="surface-nested p-2">
                <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Failed</div>
                <div className="text-xs font-mono font-bold">{day.failed}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-8 surface-base overflow-hidden">
          <div className="px-4 py-3 bg-stone-100 border-b border-stone-200">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Most Active Road Segments</h3>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[9px] font-bold uppercase text-slate-400 border-b border-stone-100">
                <th className="px-4 py-2">Road Segment</th>
                <th className="px-4 py-2">Inspections</th>
                <th className="px-4 py-2">Detections</th>
              </tr>
            </thead>
            <tbody className="text-[10px] font-mono">
              {segmentSummary.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                    No archived inspections yet.
                  </td>
                </tr>
              ) : (
                segmentSummary.map((segment) => (
                  <tr key={segment.roadSegment} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-3 font-bold text-civic-blue">{segment.roadSegment}</td>
                    <td className="px-4 py-3 text-slate-600">{segment.inspections}</td>
                    <td className="px-4 py-3 text-slate-600">{segment.detections}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="col-span-4 surface-base p-6 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={14} className="text-civic-blue" />
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">View Scope</h3>
          </div>
          <div className="surface-nested p-4 text-xs text-slate-600 leading-relaxed flex-1">
            <p className="mb-3">
              This tab intentionally summarizes stored inspections instead of pretending there is a backend ingestion-run system.
            </p>
            <p className="mb-3">
              Use it to sanity-check archive volume, notice-ready cases, and segment concentration while the project remains image-first.
            </p>
            <p className="text-slate-500">
              A future backend release can replace this summary with first-class ingestion entities without changing the rest of the review console.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
