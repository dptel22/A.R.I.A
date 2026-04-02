import React, { useEffect, useMemo, useState } from 'react';
import { Download, ExternalLink, FileText, Filter, LoaderCircle, Map as MapIcon, Printer } from 'lucide-react';
import { openNoticePdf } from '../api';
import { PipelineStatus, RoadCase } from '../types';

interface DecisionHistoryProps {
  cases: RoadCase[];
  caseDetails: Record<number, RoadCase>;
  onLoadCaseDetail: (inspectionId: number) => Promise<void>;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function pipelineLabel(status: PipelineStatus): string {
  if (status === 'FAILED') {
    return 'Pipeline Failed';
  }
  if (status === 'NO_DETECTIONS') {
    return 'No Defects';
  }
  return 'Detected';
}

function pipelineBadgeClass(status: PipelineStatus): string {
  if (status === 'FAILED') {
    return 'badge-pipeline-failed';
  }
  if (status === 'NO_DETECTIONS') {
    return 'badge-pipeline-empty';
  }
  return 'badge-pipeline-ok';
}

export default function DecisionHistory({ cases, caseDetails, onLoadCaseDetail }: DecisionHistoryProps) {
  const historyCases = useMemo(
    () => [...cases].sort((left, right) => new Date(right.created).getTime() - new Date(left.created).getTime()),
    [cases],
  );
  const [selectedInspectionId, setSelectedInspectionId] = useState<number | null>(historyCases[0]?.inspectionId || null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [noticeError, setNoticeError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedInspectionId && historyCases.length > 0) {
      setSelectedInspectionId(historyCases[0].inspectionId);
    }
  }, [historyCases, selectedInspectionId]);

  useEffect(() => {
    if (!selectedInspectionId) {
      return;
    }
    if (caseDetails[selectedInspectionId]?.segmentHistory.length) {
      return;
    }

    let cancelled = false;
    setLoadingDetail(true);
    onLoadCaseDetail(selectedInspectionId)
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) {
          setLoadingDetail(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [caseDetails, onLoadCaseDetail, selectedInspectionId]);

  const selectedCase =
    (selectedInspectionId ? caseDetails[selectedInspectionId] : null) ||
    historyCases.find((item) => item.inspectionId === selectedInspectionId) ||
    null;

  async function handleOpenNotice() {
    if (!selectedCase?.noticeUrl) {
      return;
    }
    setNoticeError(null);
    try {
      await openNoticePdf(selectedCase.inspectionId);
    } catch (error) {
      setNoticeError(error instanceof Error ? error.message : 'Failed to open notice.');
    }
  }

  return (
    <div className="h-full flex overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden border-r border-stone-200">
        <div className="p-8 pb-4 shrink-0">
          <div className="flex justify-between items-end mb-6">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-civic-blue mb-1">Decision History</h1>
              <p className="text-slate-500 text-sm">
                Audit-ready inspection archive including failed runs, masked contractor context, and repeat segment visibility.
              </p>
            </div>
            <button className="btn-secondary flex items-center gap-2 text-xs uppercase tracking-wider" disabled>
              <Download size={14} />
              Export Audit Log
            </button>
          </div>

          <div className="surface-base p-3 mb-4 flex items-center gap-3">
            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider mr-2">
              <Filter size={12} />
              Filters
            </div>
            <input type="date" className="bg-stone-100 border-stone-200 text-[10px] rounded-sm focus:ring-civic-blue" disabled />
            <select className="bg-stone-100 border-stone-200 text-[10px] rounded-sm focus:ring-civic-blue" disabled>
              <option>Recommendation: All</option>
            </select>
            <select className="bg-stone-100 border-stone-200 text-[10px] rounded-sm focus:ring-civic-blue" disabled>
              <option>Contractor: All</option>
            </select>
            <button className="ml-auto text-[10px] font-bold text-slate-400 cursor-not-allowed">Workflow actions pending</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-8 pb-8">
          <div className="surface-base overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-stone-100 border-b border-stone-200 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Case ID</th>
                  <th className="px-4 py-3">Road Segment</th>
                  <th className="px-4 py-3">Pipeline</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Prior Flags</th>
                  <th className="px-4 py-3">Processed</th>
                </tr>
              </thead>
              <tbody className="text-xs">
                {historyCases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                      No inspections are available yet.
                    </td>
                  </tr>
                ) : (
                  historyCases.map((item) => (
                    <tr
                      key={item.inspectionId}
                      onClick={() => setSelectedInspectionId(item.inspectionId)}
                      className={`border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-colors ${
                        selectedInspectionId === item.inspectionId ? 'bg-stone-100' : ''
                      }`}
                    >
                      <td className="px-4 py-4 mono-text font-bold text-civic-blue">{item.id}</td>
                      <td className="px-4 py-4 font-medium">{item.roadSegment}</td>
                      <td className="px-4 py-4">
                        <span className={`badge ${pipelineBadgeClass(item.pipelineStatus)}`}>{pipelineLabel(item.pipelineStatus)}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`badge badge-${item.severity.toLowerCase()}`}>{item.severity}</span>
                      </td>
                      <td className="px-4 py-4 text-slate-600 mono-text">{item.priorFlags}</td>
                      <td className="px-4 py-4 text-slate-500 mono-text">{formatDate(item.created)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="w-[420px] bg-white flex flex-col overflow-y-auto shrink-0">
        {selectedCase ? (
          <div className="p-6 space-y-6">
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Selected Case</div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">{selectedCase.id}</h2>
                <span className={`badge ${pipelineBadgeClass(selectedCase.pipelineStatus)}`}>{pipelineLabel(selectedCase.pipelineStatus)}</span>
              </div>
              <div className="text-xs text-slate-500">{selectedCase.roadSegment}</div>
            </div>

            <div className="aspect-video bg-stone-200 rounded-sm overflow-hidden border border-stone-300">
              <img src={selectedCase.evidenceUrl} alt="Evidence" className="w-full h-full object-cover" />
            </div>

            <div className="flex gap-2">
              <a
                className="flex-1 btn-secondary text-[10px] uppercase tracking-wider py-2 flex items-center justify-center gap-2"
                href={`https://www.google.com/maps?q=${selectedCase.coordinates.lat},${selectedCase.coordinates.lng}`}
                target="_blank"
                rel="noreferrer"
              >
                <MapIcon size={12} />
                Map Link
              </a>
              {selectedCase.noticeUrl ? (
                <button
                  className="flex-1 btn-secondary text-[10px] uppercase tracking-wider py-2 flex items-center justify-center gap-2"
                  onClick={handleOpenNotice}
                >
                  <Printer size={12} />
                  Open Notice
                </button>
              ) : (
                <button className="flex-1 btn-secondary text-[10px] uppercase tracking-wider py-2 flex items-center justify-center gap-2" disabled>
                  <Printer size={12} />
                  No Notice
                </button>
              )}
            </div>

            {loadingDetail && (
              <div className="text-[10px] text-slate-500 flex items-center gap-2">
                <LoaderCircle size={12} className="animate-spin" />
                Loading repeat-segment history...
              </div>
            )}

            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">Current Archive Summary</h3>
              <div className="bg-stone-50 border-l-2 border-civic-blue p-4 text-xs text-slate-700 leading-relaxed">
                This inspection is stored with pipeline status <span className="font-bold">{pipelineLabel(selectedCase.pipelineStatus)}</span>,
                recommendation <span className="font-bold">{selectedCase.recommendation}</span>, and {selectedCase.priorFlags} prior flag(s) on the same segment.
              </div>
              {selectedCase.failureReason && (
                <div className="mt-3 text-[10px] text-red-700 bg-red-50 border border-red-100 p-3 rounded-sm">
                  {selectedCase.failureReason}
                </div>
              )}
            </section>

            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">Repeat Segment Timeline</h3>
              <div className="space-y-2">
                {selectedCase.segmentHistory.length > 0 ? (
                  selectedCase.segmentHistory.map((item) => (
                    <div key={item.inspectionId} className="p-3 bg-stone-50 border border-stone-200 rounded-sm">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[10px] font-bold text-civic-blue">
                          ARIA-{item.inspectionId.toString().padStart(6, '0')}
                        </div>
                        <span className={`badge ${pipelineBadgeClass(item.pipelineStatus)}`}>{pipelineLabel(item.pipelineStatus)}</span>
                      </div>
                      <div className="mt-2 text-[10px] text-slate-600">
                        Severity {item.severity} · {item.totalDetections} detection(s) · {item.recommendation}
                      </div>
                      <div className="mt-1 text-[10px] text-slate-400 mono-text">{formatDate(item.created)}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-[10px] text-slate-400 italic">No prior segment history available.</div>
                )}
              </div>
            </section>

            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">Generated Artifacts</h3>
              <div className="space-y-2">
                {selectedCase.noticeUrl ? (
                  <button
                    onClick={handleOpenNotice}
                    className="w-full flex items-center justify-between p-3 bg-stone-50 border border-stone-200 rounded-sm group hover:border-civic-blue transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <FileText size={16} className="text-slate-400 group-hover:text-civic-blue" />
                      <div className="text-left">
                        <div className="text-[10px] font-bold text-slate-900">ARIA Notice PDF</div>
                        <div className="text-[8px] text-slate-400 uppercase">Authenticated frontend download</div>
                      </div>
                    </div>
                    <ExternalLink size={12} className="text-slate-300" />
                  </button>
                ) : (
                  <div className="p-3 bg-stone-50 border border-stone-200 rounded-sm text-[10px] text-slate-500">
                    No notice artifact is available for this inspection.
                  </div>
                )}
                {noticeError && <div className="text-[10px] text-red-700">{noticeError}</div>}
              </div>
            </section>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center p-12 text-center">
            <FileText size={48} className="text-stone-200 mb-4" />
            <div className="text-sm font-bold text-slate-400 uppercase tracking-widest">No Case Selected</div>
            <p className="text-xs text-slate-400 mt-2">Select a case from the inspection archive to view details.</p>
          </div>
        )}
      </div>
    </div>
  );
}
