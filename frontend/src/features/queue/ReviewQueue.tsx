import React, { useState } from 'react';
import { AlertCircle, ChevronRight, Clock, Filter, HardHat, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import UploadInspectionModal from './UploadInspectionModal';
import { formatDate, pipelineBadgeClass, pipelineLabel, severityRank } from '../../shared/lib/caseDisplay';
import { BackendHealth, DLPStatus, RoadCase, Severity } from '../../shared/types/app';

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
      if (severityDelta !== 0) {
        return severityDelta;
      }
      if (left.dlpStatus !== right.dlpStatus) {
        return left.dlpStatus === 'Active' ? -1 : 1;
      }
      if (left.priorFlags !== right.priorFlags) {
        return right.priorFlags - left.priorFlags;
      }
      return new Date(right.created).getTime() - new Date(left.created).getTime();
    });

  const awaitingReview = cases.filter((item) => item.status === 'Awaiting Review').length;
  const criticalDefects = cases.filter((item) => item.severity === 'Critical').length;
  const underDlp = cases.filter((item) => item.dlpStatus === 'Active').length;
  const manualInspection = cases.filter((item) => item.recommendation === 'Escalate Manual Inspection').length;
  const escalatedToday = cases.filter((item) => item.status === 'Escalated').length;

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-civic-blue mb-1">Review Queue</h1>
          <p className="text-slate-500 text-sm">
            Live inspection backlog from the FastAPI backend, including detection output, contract match, and DLP status.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-secondary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={handleRefresh}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh Queue
          </button>
          <button className="btn-primary flex items-center gap-2 text-xs uppercase tracking-wider" onClick={() => setUploadOpen(true)}>
            <Upload size={14} />
            Run Detection
          </button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-8">
        {[
          { label: 'Awaiting Review', value: awaitingReview, icon: Clock, color: 'text-blue-600' },
          { label: 'Critical Defects', value: criticalDefects, icon: AlertCircle, color: 'text-red-600' },
          { label: 'Under DLP', value: underDlp, icon: ShieldCheck, color: 'text-orange-600' },
          { label: 'Manual Inspection', value: manualInspection, icon: HardHat, color: 'text-slate-600' },
          { label: 'Escalated Today', value: escalatedToday, icon: ChevronRight, color: 'text-civic-blue' },
        ].map((kpi) => (
          <div key={kpi.label} className="surface-base p-4">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{kpi.label}</span>
              <kpi.icon size={14} className={kpi.color} />
            </div>
            <div className="text-2xl font-bold mono-text">{String(kpi.value).padStart(2, '0')}</div>
          </div>
        ))}
      </div>

      <div className="surface-base p-3 mb-4 flex items-center justify-between text-xs text-slate-500">
        <div>
          API status:{' '}
          <span className={`font-bold ${health?.model_loaded ? 'text-green-700' : 'text-orange-700'}`}>
            {health ? (health.model_loaded ? 'Model ready' : 'Model not loaded') : 'Checking backend...'}
          </span>
          {!health?.model_loaded && (
            <span className="ml-2 text-slate-400">
              Archive review remains available; new uploads require local model weights.
            </span>
          )}
        </div>
        <div className="mono-text">Loaded inspections: {cases.length}</div>
      </div>

      <div className="surface-base p-3 mb-6 flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider mr-4">
          <Filter size={14} />
          Filters
        </div>
        <select
          value={severityFilter}
          onChange={(event) => setSeverityFilter(event.target.value as 'All' | Severity)}
          className="bg-stone-100 border-stone-200 text-xs rounded-sm focus:ring-civic-blue"
        >
          <option value="All">Severity: All</option>
          <option value="Critical">Critical</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
        <select
          value={dlpFilter}
          onChange={(event) => setDlpFilter(event.target.value as 'All' | DLPStatus)}
          className="bg-stone-100 border-stone-200 text-xs rounded-sm focus:ring-civic-blue"
        >
          <option value="All">DLP Status: All</option>
          <option value="Active">Active</option>
          <option value="Expired">Expired</option>
          <option value="None">None</option>
        </select>
        <select
          value={zoneFilter}
          onChange={(event) => setZoneFilter(event.target.value)}
          className="bg-stone-100 border-stone-200 text-xs rounded-sm focus:ring-civic-blue"
        >
          <option value="All">Zone: All</option>
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
        <select
          value={contractorFilter}
          onChange={(event) => setContractorFilter(event.target.value)}
          className="bg-stone-100 border-stone-200 text-xs rounded-sm focus:ring-civic-blue"
        >
          <option value="All">Contractor: All</option>
          {contractors.map((contractor) => (
            <option key={contractor} value={contractor}>
              {contractor}
            </option>
          ))}
        </select>
        <button
          className="ml-auto text-xs font-bold text-civic-blue hover:underline"
          onClick={() => {
            setSeverityFilter('All');
            setDlpFilter('All');
            setZoneFilter('All');
            setContractorFilter('All');
          }}
        >
          Clear All
        </button>
      </div>

      <div className="surface-base overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-stone-100 border-b border-stone-200 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Pipeline</th>
              <th className="px-4 py-3">Evidence</th>
              <th className="px-4 py-3">Case ID</th>
              <th className="px-4 py-3">Road Segment</th>
              <th className="px-4 py-3">Ward / Zone</th>
              <th className="px-4 py-3">Contractor</th>
              <th className="px-4 py-3">DLP Status</th>
              <th className="px-4 py-3">Recommendation</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Review Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="text-xs">
            {loading ? (
              <tr>
                <td colSpan={12} className="px-4 py-12 text-center text-slate-500">
                  Loading inspection queue...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={12} className="px-4 py-12 text-center text-red-700">
                  {error}
                </td>
              </tr>
            ) : filteredCases.length === 0 ? (
              <tr>
                <td colSpan={12} className="px-4 py-12 text-center text-slate-500">
                  No inspections match the current filters.
                </td>
              </tr>
            ) : (
              filteredCases.map((item) => (
                <tr
                  key={item.inspectionId}
                  onClick={() => onSelectCase(item.inspectionId)}
                  className="border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-colors group"
                >
                  <td className="px-4 py-4">
                    <span className={`badge badge-${item.severity.toLowerCase()}`}>{item.severity}</span>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`badge ${pipelineBadgeClass(item.pipelineStatus)}`}>{pipelineLabel(item.pipelineStatus)}</span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="w-14 h-10 bg-stone-200 rounded-sm overflow-hidden border border-stone-300">
                      <img src={item.evidenceUrl} alt={item.id} className="w-full h-full object-cover" />
                    </div>
                  </td>
                  <td className="px-4 py-4 mono-text font-bold text-civic-blue">{item.id}</td>
                  <td className="px-4 py-4 font-medium">{item.roadSegment}</td>
                  <td className="px-4 py-4 text-slate-500">{item.ward}</td>
                  <td className="px-4 py-4 text-slate-500">{item.contractor}</td>
                  <td className="px-4 py-4">
                    <span className={`badge ${item.dlpStatus === 'Active' ? 'badge-dlp' : 'bg-stone-200 text-slate-500'}`}>
                      {item.dlpStatus === 'None' ? 'No Contract' : `DLP ${item.dlpStatus}`}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <span className="text-[10px] font-medium text-slate-600 italic">
                      Recommended: {item.recommendation}
                    </span>
                    <div className="mt-1 text-[10px] text-slate-400">Prior flags: {item.priorFlags}</div>
                  </td>
                  <td className="px-4 py-4 text-slate-500 mono-text">{formatDate(item.created)}</td>
                  <td className="px-4 py-4">
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-blue-50 text-blue-600 border border-blue-100">
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <ChevronRight size={16} className="text-slate-300 group-hover:text-civic-blue transition-colors" />
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
