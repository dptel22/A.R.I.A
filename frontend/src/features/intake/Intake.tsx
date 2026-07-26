import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, Camera, ChevronDown, ChevronUp,
  Crosshair, LoaderCircle, MapPin, Radio, Users, X,
} from 'lucide-react';
import {
  dismissCluster, fetchClusters, fetchDismissedClusters, promoteCluster,
} from '../../shared/api';
import { DismissReason } from '../../shared/api/mockClient';
import { formatDate, sourceLabel } from '../../shared/lib/caseDisplay';
import { SegmentMatch, SubmissionCluster, SubmissionSource } from '../../shared/types/app';

interface IntakeProps {
  onSelectCase: (inspectionId: number) => void;
}

/* ── Source icon mapping ── */
function SourceIcon({ source, size = 13 }: { source: SubmissionSource; size?: number }) {
  if (source === 'citizen_submission') return <Users size={size} className="text-ink-soft" />;
  if (source === 'roadcam_survey')     return <Camera size={size} className="text-ink-soft" />;
  return <Radio size={size} className="text-ink-soft" />;
}

/* ── Schematic cluster map (SVG) ── */
function ClusterMap({ cluster, highlightSegmentId }: { cluster: SubmissionCluster; highlightSegmentId: number | null }) {
  const W = 280, H = 160, PAD = 20;

  // Project lat/lng to SVG coords within the combined bbox
  const allLats = [cluster.centerLat, ...cluster.segmentMatches.flatMap((m) => [])];
  const allLngs = [cluster.centerLng];
  cluster.segmentMatches.forEach(() => { /* bboxes not in SegmentMatch, shown schematically */ });

  const cx = W / 2, cy = H / 2;

  return (
    <svg
      width={W} height={H} viewBox={`0 0 ${W} ${H}`}
      className="w-full border border-hairline rounded-sm bg-stone-50"
    >
      {/* Segment bbox outlines — schematic, evenly spaced */}
      {cluster.segmentMatches.map((m, i) => {
        const offset = (i - (cluster.segmentMatches.length - 1) / 2) * 30;
        const isHighlighted = highlightSegmentId === m.segmentId;
        return (
          <rect
            key={m.segmentId}
            x={cx - 55 + offset} y={cy - 36}
            width={90} height={70}
            rx={3}
            fill={isHighlighted ? 'rgba(11,59,92,0.08)' : 'rgba(216,212,200,0.4)'}
            stroke={isHighlighted ? 'var(--color-authority-blue)' : 'var(--color-hairline)'}
            strokeWidth={isHighlighted ? 1.8 : 1}
            strokeDasharray={isHighlighted ? '0' : '4 2'}
          />
        );
      })}
      {cluster.segmentMatches.length === 0 && (
        <rect x={cx - 50} y={cy - 32} width={100} height={64} rx={3}
              fill="none" stroke="var(--color-hairline)" strokeWidth={1} strokeDasharray="4 2" />
      )}

      {/* Submission dots */}
      {cluster.submissions.map((s, i) => {
        const angle = (i / Math.max(cluster.submissions.length, 1)) * Math.PI * 2;
        const r = cluster.submissions.length > 1 ? 18 : 0;
        const sx = cx + r * Math.cos(angle);
        const sy = cy + r * Math.sin(angle);
        return (
          <g key={s.id}>
            <circle cx={sx} cy={sy} r={4} fill="var(--color-ink-soft)" opacity={0.7} />
            {s.gpsMismatchFlag && (
              <circle cx={sx} cy={sy} r={7} fill="none"
                      stroke="var(--color-hazard-amber)" strokeWidth={1.5} />
            )}
          </g>
        );
      })}

      {/* Centroid crosshair */}
      <line x1={cx - 8} y1={cy} x2={cx + 8} y2={cy}
            stroke="var(--color-authority-blue)" strokeWidth={1.5} />
      <line x1={cx} y1={cy - 8} x2={cx} y2={cy + 8}
            stroke="var(--color-authority-blue)" strokeWidth={1.5} />

      {/* Labels */}
      {cluster.segmentMatches.map((m, i) => {
        const offset = (i - (cluster.segmentMatches.length - 1) / 2) * 30;
        return (
          <text key={m.segmentId}
                x={cx + 0 + offset} y={cy + 50}
                textAnchor="middle"
                fontSize={7}
                fill="var(--color-ink-soft)"
                fontFamily="var(--font-mono)">
            {m.segmentName.slice(0, 14)}
          </text>
        );
      })}
      {cluster.segmentMatches.length === 0 && (
        <text x={cx} y={cy + 44} textAnchor="middle" fontSize={7}
              fill="var(--color-ink-soft)" fontFamily="var(--font-mono)">No segment matched</text>
      )}

      {/* Legend */}
      <g transform={`translate(${W - PAD - 60}, ${PAD})`}>
        <circle cx={4} cy={4} r={3} fill="var(--color-ink-soft)" />
        <text x={10} y={7.5} fontSize={7} fill="var(--color-ink-soft)" fontFamily="var(--font-mono)">Submission</text>
        <circle cx={4} cy={14} r={3} fill="none" stroke="var(--color-hazard-amber)" strokeWidth={1.5} />
        <text x={10} y={17.5} fontSize={7} fill="var(--color-ink-soft)" fontFamily="var(--font-mono)">GPS mismatch</text>
      </g>
    </svg>
  );
}

/* ── Dismiss modal ── */
const DISMISS_REASONS: { value: DismissReason; label: string }[] = [
  { value: 'spam',              label: 'Spam / test submission' },
  { value: 'duplicate',        label: 'Duplicate of an existing case' },
  { value: 'not_a_road_defect',label: 'Not a road defect' },
  { value: 'other',            label: 'Other' },
];

function DismissModal({
  onConfirm,
  onCancel,
  loading,
}: {
  onConfirm: (reason: DismissReason) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState<DismissReason>('spam');
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm p-6">
      <div className="w-full max-w-sm surface-base p-5 space-y-4">
        <div className="flex items-start justify-between">
          <h2 className="text-sm font-headline font-bold text-ink">Dismiss Cluster</h2>
          <button onClick={onCancel} className="text-ink-soft hover:text-ink"><X size={16} /></button>
        </div>
        <p className="text-xs text-ink-soft">Select a reason. Dismissed clusters remain visible in the audit section.</p>
        <div className="space-y-2">
          {DISMISS_REASONS.map((r) => (
            <label key={r.value} className="flex items-center gap-3 cursor-pointer group">
              <input
                type="radio" name="reason" value={r.value}
                checked={reason === r.value}
                onChange={() => setReason(r.value)}
                className="accent-authority-blue"
              />
              <span className="text-xs text-ink group-hover:text-ink">{r.label}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-secondary text-xs" onClick={onCancel} disabled={loading}>Cancel</button>
          <button
            className="btn-warning text-xs flex items-center gap-2"
            onClick={() => onConfirm(reason)}
            disabled={loading}
          >
            {loading ? <LoaderCircle size={13} className="animate-spin" /> : null}
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Promote confirm modal ── */
function PromoteModal({
  cluster,
  selectedSegmentId,
  onConfirm,
  onCancel,
  loading,
}: {
  cluster: SubmissionCluster;
  selectedSegmentId: number;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const noMatch = cluster.segmentMatches.length === 0;
  const seg = cluster.segmentMatches.find((m) => m.segmentId === selectedSegmentId);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm p-6">
      <div className="w-full max-w-sm surface-base p-5 space-y-4">
        <div className="flex items-start justify-between">
          <h2 className="text-sm font-headline font-bold text-ink">Promote to Case</h2>
          <button onClick={onCancel} className="text-ink-soft hover:text-ink"><X size={16} /></button>
        </div>
        <div className="surface-nested p-4 rounded-sm space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-ink-soft">Segment</span>
            <span className="font-medium text-ink">{noMatch ? 'No mapped segment' : seg?.segmentName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">Contractor</span>
            <span className="font-medium text-ink">{noMatch ? 'No contract on file' : seg?.contractorName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">DLP Active</span>
            <span className={`badge ${!noMatch && seg?.isDlpActive ? 'badge-dlp' : 'badge-none'}`}>
              {!noMatch && seg?.isDlpActive ? 'Active' : 'None'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">Submissions</span>
            <span className="font-medium text-ink mono-text">{cluster.submissionCount}</span>
          </div>
        </div>
        <p className="text-[10px] text-ink-soft">
          {noMatch
            ? 'No road segment matched these coordinates. This will create a no-contract inspection event requiring manual inspection — no enforcement notice will be generated.'
            : 'This will create an inspection event for all submissions in this cluster, attached to the selected segment and contract.'}
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-secondary text-xs" onClick={onCancel} disabled={loading}>Cancel</button>
          <button
            className="btn-primary text-xs flex items-center gap-2"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? <LoaderCircle size={13} className="animate-spin" /> : null}
            {noMatch ? 'Promote as No-Contract Case' : 'Confirm Promotion'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Intake component ── */
export default function Intake({ onSelectCase: _onSelectCase }: IntakeProps) {
  const [clusters, setClusters] = useState<SubmissionCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [showDismissModal, setShowDismissModal] = useState(false);
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showDismissed, setShowDismissed] = useState(false);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<{ cluster: SubmissionCluster; reason: DismissReason; dismissedAt: string }[]>([]);

  useEffect(() => {
    setLoading(true);
    fetchClusters()
      .then(setClusters)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load clusters.'))
      .finally(() => setLoading(false));
    fetchDismissedClusters()
      .then(setDismissed)
      .catch(() => setDismissed([]));
  }, []);

  const selected = clusters.find((c) => c.id === selectedId) ?? null;

  // Auto-select segment if exactly one match
  useEffect(() => {
    if (selected) {
      setSelectedSegmentId(selected.segmentMatches.length === 1 ? selected.segmentMatches[0].segmentId : null);
    }
  }, [selected?.id]);

  const unreviewedClusters = clusters
    .filter((c) => c.submissions.some((s) => s.status === 'unreviewed'))
    .sort((a, b) => b.submissionCount - a.submissionCount || new Date(b.lastSubmittedAt).getTime() - new Date(a.lastSubmittedAt).getTime());

  async function handleDismiss(reason: DismissReason) {
    if (!selectedId) return;
    setActionLoading(true);
    try {
      await dismissCluster(selectedId, reason);
      const [refreshedClusters, refreshedDismissed] = await Promise.all([
        fetchClusters(),
        fetchDismissedClusters().catch(() => dismissed),
      ]);
      setClusters(refreshedClusters);
      setDismissed(refreshedDismissed);
      setSelectedId(null);
    } finally {
      setActionLoading(false);
      setShowDismissModal(false);
    }
  }

  async function handlePromote() {
    if (!selectedId || !selected) return;
    const noMatch = selected.segmentMatches.length === 0;
    if (!noMatch && selectedSegmentId === null) return;
    setActionLoading(true);
    try {
      await promoteCluster(selectedId, noMatch ? null : selectedSegmentId);
      const refreshed = await fetchClusters();
      setClusters(refreshed);
      setSelectedId(null);
    } finally {
      setActionLoading(false);
      setShowPromoteModal(false);
    }
  }

  function segmentMatchPreview(cluster: SubmissionCluster) {
    if (cluster.segmentMatches.length === 0) return 'No segment matched';
    if (cluster.segmentMatches.length === 1) return cluster.segmentMatches[0].segmentName;
    return 'Multiple segments — resolve on review';
  }

  function segmentMatchColor(cluster: SubmissionCluster) {
    if (cluster.segmentMatches.length === 0)  return 'text-ink-soft';
    if (cluster.segmentMatches.length === 1)  return 'text-ink';
    return 'text-hazard-amber';
  }

  const canPromote = selected !== null && (
    selected.segmentMatches.length <= 1 ? true :
    selectedSegmentId !== null
  );

  return (
    <div className="h-full flex overflow-hidden">
      {/* ── Left: Cluster list ── */}
      <div className="w-80 bg-white border-r border-hairline flex flex-col overflow-hidden shrink-0">
        <div className="px-5 py-4 border-b border-hairline shrink-0">
          <h1 className="text-base font-headline font-bold" style={{ color: 'var(--color-authority-blue)' }}>
            Intake
          </h1>
          <p className="text-[10px] text-ink-soft mt-0.5">
            {loading ? 'Loading…' : `${unreviewedClusters.length} cluster${unreviewedClusters.length !== 1 ? 's' : ''} awaiting triage`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-40 gap-2 text-ink-soft text-xs">
              <LoaderCircle size={16} className="animate-spin" />
              Loading clusters…
            </div>
          ) : error ? (
            <div className="p-5 text-xs" style={{ color: 'var(--color-signal-red)' }}>{error}</div>
          ) : unreviewedClusters.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <Crosshair size={32} className="text-hairline mb-3" />
              <div className="text-sm font-bold text-ink-soft">No unreviewed submissions right now</div>
              <p className="text-[10px] text-ink-soft mt-2 leading-relaxed">
                Clusters appear here when citizen or road-cam submissions are grouped by proximity and await engineer triage.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-hairline">
              {unreviewedClusters.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => setSelectedId(c.id)}
                    className={`w-full text-left p-4 transition-colors hover:bg-stone-50 ${
                      selectedId === c.id ? 'bg-stone-100 border-l-2' : ''
                    }`}
                    style={selectedId === c.id ? { borderColor: 'var(--color-authority-blue)' } : {}}
                  >
                    <div className="flex gap-3">
                      {/* Thumbnail */}
                      <div className="w-14 h-12 bg-stone-200 border border-hairline rounded-sm overflow-hidden shrink-0">
                        <img
                          src={c.submissions[0]?.imageUrl}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[9px] font-bold mono-text text-ink-soft">CLU-{String(c.id).padStart(4, '0')}</span>
                          <span
                            className="text-[9px] font-bold px-1.5 py-0.5 rounded-sm text-white"
                            style={{ background: 'var(--color-authority-blue)' }}
                          >
                            {c.submissionCount}
                          </span>
                          {/* Source icons */}
                          <div className="flex gap-1">
                            {(Array.from(new Set(c.sourceTypes)) as SubmissionSource[]).map((src) => (
                              <React.Fragment key={src}>
                                <SourceIcon source={src} size={11} />
                              </React.Fragment>
                            ))}
                          </div>
                        </div>
                        <div className={`text-[10px] truncate font-medium ${segmentMatchColor(c)}`}>
                          {segmentMatchPreview(c)}
                        </div>
                        <div className="text-[9px] text-ink-soft mono-text mt-0.5">
                          {formatDate(c.firstSubmittedAt).slice(0, 12)} →{' '}
                          {formatDate(c.lastSubmittedAt).slice(0, 12)}
                        </div>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Dismissed section */}
        <div className="border-t border-hairline shrink-0">
          <button
            className="w-full flex items-center justify-between px-5 py-3 text-[9px] font-bold uppercase tracking-wider text-ink-soft hover:bg-stone-50 transition-colors"
            onClick={() => setShowDismissed(!showDismissed)}
          >
            <span>Recently Dismissed ({dismissed.length})</span>
            {showDismissed ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {showDismissed && (
            <div className="max-h-48 overflow-y-auto divide-y divide-hairline">
              {dismissed.length === 0 ? (
                <div className="px-5 py-4 text-[9px] text-ink-soft italic">No dismissed clusters in this session.</div>
              ) : (
                dismissed.map(({ cluster, reason, dismissedAt }) => (
                  <div key={cluster.id} className="px-5 py-3">
                    <div className="text-[9px] font-bold mono-text text-ink-soft mb-0.5">CLU-{String(cluster.id).padStart(4, '0')}</div>
                    <div className="text-[9px] text-ink-soft">{reason.replace(/_/g, ' ')}</div>
                    <div className="text-[8px] text-ink-soft mono-text">{formatDate(dismissedAt)}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Right: Detail pane ── */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-paper">
        {!selected ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-12">
            <MapPin size={40} className="text-hairline mb-4" />
            <div className="text-sm font-bold text-ink-soft uppercase tracking-widest">No cluster selected</div>
            <p className="text-xs text-ink-soft mt-2 max-w-xs leading-relaxed">
              Select a cluster from the left to review submissions, check GPS data, and decide whether to promote or dismiss.
            </p>
          </div>
        ) : (
          <div className="p-6 space-y-6 max-w-3xl">
            {/* Cluster header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[9px] mono-text text-ink-soft mb-1">CLU-{String(selected.id).padStart(4, '0')}</div>
                <h2 className="text-lg font-headline font-bold text-ink">
                  {selected.submissionCount} Submission{selected.submissionCount !== 1 ? 's' : ''}
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  {(Array.from(new Set(selected.sourceTypes)) as SubmissionSource[]).map((src) => (
                    <React.Fragment key={src}>
                      <span className="flex items-center gap-1 text-[9px] text-ink-soft">
                        <SourceIcon source={src} size={11} />
                        {sourceLabel(src)}
                      </span>
                    </React.Fragment>
                  ))}
                  <span className="text-[9px] text-ink-soft mono-text">
                    {formatDate(selected.firstSubmittedAt)} — {formatDate(selected.lastSubmittedAt)}
                  </span>
                </div>
              </div>
            </div>

            {/* Photo grid */}
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">Submissions</div>
              <div className="grid grid-cols-3 gap-3">
                {selected.submissions.map((s) => (
                  <div key={s.id} className="relative">
                    <button
                      className="w-full aspect-[4/3] overflow-hidden border border-hairline rounded-sm bg-stone-200"
                      onClick={() => setLightboxUrl(s.imageUrl)}
                    >
                      <img src={s.imageUrl} alt="" className="w-full h-full object-cover hover:opacity-90 transition-opacity" />
                    </button>
                    {s.gpsMismatchFlag && (
                      <div className="absolute top-1.5 left-1.5 flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[8px] font-bold text-white"
                           style={{ background: 'var(--color-hazard-amber)' }}>
                        <AlertTriangle size={9} />
                        GPS mismatch
                      </div>
                    )}
                    <div className="mt-1 text-[8px] text-ink-soft mono-text">
                      {sourceLabel(s.source)} · {formatDate(s.submittedAt).slice(0, 12)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Schematic map */}
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-2">Cluster Location</div>
              <ClusterMap cluster={selected} highlightSegmentId={selectedSegmentId} />
              <div className="mt-1.5 text-[9px] text-ink-soft mono-text">
                Centroid: {selected.centerLat.toFixed(5)}, {selected.centerLng.toFixed(5)}
              </div>
            </div>

            {/* Segment match */}
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">Segment Matches</div>
              {selected.segmentMatches.length === 0 ? (
                <div className="surface-nested p-4 text-xs text-ink-soft rounded-sm">
                  No road segment matched this cluster's coordinates. You may promote it as a no-contract case for manual inspection, or dismiss it.
                </div>
              ) : selected.segmentMatches.length === 1 ? (
                <div className="surface-nested p-4 rounded-sm">
                  <SegmentMatchRow m={selected.segmentMatches[0]} selected={true} onSelect={() => {}} />
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-[10px] font-medium" style={{ color: 'var(--color-hazard-amber)' }}>
                    Multiple segments overlap — select one before promoting.
                  </div>
                  {selected.segmentMatches.map((m) => (
                    <button
                      key={m.segmentId}
                      onClick={() => setSelectedSegmentId(m.segmentId)}
                      className={`w-full text-left surface-nested p-4 rounded-sm border transition-colors ${
                        selectedSegmentId === m.segmentId ? 'border-authority-blue' : 'border-hairline hover:border-ink-soft'
                      }`}
                    >
                      <SegmentMatchRow m={m} selected={selectedSegmentId === m.segmentId} onSelect={() => setSelectedSegmentId(m.segmentId)} />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2 border-t border-hairline">
              <button
                className="btn-primary flex items-center gap-2 text-xs"
                disabled={!canPromote || actionLoading}
                onClick={() => setShowPromoteModal(true)}
              >
                Promote to Case
              </button>
              <button
                className="btn-secondary flex items-center gap-2 text-xs"
                disabled={actionLoading}
                onClick={() => setShowDismissModal(true)}
              >
                Dismiss Cluster
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm p-8"
          onClick={() => setLightboxUrl(null)}
        >
          <img src={lightboxUrl} alt="" className="max-w-full max-h-full rounded-sm shadow-2xl object-contain" />
        </div>
      )}

      {/* Modals */}
      {showDismissModal && (
        <DismissModal
          onConfirm={handleDismiss}
          onCancel={() => setShowDismissModal(false)}
          loading={actionLoading}
        />
      )}
      {showPromoteModal && selected && (selected.segmentMatches.length === 0 || selectedSegmentId !== null) && (
        <PromoteModal
          cluster={selected}
          selectedSegmentId={selected.segmentMatches.length === 0 ? -1 : selectedSegmentId}
          onConfirm={handlePromote}
          onCancel={() => setShowPromoteModal(false)}
          loading={actionLoading}
        />
      )}
    </div>
  );
}

function SegmentMatchRow({
  m, selected, onSelect,
}: {
  m: SegmentMatch;
  selected: boolean;
  onSelect: () => void;
}) {
  void onSelect;
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className={`text-xs font-bold ${selected ? '' : 'text-ink'}`}
             style={selected ? { color: 'var(--color-authority-blue)' } : {}}>
          {m.segmentName}
        </div>
        <div className="text-[9px] text-ink-soft">{m.contractorName}</div>
      </div>
      <span className={`badge ${m.isDlpActive ? 'badge-dlp' : 'badge-none'}`}>
        DLP {m.isDlpActive ? 'Active' : 'Expired'}
      </span>
    </div>
  );
}
