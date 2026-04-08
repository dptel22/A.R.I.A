import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  ExternalLink,
  History as HistoryIcon,
  Layers,
  LoaderCircle,
  MapPin,
  ShieldAlert,
} from 'lucide-react';
import { openNoticePdf } from '../../shared/api';
import { formatDate, pipelineBadgeClass, pipelineLabel } from '../../shared/lib/caseDisplay';
import { RoadCase } from '../../shared/types/app';

interface CaseDetailProps {
  caseData: RoadCase | null;
  loading: boolean;
  onBack: () => void;
  onSelectRelatedCase: (inspectionId: number) => void;
}

export default function CaseDetail({
  caseData,
  loading,
  onBack,
  onSelectRelatedCase,
}: CaseDetailProps) {
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [enhanced, setEnhanced] = useState(false);
  const [openingNotice, setOpeningNotice] = useState(false);
  const [noticeError, setNoticeError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center gap-3 text-slate-500">
        <LoaderCircle size={20} className="animate-spin" />
        Loading case detail...
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3">
        <ShieldAlert size={24} />
        <div className="text-sm font-medium">Select an inspection from the queue to view evidence.</div>
      </div>
    );
  }

  async function handleOpenNotice() {
    if (!caseData.noticeUrl) {
      return;
    }
    setOpeningNotice(true);
    setNoticeError(null);
    try {
      await openNoticePdf(caseData.inspectionId);
    } catch (error) {
      setNoticeError(error instanceof Error ? error.message : 'Failed to open notice.');
    } finally {
      setOpeningNotice(false);
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="h-14 bg-white border-b border-stone-200 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-1 hover:bg-stone-100 rounded-sm transition-colors text-slate-500">
            <ArrowLeft size={20} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">{caseData.id}</h2>
              <span className={`badge badge-${caseData.severity.toLowerCase()}`}>{caseData.severity}</span>
              <span className={`badge ${pipelineBadgeClass(caseData.pipelineStatus)}`}>{pipelineLabel(caseData.pipelineStatus)}</span>
            </div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">{caseData.roadSegment}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Review Status:</span>
          <span className="bg-blue-50 text-blue-600 text-[10px] font-bold px-2 py-0.5 rounded-sm border border-blue-100 uppercase">
            {caseData.status}
          </span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 bg-stone-200 flex flex-col overflow-hidden relative">
          <div className="absolute top-4 left-4 right-4 z-10 flex justify-between items-center">
            <div className="flex gap-2">
              <button
                onClick={() => setOverlayEnabled(!overlayEnabled)}
                className={`px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  overlayEnabled ? 'bg-civic-blue text-white' : 'bg-white text-slate-600'
                }`}
              >
                <Layers size={12} />
                Overlay: {overlayEnabled ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setEnhanced(!enhanced)}
                className={`px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  enhanced ? 'bg-civic-blue text-white' : 'bg-white text-slate-600'
                }`}
              >
                {enhanced ? 'Enhanced' : 'Original'}
              </button>
            </div>
            <div className="bg-black/60 text-white px-3 py-1.5 rounded-sm text-[10px] font-mono flex items-center gap-4">
              <span>CONFIDENCE: {(caseData.confidence * 100).toFixed(1)}%</span>
              <span>FRAME: {caseData.runId}</span>
            </div>
          </div>

          <div className="flex-1 relative overflow-hidden flex items-center justify-center p-8">
            <div className="relative max-w-full max-h-full shadow-2xl">
              <img
                src={caseData.evidenceUrl}
                alt="Road Defect Evidence"
                className={`max-w-full max-h-full object-contain ${enhanced ? 'contrast-125 brightness-110 saturate-110' : ''}`}
              />

              {overlayEnabled && caseData.pipelineStatus === 'SUCCEEDED' && (
                <div className="absolute inset-0 pointer-events-none">
                  {caseData.detections.map((detection) => (
                    <div
                      key={`${detection.className}-${detection.bboxX}-${detection.bboxY}`}
                      className="absolute border-2 border-red-500 bg-red-500/10"
                      style={{
                        left: `${(detection.bboxX - detection.bboxW / 2) * 100}%`,
                        top: `${(detection.bboxY - detection.bboxH / 2) * 100}%`,
                        width: `${detection.bboxW * 100}%`,
                        height: `${detection.bboxH * 100}%`,
                      }}
                    >
                      <div className="absolute -top-6 left-0 bg-red-500 text-white text-[8px] font-bold px-1 py-0.5 uppercase whitespace-nowrap">
                        {detection.className} {(detection.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="absolute bottom-4 left-4 bg-white/90 p-3 rounded-sm border border-stone-200 shadow-lg backdrop-blur-sm">
                <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Detection</div>
                <div className="text-xs font-bold text-slate-900">{caseData.defectClass}</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className={`badge badge-${caseData.severity.toLowerCase()}`}>{caseData.severity}</span>
                  <span className={`badge ${pipelineBadgeClass(caseData.pipelineStatus)}`}>{pipelineLabel(caseData.pipelineStatus)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="h-24 bg-stone-100 border-t border-stone-300 flex items-center gap-2 px-4 shrink-0">
            <div className="w-24 h-16 rounded-sm border-2 overflow-hidden border-civic-blue">
              <img src={caseData.evidenceUrl} alt={caseData.id} className="w-full h-full object-cover" />
            </div>
          </div>
        </div>

        <div className="w-[460px] bg-white border-l border-stone-200 flex flex-col overflow-y-auto">
          <div className="p-6 space-y-6">
            {caseData.failureReason && (
              <section className="bg-red-50 border border-red-100 p-4 rounded-sm">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={16} className="text-red-600" />
                  <h3 className="text-xs font-bold text-red-800 uppercase tracking-wider">Pipeline Failure Logged</h3>
                </div>
                <p className="text-xs text-red-700">{caseData.failureReason}</p>
              </section>
            )}

            <section>
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={14} className="text-civic-blue" />
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Geographic Context</h3>
              </div>
              <div className="surface-nested p-4 rounded-sm">
                <div className="text-sm font-bold text-slate-900 mb-1">{caseData.roadSegment}</div>
                <div className="text-xs text-slate-600 mb-3">{caseData.ward}</div>
                <div className="mono-text text-[10px] text-slate-500 bg-white p-2 border border-stone-200 rounded-sm">
                  LAT: {caseData.coordinates.lat.toFixed(6)}
                  <br />
                  LNG: {caseData.coordinates.lng.toFixed(6)}
                </div>
                <a
                  className="mt-3 inline-flex items-center gap-2 text-xs text-civic-blue font-medium hover:underline"
                  href={`https://www.google.com/maps?q=${caseData.coordinates.lat},${caseData.coordinates.lng}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open coordinate in map
                  <ExternalLink size={12} />
                </a>
              </div>
            </section>

            <section>
              <div className="flex items-center gap-2 mb-3">
                <Calendar size={14} className="text-civic-blue" />
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Review Parameters</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Defect Class</div>
                  <div className="text-xs font-bold">{caseData.defectClass}</div>
                </div>
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Severity</div>
                  <div className="text-xs font-bold text-red-600">{caseData.severity}</div>
                </div>
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Pipeline</div>
                  <div className="text-xs font-bold">{pipelineLabel(caseData.pipelineStatus)}</div>
                </div>
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Created</div>
                  <div className="text-xs font-mono">{formatDate(caseData.created)}</div>
                </div>
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Source Run</div>
                  <div className="text-xs font-mono font-bold">{caseData.runId}</div>
                </div>
                <div className="surface-nested p-3">
                  <div className="text-[8px] font-bold text-slate-500 uppercase mb-1">Prior Flags</div>
                  <div className="text-xs font-mono font-bold">{caseData.priorFlags}</div>
                </div>
              </div>
            </section>

            <section className="bg-blue-50 border border-blue-100 p-4 rounded-sm">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert size={16} className="text-blue-600" />
                <h3 className="text-xs font-bold text-blue-800 uppercase tracking-wider">System Recommendation</h3>
              </div>
              <p className="text-xs text-blue-700 font-medium mb-2">
                Suggested action: <span className="font-bold underline">{caseData.recommendation}</span>
              </p>
              <p className="text-[10px] text-blue-600 italic">
                This guidance is derived from the current defect severity, DLP state, and pipeline status. Final decision requires engineer approval.
              </p>
              {caseData.noticeUrl && (
                <button
                  onClick={handleOpenNotice}
                  disabled={openingNotice}
                  className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-civic-blue hover:underline disabled:opacity-50"
                >
                  {openingNotice ? <LoaderCircle size={12} className="animate-spin" /> : <ExternalLink size={12} />}
                  {openingNotice ? 'Opening notice...' : 'Open generated notice'}
                </button>
              )}
              {noticeError && <div className="mt-3 text-[10px] text-red-700">{noticeError}</div>}
            </section>

            <section>
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert size={14} className="text-civic-blue" />
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Maintenance Entity</h3>
              </div>
              <div className="surface-nested p-4 border-l-4 border-dlp-amber">
                <div className="flex justify-between items-start mb-2">
                  <div className="text-sm font-bold">{caseData.contractor}</div>
                  <span className={`badge ${caseData.dlpStatus === 'Active' ? 'badge-dlp' : 'bg-stone-200 text-slate-500'}`}>
                    {caseData.dlpStatus === 'None' ? 'No Contract' : `DLP ${caseData.dlpStatus}`}
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 mono-text mb-2">
                  CONTRACT: {caseData.contractId ? caseData.contractId : 'Unavailable'}
                </div>
                {caseData.dlpExpiry && (
                  <div className="flex items-center gap-2 text-[10px] text-slate-600">
                    <Calendar size={12} />
                    <span>Expiry: {caseData.dlpExpiry}</span>
                  </div>
                )}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-2 mb-3">
                <HistoryIcon size={14} className="text-civic-blue" />
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Prior Segment Flags</h3>
              </div>
              <div className="space-y-2">
                {caseData.segmentHistory.length > 0 ? (
                  caseData.segmentHistory.map((related) => (
                    <button
                      key={related.inspectionId}
                      onClick={() => onSelectRelatedCase(related.inspectionId)}
                      className="w-full p-3 bg-stone-50 border border-stone-200 text-[10px] text-left hover:border-civic-blue transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">
                          ARIA-{related.inspectionId.toString().padStart(6, '0')} - {related.totalDetections} detection(s)
                        </span>
                        <span className={`badge ${pipelineBadgeClass(related.pipelineStatus)}`}>{pipelineLabel(related.pipelineStatus)}</span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-slate-500">
                        <span>
                          Severity {related.severity} · Recommendation {related.recommendation}
                        </span>
                        <span className="font-mono">{formatDate(related.created)}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="text-[10px] text-slate-400 italic">No prior flags recorded for this segment.</div>
                )}
              </div>
            </section>
          </div>

          <div className="mt-auto p-6 bg-stone-50 border-t border-stone-200 space-y-4">
            <div>
              <div className="text-[10px] font-bold text-slate-500 uppercase mb-2">Current Reviewer Workflow</div>
              <p className="text-xs text-slate-600 leading-relaxed">
                This build focuses on inspection review, repeat-segment context, and authenticated notice access. Persistent engineer decision actions are intentionally omitted until the backend supports them end to end.
              </p>
            </div>

            {caseData.noticeUrl ? (
              <button
                onClick={handleOpenNotice}
                disabled={openingNotice}
                className="btn-primary text-[10px] uppercase tracking-wider py-3 flex items-center justify-center gap-2 w-full"
              >
                {openingNotice ? <LoaderCircle size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                {openingNotice ? 'Opening Notice...' : 'Open Notice PDF'}
              </button>
            ) : (
              <div className="rounded-sm border border-stone-200 bg-white px-4 py-3 text-[10px] uppercase tracking-wider text-slate-500">
                No contractor notice is available for this inspection state.
              </div>
            )}

            <p className="text-[9px] text-slate-400 text-center italic">
              Failed inspections, repeat-segment history, and notice availability are sourced from the live backend contract.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
