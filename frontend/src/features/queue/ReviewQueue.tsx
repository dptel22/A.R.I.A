import React, { useState } from 'react';
import {
  AlertCircle, ChevronRight, Clock, Filter,
  HardHat, RefreshCw, ShieldCheck, Upload,
} from 'lucide-react';
import UploadInspectionModal from './UploadInspectionModal';
import { formatDate, pipelineLabel, pipelineStatusClass, severityRank, sourceLabel } from '../../shared/lib/caseDisplay';
import { BackendHealth, DLPStatus, RoadCase, Severity } from '../../shared/types/app';
import DefectIcon from '../../shared/components/DefectIcon';

interface ReviewQueueProps {
  cases: RoadCase[];
  loading: boolean;
  error: string | null;
  health: BackendHealth | null;
  onSelectCase: (inspectionId: number) => void;
  onRefresh: () => Promise<void>;
  onUpload: (payload: { file: File; lat: number; lng: number }) => Promise<void>;
}

export default function ReviewQueue({
  cases,
  loading,
  error,
  health,
  onSelectCase,
  onRefresh,
  onUpload,
}: ReviewQueueProps) {
  const [severityFilter, setSeverityFilter] = useState<'All' | Severity>('All');
  const [dlpFilter, setDlpFilter] = useState<'All' | DLPStatus>('All');
  const [zoneFilter, setZoneFilter] = useState('All');
  const [contractorFilter, setContractorFilter] = useState('All');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const zones = Array.from(new Set(cases.map((item) => item.zoneId)));
  const contractors = Array.from(new Set(cases.map((item) => item.contractor)));

  const filteredCases = cases
    .filter((item) => severityFilter === 'All' || item.severity === severityFilter)
    .filter((item) => dlpFilter === 'All' || item.dlpStatus === dlpFilter)
    .filter((item) => zoneFilter === 'All' || item.zoneId === zoneFilter)
    .filter((item) => contractorFilter === 'All' || item.contractor === contractorFilter)
    .sort((left, right) => {
      const severityDelta = severityRank(right.severity) - severityRank(left.severity);
      if (severityDelta !== 0) return severityDelta;
      if (left.dlpStatus !== right.dlpStatus) return left.dlpStatus === 'Active' ? -1 : 1;
      if (left.priorFlags !== right.priorFlags) return right.priorFlags - left.priorFlags;
      return new Date(right.created).getTime() - new Date(left.created).getTime();
    });

  const awaitingReview    = cases.filter((item) => item.status === 'Awaiting Review').length;
  const criticalDefects   = cases.filter((item) => item.severity === 'Critical').length;
  const underDlp          = cases.filter((item) => item.dlpStatus === 'Active').length;
  const manualInspection  = cases.filter((item) => item.recommendation === 'Escalate Manual Inspection').length;
  const escalatedToday    = cases.filter((item) => item.status === 'Escalated').length;

  async function handleRefresh() {
    setRefreshing(true);
    try { await onRefresh(); } finally { setRefreshing(false); }
  }

  const selectClass = 'bg-paper border border-hairline text-xs rounded-sm px-2 py-1 text-ink focus:outline-none focus:ring-1 focus:ring-authority-blue';

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-headline font-bold tracking-tight mb-1"
              style={{ color: 'var(--color-authority-blue)' }}>
            Review Queue
          </h1>
          <p className="text-ink-soft text-sm">
            Live inspection backlog from the FastAPI backend — detection output, contract match, and DLP status.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-secondary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={handleRefresh}>
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button className="btn-primary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={() => setUploadOpen(true)}>
            <Upload size={13} />
            Run Detection
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        {[
          { label: 'Awaiting Review', value: awaitingReview,   icon: Clock,      color: 'var(--color-authority-blue)' },
          { label: 'Critical',        value: criticalDefects,  icon: AlertCircle, color: 'var(--color-signal-red)'    },
          { label: 'Under DLP',       value: underDlp,         icon: ShieldCheck, color: 'var(--color-hazard-amber)'  },
          { label: 'Manual Inspect',  value: manualInspection, icon: HardHat,     color: 'var(--color-ink-soft)'      },
          { label: 'Escalated',       value: escalatedToday,   icon: ChevronRight,color: 'var(--color-authority-blue)'},
        ].map((kpi) => (
          <div key={kpi.label} className="surface-base p-4">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[9px] font-bold uppercase tracking-wider text-ink-soft">{kpi.label}</span>
              <kpi.icon size={13} style={{ color: kpi.color }} />
            </div>
            <div className="text-2xl font-bold mono-text">{String(kpi.value).padStart(2, '0')}</div>
          </div>
        ))}
      </div>

      {/* API status bar */}
      <div className="surface-base p-3 mb-4 flex items-center justify-between text-xs text-ink-soft">
        <div>
          API status:{' '}
          <span className="font-bold" style={{ color: health?.model_loaded ? '#2d6a4f' : 'var(--color-hazard-amber)' }}>
            {health ? (health.model_loaded ? 'Model ready' : 'Model not loaded') : 'Checking backend…'}
          </span>
          {!health?.model_loaded && (
            <span className="ml-2 text-ink-soft/60">
              Archive review remains available; new uploads require local model weights.
            </span>
          )}
        </div>
        <div className="mono-text">Loaded: {cases.length}</div>
      </div>

      {/* Filter bar */}
      <div className="surface-base p-3 mb-6 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-[10px] font-bold text-ink-soft uppercase tracking-wider mr-2">
          <Filter size={13} />
          Filters
        </div>
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value as 'All' | Severity)} className={selectClass}>
          <option value="All">Severity: All</option>
          {(['Critical','High','Medium','Low'] as Severity[]).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={dlpFilter} onChange={(e) => setDlpFilter(e.target.value as 'All' | DLPStatus)} className={selectClass}>
          <option value="All">DLP: All</option>
          <option value="Active">Active</option>
          <option value="Expired">Expired</option>
          <option value="None">None</option>
        </select>
        <select value={zoneFilter} onChange={(e) => setZoneFilter(e.target.value)} className={selectClass}>
          <option value="All">Zone: All</option>
          {zones.map((z) => <option key={z} value={z}>{z}</option>)}
        </select>
        <select value={contractorFilter} onChange={(e) => setContractorFilter(e.target.value)} className={selectClass}>
          <option value="All">Contractor: All</option>
          {contractors.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button
          className="ml-auto text-xs font-bold hover:underline"
          style={{ color: 'var(--color-authority-blue)' }}
          onClick={() => { setSeverityFilter('All'); setDlpFilter('All'); setZoneFilter('All'); setContractorFilter('All'); }}
        >
          Clear
        </button>
      </div>

      {/* Table */}
      <div className="surface-base overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-stone-100 border-b border-hairline text-[9px] font-bold uppercase tracking-wider text-ink-soft">
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Pipeline</th>
              <th className="px-4 py-3">Evidence</th>
              <th className="px-4 py-3">Case ID</th>
              <th className="px-4 py-3">Road Segment</th>
              <th className="px-4 py-3">Ward / Zone</th>
              <th className="px-4 py-3">Contractor</th>
              <th className="px-4 py-3">DLP</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="text-xs">
            {loading ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center text-ink-soft">Loading inspection queue…</td></tr>
            ) : error ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center" style={{ color: 'var(--color-signal-red)' }}>{error}</td></tr>
            ) : filteredCases.length === 0 ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center text-ink-soft">No inspections match the current filters.</td></tr>
            ) : (
              filteredCases.map((item) => (
                <tr
                  key={item.inspectionId}
                  onClick={() => onSelectCase(item.inspectionId)}
                  className="border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-colors group"
                >
                  {/* Severity — schematic icon + flag label */}
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <DefectIcon className={item.defectClass} size={16} wrapClass={`badge badge-${item.severity.toLowerCase()}`} />
                      <span className={`badge badge-${item.severity.toLowerCase()}`}>{item.severity}</span>
                    </div>
                  </td>
                  {/* Pipeline — dot + label */}
                  <td className="px-4 py-4">
                    <span className={pipelineStatusClass(item.pipelineStatus)}>
                      <span className="pipeline-dot" />
                      {pipelineLabel(item.pipelineStatus)}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="w-14 h-10 bg-stone-200 rounded-sm overflow-hidden border border-hairline">
                      <img src={item.evidenceUrl} alt={item.id} className="w-full h-full object-cover" />
                    </div>
                  </td>
                  <td className="px-4 py-4 mono-text font-bold" style={{ color: 'var(--color-authority-blue)' }}>{item.id}</td>
                  <td className="px-4 py-4 font-medium">{item.roadSegment}</td>
                  <td className="px-4 py-4 text-ink-soft">{item.ward}</td>
                  <td className="px-4 py-4 text-ink-soft">{item.contractor}</td>
                  <td className="px-4 py-4">
                    <span className={`badge ${item.dlpStatus === 'Active' ? 'badge-dlp' : 'badge-none'}`}>
                      {item.dlpStatus === 'None' ? 'No Contract' : `DLP ${item.dlpStatus}`}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-ink-soft text-[10px]">{sourceLabel(item.source)}</td>
                  <td className="px-4 py-4 text-ink-soft mono-text">{formatDate(item.created)}</td>
                  <td className="px-4 py-4">
                    <span className="px-2 py-0.5 rounded-sm text-[9px] font-bold bg-stone-100 text-ink-soft border border-hairline uppercase">
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <ChevronRight size={15} className="text-hairline group-hover:text-ink transition-colors" />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <UploadInspectionModal open={uploadOpen} onClose={() => setUploadOpen(false)} onSubmit={onUpload} />
    </div>
  );
}
