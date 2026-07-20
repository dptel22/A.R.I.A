import React, { useEffect, useMemo, useState } from 'react';
import { ExternalLink, FileText, LoaderCircle, Map as MapIcon, Printer } from 'lucide-react';
import { openNoticePdf } from '../../shared/api';
import { formatDate, pipelineLabel, pipelineStatusClass } from '../../shared/lib/caseDisplay';
import { RoadCase } from '../../shared/types/app';

interface DecisionHistoryProps {
  cases: RoadCase[];
  caseDetails: Record<number, RoadCase>;
  onLoadCaseDetail: (inspectionId: number) => Promise<void>;
}

export default function DecisionHistory({ cases, caseDetails, onLoadCaseDetail }: DecisionHistoryProps) {
  const historyCases = useMemo(
    () => [...cases].sort((l, r) => new Date(r.created).getTime() - new Date(l.created).getTime()),
    [cases],
  );
  const noticeReadyCount = useMemo(() => historyCases.filter((c) => Boolean(c.noticeUrl)).length, [historyCases]);

  const [selectedId, setSelectedId] = useState<number | null>(historyCases[0]?.inspectionId || null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [noticeError, setNoticeError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && historyCases.length > 0) setSelectedId(historyCases[0].inspectionId);
  }, [historyCases, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    if (caseDetails[selectedId]?.segmentHistory.length) return;

    let cancelled = false;
    setLoadingDetail(true);
    onLoadCaseDetail(selectedId)
      .catch(() => undefined)
      .finally(() => { if (!cancelled) setLoadingDetail(false); });
    return () => { cancelled = true; };
  }, [caseDetails, onLoadCaseDetail, selectedId]);

  const selectedCase =
    (selectedId ? caseDetails[selectedId] : null) ||
    historyCases.find((c) => c.inspectionId === selectedId) ||
    null;

  async function handleOpenNotice() {
    if (!selectedCase?.noticeUrl) return;
    setNoticeError(null);
    try { await openNoticePdf(selectedCase.inspectionId); }
    catch (e) { setNoticeError(e instanceof Error ? e.message : 'Failed to open notice.'); }
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* List pane */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-hairline">
        <div className="p-6 pb-4 shrink-0">
          <div className="flex justify-between items-end mb-5">
            <div>
              <h1 className="text-2xl font-headline font-bold tracking-tight mb-1"
                  style={{ color: 'var(--color-authority-blue)' }}>
                Decision History
              </h1>
              <p className="text-ink-soft text-sm">
                Audit-ready inspection archive with failed runs, contractor context, and repeat segment visibility.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 mb-4">
            {[
              { label: 'Archive Size',  value: historyCases.length },
              { label: 'Notice Ready', value: noticeReadyCount },
              { label: 'Ordering',     value: 'Newest first', mono: false },
            ].map(({ label, value, mono }) => (
              <div key={label} className="surface-base p-3">
                <div className="text-[9px] font-bold uppercase tracking-wider text-ink-soft mb-1">{label}</div>
                <div className={`${mono === false ? 'text-xs text-ink-soft' : 'mono-text text-lg font-bold'}`}
                     style={mono === false ? {} : { color: 'var(--color-authority-blue)' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="surface-base overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-stone-100 border-b border-hairline text-[9px] font-bold uppercase tracking-wider text-ink-soft">
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
                    <td colSpan={6} className="px-4 py-12 text-center text-ink-soft">
                      No inspections are available yet.
                    </td>
                  </tr>
                ) : (
                  historyCases.map((item) => (
                    <tr
                      key={item.inspectionId}
                      onClick={() => setSelectedId(item.inspectionId)}
                      className={`border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-colors ${
                        selectedId === item.inspectionId ? 'bg-stone-100' : ''
                      }`}
                    >
                      <td className="px-4 py-3 mono-text font-bold"
                          style={{ color: 'var(--color-authority-blue)' }}>{item.id}</td>
                      <td className="px-4 py-3 font-medium">{item.roadSegment}</td>
                      <td className="px-4 py-3">
                        <span className={pipelineStatusClass(item.pipelineStatus)}>
                          <span className="pipeline-dot" />
                          {pipelineLabel(item.pipelineStatus)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`badge badge-${item.severity.toLowerCase()}`}>{item.severity}</span>
                      </td>
                      <td className="px-4 py-3 text-ink-soft mono-text">{item.priorFlags}</td>
                      <td className="px-4 py-3 text-ink-soft mono-text">{formatDate(item.created)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail pane */}
      <div className="w-[400px] bg-white flex flex-col overflow-y-auto shrink-0">
        {selectedCase ? (
          <div className="p-5 space-y-5">
            <div>
              <div className="text-[9px] font-bold text-ink-soft uppercase tracking-widest mb-1">Selected Case</div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-headline font-bold text-ink">{selectedCase.id}</h2>
                <span className={pipelineStatusClass(selectedCase.pipelineStatus)}>
                  <span className="pipeline-dot" />
                  {pipelineLabel(selectedCase.pipelineStatus)}
                </span>
              </div>
              <div className="text-xs text-ink-soft">{selectedCase.roadSegment}</div>
            </div>

            <div className="aspect-video bg-stone-200 rounded-sm overflow-hidden border border-hairline">
              <img src={selectedCase.evidenceUrl} alt="Evidence" className="w-full h-full object-cover" />
            </div>

            <div className="flex gap-2">
              <a
                className="flex-1 btn-secondary text-[9px] uppercase tracking-wider py-2 flex items-center justify-center gap-2"
                href={`https://www.google.com/maps?q=${selectedCase.coordinates.lat},${selectedCase.coordinates.lng}`}
                target="_blank" rel="noreferrer"
              >
                <MapIcon size={11} />
                Map Link
              </a>
              <button
                className="flex-1 btn-secondary text-[9px] uppercase tracking-wider py-2 flex items-center justify-center gap-2 disabled:opacity-40"
                onClick={handleOpenNotice}
                disabled={!selectedCase.noticeUrl}
              >
                <Printer size={11} />
                {selectedCase.noticeUrl ? 'Open Notice' : 'No Notice'}
              </button>
            </div>

            {loadingDetail && (
              <div className="text-[9px] text-ink-soft flex items-center gap-2">
                <LoaderCircle size={11} className="animate-spin" />
                Loading repeat-segment history…
              </div>
            )}

            <section>
              <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-2">Archive Summary</h3>
              <div className="bg-stone-50 border-l-2 p-3 text-xs text-ink leading-relaxed"
                   style={{ borderColor: 'var(--color-authority-blue)' }}>
                Pipeline status{' '}
                <span className="font-bold">{pipelineLabel(selectedCase.pipelineStatus)}</span>,
                recommendation{' '}
                <span className="font-bold">{selectedCase.recommendation}</span>,
                {' '}{selectedCase.priorFlags} prior flag(s) on same segment.
              </div>
              {selectedCase.failureReason && (
                <div className="mt-2 text-[9px] bg-red-50 border border-red-100 p-3 rounded-sm"
                     style={{ color: 'var(--color-signal-red)' }}>
                  {selectedCase.failureReason}
                </div>
              )}
            </section>

            <section>
              <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">Repeat Segment Timeline</h3>
              <div className="space-y-2">
                {selectedCase.segmentHistory.length > 0 ? (
                  selectedCase.segmentHistory.map((item) => (
                    <div key={item.inspectionId} className="p-3 bg-stone-50 border border-hairline rounded-sm">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[9px] font-bold mono-text" style={{ color: 'var(--color-authority-blue)' }}>
                          ARIA-{item.inspectionId.toString().padStart(6, '0')}
                        </div>
                        <span className={pipelineStatusClass(item.pipelineStatus)}>
                          <span className="pipeline-dot" />
                          {pipelineLabel(item.pipelineStatus)}
                        </span>
                      </div>
                      <div className="mt-1.5 text-[9px] text-ink-soft">
                        Severity {item.severity} · {item.totalDetections} detection(s) · {item.recommendation}
                      </div>
                      <div className="mt-1 text-[9px] text-ink-soft mono-text">{formatDate(item.created)}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-[9px] text-ink-soft italic">No prior segment history available.</div>
                )}
              </div>
            </section>

            <section>
              <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">Generated Artifacts</h3>
              {selectedCase.noticeUrl ? (
                <button
                  onClick={handleOpenNotice}
                  className="w-full flex items-center justify-between p-3 bg-stone-50 border border-hairline rounded-sm group hover:border-authority-blue transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <FileText size={14} className="text-ink-soft group-hover:text-authority-blue" />
                    <div className="text-left">
                      <div className="text-[9px] font-bold text-ink">ARIA Notice PDF</div>
                      <div className="text-[8px] text-ink-soft uppercase">Authenticated frontend download</div>
                    </div>
                  </div>
                  <ExternalLink size={11} className="text-ink-soft" />
                </button>
              ) : (
                <div className="p-3 bg-stone-50 border border-hairline rounded-sm text-[9px] text-ink-soft">
                  No notice artifact available for this inspection.
                </div>
              )}
              {noticeError && <div className="mt-2 text-[9px]" style={{ color: 'var(--color-signal-red)' }}>{noticeError}</div>}
            </section>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center p-10 text-center">
            <FileText size={40} className="text-hairline mb-4" />
            <div className="text-sm font-bold text-ink-soft uppercase tracking-widest">No Case Selected</div>
            <p className="text-xs text-ink-soft mt-2">Select a case from the archive to view details.</p>
          </div>
        )}
      </div>
    </div>
  );
}
