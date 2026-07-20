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
import { formatDate, pipelineLabel, pipelineStatusClass } from '../../shared/lib/caseDisplay';
import { RoadCase } from '../../shared/types/app';
import DefectIcon from '../../shared/components/DefectIcon';

interface CaseDetailProps {
  caseData: RoadCase | null;
  loading: boolean;
  onBack: () => void;
  onSelectRelatedCase: (inspectionId: number) => void;
}

export default function CaseDetail({ caseData, loading, onBack, onSelectRelatedCase }: CaseDetailProps) {
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [enhanced, setEnhanced] = useState(false);
  const [openingNotice, setOpeningNotice] = useState(false);
  const [noticeError, setNoticeError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center gap-3 text-ink-soft">
        <LoaderCircle size={20} className="animate-spin" />
        Loading case detail…
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-ink-soft gap-3">
        <ShieldAlert size={24} />
        <div className="text-sm font-medium">Select an inspection from the queue to view evidence.</div>
      </div>
    );
  }

  async function handleOpenNotice() {
    if (!caseData!.noticeUrl) return;
    setOpeningNotice(true);
    setNoticeError(null);
    try {
      await openNoticePdf(caseData!.inspectionId);
    } catch (error) {
      setNoticeError(error instanceof Error ? error.message : 'Failed to open notice.');
    } finally {
      setOpeningNotice(false);
    }
  }

  const severityClass = `badge badge-${caseData.severity.toLowerCase()}`;

  return (
    <div className="h-full flex flex-col">
      {/* Top bar */}
      <div className="h-12 bg-white border-b border-hairline flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-1 hover:bg-stone-100 rounded-sm transition-colors text-ink-soft">
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-headline font-bold text-ink">{caseData.id}</h2>
              <span className={severityClass}>{caseData.severity}</span>
              {/* Pipeline dot+label inline */}
              <span className={pipelineStatusClass(caseData.pipelineStatus)}>
                <span className="pipeline-dot" />
                {pipelineLabel(caseData.pipelineStatus)}
              </span>
            </div>
            <div className="text-[9px] text-ink-soft uppercase tracking-wider font-medium">{caseData.roadSegment}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-bold text-ink-soft uppercase tracking-widest">Status:</span>
          <span className="bg-stone-100 text-ink-soft text-[9px] font-bold px-2 py-0.5 rounded-sm border border-hairline uppercase">
            {caseData.status}
          </span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Evidence pane */}
        <div className="flex-1 bg-stone-200 flex flex-col overflow-hidden relative">
          <div className="absolute top-4 left-4 right-4 z-10 flex justify-between items-center">
            <div className="flex gap-2">
              <button
                onClick={() => setOverlayEnabled(!overlayEnabled)}
                className={`px-3 py-1.5 rounded-sm text-[9px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  overlayEnabled ? 'text-white' : 'bg-white text-ink-soft'
                }`}
                style={overlayEnabled ? { background: 'var(--color-authority-blue)' } : {}}
              >
                <Layers size={11} />
                Overlay: {overlayEnabled ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setEnhanced(!enhanced)}
                className={`px-3 py-1.5 rounded-sm text-[9px] font-bold uppercase tracking-wider transition-colors ${
                  enhanced ? 'text-white' : 'bg-white text-ink-soft'
                }`}
                style={enhanced ? { background: 'var(--color-authority-blue)' } : {}}
              >
                {enhanced ? 'Enhanced' : 'Original'}
              </button>
            </div>
            <div className="bg-black/60 text-white px-3 py-1.5 rounded-sm text-[9px] mono-text flex items-center gap-4">
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
                      className="absolute border-2 border-signal-red bg-signal-red/10"
                      style={{
                        left:   `${(detection.bboxX - detection.bboxW / 2) * 100}%`,
                        top:    `${(detection.bboxY - detection.bboxH / 2) * 100}%`,
                        width:  `${detection.bboxW * 100}%`,
                        height: `${detection.bboxH * 100}%`,
                      }}
                    >
                      <div
                        className="absolute -top-5 left-0 text-white text-[8px] font-bold px-1 py-0.5 uppercase whitespace-nowrap"
                        style={{ background: 'var(--color-signal-red)' }}
                      >
                        {detection.className} {(detection.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Defect badge overlay */}
              <div className="absolute bottom-4 left-4 bg-white/90 p-3 rounded-sm border border-hairline shadow-lg backdrop-blur-sm">
                <div className="text-[9px] font-bold text-ink-soft uppercase mb-1">Detection</div>
                <div className="flex items-center gap-2">
                  <DefectIcon className={caseData.defectClass} size={18} />
                  <span className="text-xs font-bold text-ink">{caseData.defectClass}</span>
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={severityClass}>{caseData.severity}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="h-20 bg-stone-100 border-t border-hairline flex items-center gap-2 px-4 shrink-0">
            <div className="w-20 h-14 rounded-sm border-2 overflow-hidden" style={{ borderColor: 'var(--color-authority-blue)' }}>
              <img src={caseData.evidenceUrl} alt={caseData.id} className="w-full h-full object-cover" />
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-[440px] bg-white border-l border-hairline flex flex-col overflow-y-auto">
          <div className="p-5 space-y-5">
            {caseData.failureReason && (
              <section className="bg-red-50 border border-red-100 p-4 rounded-sm">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={14} style={{ color: 'var(--color-signal-red)' }} />
                  <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--color-signal-red)' }}>
                    Pipeline Failure Logged
                  </h3>
                </div>
                <p className="text-xs" style={{ color: 'var(--color-signal-red)' }}>{caseData.failureReason}</p>
              </section>
            )}

            {/* Geographic */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={13} style={{ color: 'var(--color-authority-blue)' }} />
                <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Geographic Context</h3>
              </div>
              <div className="surface-nested p-4 rounded-sm">
                <div className="text-sm font-bold text-ink mb-1">{caseData.roadSegment}</div>
                <div className="text-xs text-ink-soft mb-3">{caseData.ward}</div>
                <div className="mono-text text-[9px] text-ink-soft bg-white p-2 border border-hairline rounded-sm leading-5">
                  LAT: {caseData.coordinates.lat.toFixed(6)}<br />
                  LNG: {caseData.coordinates.lng.toFixed(6)}
                </div>
                <a
                  className="mt-2 inline-flex items-center gap-2 text-xs font-medium hover:underline"
                  style={{ color: 'var(--color-authority-blue)' }}
                  href={`https://www.google.com/maps?q=${caseData.coordinates.lat},${caseData.coordinates.lng}`}
                  target="_blank" rel="noreferrer"
                >
                  Open in map <ExternalLink size={11} />
                </a>
              </div>
            </section>

            {/* Review parameters */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Calendar size={13} style={{ color: 'var(--color-authority-blue)' }} />
                <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Review Parameters</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Defect Class', value: <div className="flex items-center gap-1.5"><DefectIcon className={caseData.defectClass} size={14} /><span>{caseData.defectClass}</span></div> },
                  { label: 'Severity',     value: <span className={severityClass}>{caseData.severity}</span> },
                  { label: 'Pipeline',     value: <span className={pipelineStatusClass(caseData.pipelineStatus)}><span className="pipeline-dot" />{pipelineLabel(caseData.pipelineStatus)}</span> },
                  { label: 'Created',      value: <span className="mono-text">{formatDate(caseData.created)}</span> },
                  { label: 'Source Run',   value: <span className="mono-text font-bold">{caseData.runId}</span> },
                  { label: 'Prior Flags',  value: <span className="mono-text font-bold">{caseData.priorFlags}</span> },
                ].map(({ label, value }) => (
                  <div key={label} className="surface-nested p-3">
                    <div className="text-[8px] font-bold text-ink-soft uppercase mb-1">{label}</div>
                    <div className="text-xs">{value}</div>
                  </div>
                ))}
              </div>
            </section>

            {/* Recommendation */}
            <section className="bg-stone-50 border border-hairline p-4 rounded-sm">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert size={14} style={{ color: 'var(--color-authority-blue)' }} />
                <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--color-authority-blue)' }}>
                  System Recommendation
                </h3>
              </div>
              <p className="text-xs text-ink font-medium mb-2">
                Suggested: <span className="font-bold underline">{caseData.recommendation}</span>
              </p>
              <p className="text-[9px] text-ink-soft italic">
                Derived from defect severity, DLP state, and pipeline status. Final decision requires engineer approval.
              </p>
              {caseData.noticeUrl && (
                <button
                  onClick={handleOpenNotice}
                  disabled={openingNotice}
                  className="mt-3 inline-flex items-center gap-2 text-xs font-bold hover:underline disabled:opacity-50"
                  style={{ color: 'var(--color-authority-blue)' }}
                >
                  {openingNotice ? <LoaderCircle size={11} className="animate-spin" /> : <ExternalLink size={11} />}
                  {openingNotice ? 'Opening…' : 'Open generated notice'}
                </button>
              )}
              {noticeError && <div className="mt-2 text-[9px]" style={{ color: 'var(--color-signal-red)' }}>{noticeError}</div>}
            </section>

            {/* Contract entity */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert size={13} style={{ color: 'var(--color-authority-blue)' }} />
                <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Maintenance Entity</h3>
              </div>
              <div className="surface-nested p-4 border-l-4" style={{ borderColor: 'var(--color-hazard-amber)' }}>
                <div className="flex justify-between items-start mb-2">
                  <div className="text-sm font-bold text-ink">{caseData.contractor}</div>
                  <span className={`badge ${caseData.dlpStatus === 'Active' ? 'badge-dlp' : 'badge-none'}`}>
                    {caseData.dlpStatus === 'None' ? 'No Contract' : `DLP ${caseData.dlpStatus}`}
                  </span>
                </div>
                <div className="text-[9px] text-ink-soft mono-text mb-2">
                  CONTRACT: {caseData.contractId ?? 'Unavailable'}
                </div>
                {caseData.dlpExpiry && (
                  <div className="flex items-center gap-2 text-[9px] text-ink-soft">
                    <Calendar size={11} />
                    <span>Expiry: {caseData.dlpExpiry}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Prior flags */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <HistoryIcon size={13} style={{ color: 'var(--color-authority-blue)' }} />
                <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">Prior Segment Flags</h3>
              </div>
              <div className="space-y-2">
                {caseData.segmentHistory.length > 0 ? (
                  caseData.segmentHistory.map((related) => (
                    <button
                      key={related.inspectionId}
                      onClick={() => onSelectRelatedCase(related.inspectionId)}
                      className="w-full p-3 bg-stone-50 border border-hairline text-[9px] text-left hover:border-authority-blue transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium mono-text">
                          ARIA-{related.inspectionId.toString().padStart(6, '0')} — {related.totalDetections} detection(s)
                        </span>
                        <span className={pipelineStatusClass(related.pipelineStatus)}>
                          <span className="pipeline-dot" />
                          {pipelineLabel(related.pipelineStatus)}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center justify-between text-ink-soft">
                        <span>Severity {related.severity} · {related.recommendation}</span>
                        <span className="mono-text">{formatDate(related.created)}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="text-[9px] text-ink-soft italic">No prior flags recorded for this segment.</div>
                )}
              </div>
            </section>
          </div>

          {/* Notice action footer */}
          <div className="mt-auto p-5 bg-stone-50 border-t border-hairline space-y-3">
            {caseData.noticeUrl ? (
              <button
                onClick={handleOpenNotice}
                disabled={openingNotice}
                className="btn-primary text-[9px] uppercase tracking-wider py-3 flex items-center justify-center gap-2 w-full"
              >
                {openingNotice ? <LoaderCircle size={13} className="animate-spin" /> : <ExternalLink size={13} />}
                {openingNotice ? 'Opening Notice…' : 'Open Notice PDF'}
              </button>
            ) : (
              <div className="rounded-sm border border-hairline bg-white px-4 py-3 text-[9px] uppercase tracking-wider text-ink-soft">
                No contractor notice available for this inspection state.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
