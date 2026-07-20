import React, { useEffect, useState } from 'react';
import { ChevronRight, Filter, LoaderCircle, MapPin } from 'lucide-react';
import { fetchSegmentDetail, fetchSegments } from '../../shared/api';
import { formatDate } from '../../shared/lib/caseDisplay';
import { ContractSummary, RoadCase, RoadSegment } from '../../shared/types/app';

interface RoadSegmentsProps {
  onSelectCase: (inspectionId: number, preloadedCase?: RoadCase) => void;
}

/* ── Schematic bbox map ── */
function BboxMap({ segment }: { segment: RoadSegment }) {
  const { bbox } = segment;
  const W = 240, H = 120, PAD = 16;
  const usableW = W - PAD * 2;
  const usableH = H - PAD * 2;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
         className="w-full border border-hairline rounded-sm bg-stone-50">
      {/* Bbox outline */}
      <rect x={PAD} y={PAD} width={usableW} height={usableH}
            rx={4} fill="rgba(11,59,92,0.06)"
            stroke="var(--color-authority-blue)" strokeWidth={1.5} />
      {/* Center crosshair */}
      <line x1={W / 2 - 7} y1={H / 2} x2={W / 2 + 7} y2={H / 2}
            stroke="var(--color-authority-blue)" strokeWidth={1.5} />
      <line x1={W / 2} y1={H / 2 - 7} x2={W / 2} y2={H / 2 + 7}
            stroke="var(--color-authority-blue)" strokeWidth={1.5} />
      {/* Corner coords */}
      <text x={PAD + 2} y={PAD + 10} fontSize={6} fill="var(--color-ink-soft)" fontFamily="var(--font-mono)">
        {bbox.maxLat.toFixed(3)},{bbox.minLng.toFixed(3)}
      </text>
      <text x={PAD + 2} y={H - PAD - 2} fontSize={6} fill="var(--color-ink-soft)" fontFamily="var(--font-mono)">
        {bbox.minLat.toFixed(3)},{bbox.maxLng.toFixed(3)}
      </text>
    </svg>
  );
}

/* ── DLP status flag ── */
function DlpFlag({ isDlpActive, dlpEndDate }: { isDlpActive: boolean; dlpEndDate: string | null }) {
  return (
    <span className={`badge ${isDlpActive ? 'badge-dlp' : 'badge-none'}`}>
      {isDlpActive ? 'DLP Active' : dlpEndDate ? 'DLP Expired' : 'No DLP'}
    </span>
  );
}

/* ── Contract history entry ── */
function ContractRow({ contract }: { contract: ContractSummary }) {
  return (
    <div className={`p-3 border-l-2 rounded-r-sm surface-nested mb-2`}
         style={{ borderColor: contract.isDlpActive ? 'var(--color-hazard-amber)' : 'var(--color-hairline)' }}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-bold text-ink">{contract.contractorName}</div>
          <div className="text-[9px] text-ink-soft mono-text">{contract.contractorEmail}</div>
        </div>
        <DlpFlag isDlpActive={contract.isDlpActive} dlpEndDate={contract.dlpEndDate} />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[9px] text-ink-soft">
        <div><span className="font-bold">Contract ID</span> <span className="mono-text">{contract.id}</span></div>
        {contract.dlpEndDate && <div><span className="font-bold">DLP End</span> <span className="mono-text">{contract.dlpEndDate}</span></div>}
        {contract.contractValue && (
          <div><span className="font-bold">Value</span>{' '}
            <span className="mono-text">₹{contract.contractValue.toLocaleString('en-IN')}</span>
          </div>
        )}
        <div><span className="font-bold">Since</span> <span className="mono-text">{formatDate(contract.createdAt).slice(0, 12)}</span></div>
      </div>
    </div>
  );
}

/* ── Main component ── */
export default function RoadSegments({ onSelectCase }: RoadSegmentsProps) {
  const [segments, setSegments] = useState<RoadSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<{ segment: RoadSegment; cases: RoadCase[] } | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [wardFilter, setWardFilter] = useState('All');
  const [zoneFilter, setZoneFilter] = useState('All');

  useEffect(() => {
    fetchSegments()
      .then(setSegments)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load segments.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    setLoadingDetail(true);
    fetchSegmentDetail(selectedId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [selectedId]);

  const wards  = Array.from(new Set(segments.map((s) => s.wardId)));
  const zones  = Array.from(new Set(segments.map((s) => s.zoneId)));

  const filtered = segments
    .filter((s) => wardFilter === 'All' || s.wardId === wardFilter)
    .filter((s) => zoneFilter === 'All' || s.zoneId === zoneFilter);

  const selectClass = 'bg-paper border border-hairline text-xs rounded-sm px-2 py-1 text-ink focus:outline-none focus:ring-1';

  return (
    <div className="h-full flex overflow-hidden">
      {/* ── Left: Segment list ── */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-hairline">
        {/* Header + filters */}
        <div className="p-6 pb-4 shrink-0">
          <h1 className="text-2xl font-headline font-bold tracking-tight mb-1"
              style={{ color: 'var(--color-authority-blue)' }}>
            Road Segments
          </h1>
          <p className="text-ink-soft text-sm mb-5">
            Read-only lookup. Click a segment to view contract history and linked cases.
          </p>

          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 text-[9px] font-bold text-ink-soft uppercase tracking-wider">
              <Filter size={12} />
              Filters
            </div>
            <select value={wardFilter} onChange={(e) => setWardFilter(e.target.value)} className={selectClass}>
              <option value="All">Ward: All</option>
              {wards.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
            <select value={zoneFilter} onChange={(e) => setZoneFilter(e.target.value)} className={selectClass}>
              <option value="All">Zone: All</option>
              {zones.map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
            <button
              className="ml-auto text-xs font-bold hover:underline"
              style={{ color: 'var(--color-authority-blue)' }}
              onClick={() => { setWardFilter('All'); setZoneFilter('All'); }}
            >
              Clear
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="surface-base overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-stone-100 border-b border-hairline text-[9px] font-bold uppercase tracking-wider text-ink-soft">
                  <th className="px-4 py-3">Segment Name</th>
                  <th className="px-4 py-3">Ward</th>
                  <th className="px-4 py-3">Zone</th>
                  <th className="px-4 py-3">Active Contractor</th>
                  <th className="px-4 py-3">DLP Status</th>
                  <th className="px-4 py-3">Cases</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="text-xs">
                {loading ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-ink-soft">
                    <div className="flex items-center justify-center gap-2"><LoaderCircle size={15} className="animate-spin" /> Loading segments…</div>
                  </td></tr>
                ) : error ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center" style={{ color: 'var(--color-signal-red)' }}>{error}</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-ink-soft">No segments match the current filters.</td></tr>
                ) : (
                  filtered.map((seg) => (
                    <tr
                      key={seg.id}
                      onClick={() => setSelectedId(seg.id)}
                      className={`border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-colors group ${
                        selectedId === seg.id ? 'bg-stone-100' : ''
                      }`}
                    >
                      <td className="px-4 py-3 font-bold" style={{ color: 'var(--color-authority-blue)' }}>{seg.name}</td>
                      <td className="px-4 py-3 text-ink-soft mono-text">{seg.wardId}</td>
                      <td className="px-4 py-3 text-ink-soft mono-text">{seg.zoneId}</td>
                      <td className="px-4 py-3">{seg.activeContract?.contractorName ?? <span className="text-ink-soft italic">No contract</span>}</td>
                      <td className="px-4 py-3">
                        {seg.activeContract ? (
                          <DlpFlag isDlpActive={seg.activeContract.isDlpActive} dlpEndDate={seg.activeContract.dlpEndDate} />
                        ) : (
                          <span className="badge badge-none">No Contract</span>
                        )}
                      </td>
                      <td className="px-4 py-3 mono-text text-ink-soft">{seg.caseCount}</td>
                      <td className="px-4 py-3 text-right">
                        <ChevronRight size={14} className="text-hairline group-hover:text-ink transition-colors" />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Right: Detail pane ── */}
      <div className="w-[440px] bg-white flex flex-col overflow-y-auto shrink-0">
        {!selectedId ? (
          <div className="h-full flex flex-col items-center justify-center p-10 text-center">
            <MapPin size={36} className="text-hairline mb-4" />
            <div className="text-sm font-bold text-ink-soft uppercase tracking-widest">No Segment Selected</div>
            <p className="text-xs text-ink-soft mt-2">Click a segment to view its contract history and linked cases.</p>
          </div>
        ) : loadingDetail ? (
          <div className="h-full flex items-center justify-center gap-2 text-ink-soft">
            <LoaderCircle size={16} className="animate-spin" />
            <span className="text-xs">Loading segment detail…</span>
          </div>
        ) : !detail ? (
          <div className="p-6 text-xs" style={{ color: 'var(--color-signal-red)' }}>Failed to load segment detail.</div>
        ) : (
          <div className="p-5 space-y-6">
            {/* Segment metadata */}
            <div>
              <div className="text-[9px] mono-text text-ink-soft mb-1">SEG-{String(detail.segment.id).padStart(4, '0')}</div>
              <h2 className="text-lg font-headline font-bold text-ink mb-1">{detail.segment.name}</h2>
              <div className="flex gap-3 text-[9px] text-ink-soft mono-text">
                <span>Ward: {detail.segment.wardId}</span>
                <span>Zone: {detail.segment.zoneId}</span>
              </div>
            </div>

            <BboxMap segment={detail.segment} />

            {/* Contract history */}
            <section>
              <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">
                Contract History ({detail.segment.contractHistory.length})
              </h3>
              {detail.segment.contractHistory.length === 0 ? (
                <div className="text-[9px] text-ink-soft italic">No contracts recorded.</div>
              ) : (
                detail.segment.contractHistory.map((c) => (
                  <React.Fragment key={c.id}>
                    <ContractRow contract={c} />
                  </React.Fragment>
                ))
              )}
            </section>

            {/* Linked cases */}
            <section>
              <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft mb-3">
                Linked Cases ({detail.cases.length})
              </h3>
              {detail.cases.length === 0 ? (
                <div className="text-[9px] text-ink-soft italic">No cases linked to this segment.</div>
              ) : (
                <div className="space-y-1">
                  {detail.cases.map((c) => (
                    <button
                      key={c.inspectionId}
                      onClick={() => onSelectCase(c.inspectionId, c)}
                      className="w-full flex items-center justify-between p-3 bg-stone-50 border border-hairline rounded-sm hover:border-authority-blue transition-colors text-left group"
                    >
                      <div>
                        <div className="text-[10px] font-bold mono-text" style={{ color: 'var(--color-authority-blue)' }}>
                          {c.id}
                        </div>
                        <div className="text-[9px] text-ink-soft mt-0.5">
                          {c.severity && <span className={`badge badge-${c.severity.toLowerCase()} mr-2`}>{c.severity}</span>}
                          {c.created && <span className="mono-text">{formatDate(c.created).slice(0, 12)}</span>}
                        </div>
                      </div>
                      <ChevronRight size={13} className="text-hairline group-hover:text-ink transition-colors shrink-0" />
                    </button>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
