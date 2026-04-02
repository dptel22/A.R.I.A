import {
  BackendHealth,
  Decision,
  DetectionBox,
  DLPStatus,
  PipelineStatus,
  RoadCase,
  SegmentHistoryItem,
  Severity,
} from './types';

const API_BASE = (import.meta.env.VITE_ARIA_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = import.meta.env.VITE_ARIA_API_KEY || '';

type BackendSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';

interface BackendContract {
  contract_id: number | null;
  contractor_name: string | null;
  contractor_email: string | null;
  dlp_end_date: string | null;
  is_dlp_active: boolean;
  is_enforceable: boolean;
}

interface BackendSummaryRow {
  inspection_id: number;
  timestamp: string;
  lat: number;
  lng: number;
  road_name: string;
  ward_id: string;
  zone_id: string;
  total_defects: number;
  highest_severity: BackendSeverity;
  contractor_name: string | null;
  contractor_email: string | null;
  contract_id: number | null;
  dlp_end_date: string | null;
  is_dlp_active: boolean;
  image_url: string | null;
  recommendation: Decision;
  dlp_status: 'ACTIVE' | 'EXPIRED' | 'NONE';
  pipeline_status: PipelineStatus;
  failure_reason: string | null;
  prior_flags: number;
}

interface BackendSummaryResponse {
  total_matching: number;
  returned_count: number;
  limit: number;
  offset: number;
  results: BackendSummaryRow[];
}

interface BackendDetection {
  id?: number;
  class_name: string;
  confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  severity_score: number;
  severity_level: BackendSeverity;
}

interface BackendSegmentHistoryItem {
  inspection_id: number;
  created_at: string;
  pipeline_status: PipelineStatus;
  highest_severity: BackendSeverity;
  total_detections: number;
  recommendation: Decision;
  notice_url: string | null;
}

interface BackendDetailResponse {
  inspection_id: number;
  created_at: string;
  lat: number;
  lng: number;
  image_url: string | null;
  road_segment: string;
  ward_id: string;
  zone_id: string;
  pipeline_status: PipelineStatus;
  failure_reason: string | null;
  total_detections: number;
  primary_defect: BackendDetection | null;
  detections: BackendDetection[];
  contract: BackendContract;
  prior_flags: number;
  segment_history: BackendSegmentHistoryItem[];
  recommendation: Decision;
  notice_url: string | null;
}

interface BackendDetectResponse {
  inspection_id: number;
  pipeline_status: PipelineStatus;
  message: string;
  road_segment: string;
  ward_id: string;
  zone_id: string;
  lat: number;
  lng: number;
  total_detections: number;
  primary_defect: BackendDetection | null;
  all_detections: BackendDetection[];
  image_url: string | null;
  contract: BackendContract;
  recommendation: Decision;
  notice_url: string | null;
}

function buildHeaders(extraHeaders: HeadersInit = {}): HeadersInit {
  return API_KEY ? { 'x-api-key': API_KEY, ...extraHeaders } : extraHeaders;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') {
      return payload.detail;
    }
    if (typeof payload?.detail?.detail === 'string') {
      return payload.detail.detail;
    }
    if (typeof payload?.message === 'string') {
      return payload.message;
    }
  } catch {
    // Fall through to status text.
  }

  return `${response.status} ${response.statusText}`.trim();
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<T>;
}

async function fetchBinary(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: buildHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.blob();
}

function toSeverity(level: BackendSeverity): Severity {
  switch (level) {
    case 'CRITICAL':
      return 'Critical';
    case 'HIGH':
      return 'High';
    case 'MEDIUM':
      return 'Medium';
    case 'LOW':
      return 'Low';
    default:
      return 'None';
  }
}

function toDlpStatus(value: 'ACTIVE' | 'EXPIRED' | 'NONE'): DLPStatus {
  if (value === 'ACTIVE') {
    return 'Active';
  }
  if (value === 'EXPIRED') {
    return 'Expired';
  }
  return 'None';
}

function toCaseId(inspectionId: number): string {
  return `ARIA-${inspectionId.toString().padStart(6, '0')}`;
}

function toRunId(timestamp: string): string {
  return `RUN-${timestamp.slice(0, 10)}`;
}

function placeholderEvidence(label: string): string {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#e5e7eb" />
          <stop offset="100%" stop-color="#cbd5e1" />
        </linearGradient>
      </defs>
      <rect width="800" height="600" fill="url(#bg)" />
      <g opacity="0.4" stroke="#64748b" stroke-width="3">
        <line x1="90" y1="110" x2="710" y2="110" />
        <line x1="90" y1="300" x2="710" y2="300" />
        <line x1="90" y1="490" x2="710" y2="490" />
      </g>
      <text x="400" y="260" font-family="Arial, sans-serif" font-size="36" font-weight="700" fill="#0f172a" text-anchor="middle">
        A.R.I.A. Evidence Pending
      </text>
      <text x="400" y="318" font-family="Arial, sans-serif" font-size="22" fill="#334155" text-anchor="middle">
        ${label}
      </text>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function normalizeDetections(detections: BackendDetection[]): DetectionBox[] {
  return detections.map((detection) => ({
    id: detection.id,
    className: detection.class_name,
    confidence: detection.confidence,
    bboxX: detection.bbox_x,
    bboxY: detection.bbox_y,
    bboxW: detection.bbox_w,
    bboxH: detection.bbox_h,
    severityScore: detection.severity_score,
    severityLevel: toSeverity(detection.severity_level),
  }));
}

function normalizeHistory(items: BackendSegmentHistoryItem[]): SegmentHistoryItem[] {
  return items.map((item) => ({
    inspectionId: item.inspection_id,
    created: item.created_at,
    pipelineStatus: item.pipeline_status,
    severity: toSeverity(item.highest_severity),
    totalDetections: item.total_detections,
    recommendation: item.recommendation,
    noticeUrl: item.notice_url,
  }));
}

function describeDefect(
  totalDetections: number,
  severity: BackendSeverity,
  pipelineStatus: PipelineStatus,
  primaryClass?: string | null,
): string {
  if (pipelineStatus === 'FAILED') {
    return 'Inspection pipeline failed';
  }
  if (totalDetections === 0) {
    return 'No defect detected';
  }
  if (primaryClass) {
    return primaryClass;
  }
  if (severity === 'NONE') {
    return `${totalDetections} detected issue(s)`;
  }
  return `${totalDetections} detected issue(s)`;
}

function mergeCase(base: Partial<RoadCase>, detail: Partial<RoadCase>): RoadCase {
  return {
    inspectionId: detail.inspectionId ?? base.inspectionId ?? 0,
    id: detail.id ?? base.id ?? '',
    pipelineStatus: detail.pipelineStatus ?? base.pipelineStatus ?? 'NO_DETECTIONS',
    failureReason: detail.failureReason ?? base.failureReason ?? null,
    severity: detail.severity ?? base.severity ?? 'None',
    evidenceUrl: detail.evidenceUrl ?? base.evidenceUrl ?? placeholderEvidence('No evidence'),
    roadSegment: detail.roadSegment ?? base.roadSegment ?? 'Unknown road segment',
    ward: detail.ward ?? base.ward ?? 'Unknown ward',
    wardId: detail.wardId ?? base.wardId ?? 'UNKNOWN',
    zoneId: detail.zoneId ?? base.zoneId ?? 'UNKNOWN',
    contractor: detail.contractor ?? base.contractor ?? 'No contract on file',
    contractorEmail: detail.contractorEmail ?? base.contractorEmail ?? null,
    contractId: detail.contractId ?? base.contractId ?? null,
    dlpStatus: detail.dlpStatus ?? base.dlpStatus ?? 'None',
    dlpExpiry: detail.dlpExpiry ?? base.dlpExpiry ?? null,
    recommendation: detail.recommendation ?? base.recommendation ?? 'No Action',
    created: detail.created ?? base.created ?? new Date().toISOString(),
    status: detail.status ?? base.status ?? 'Awaiting Review',
    confidence: detail.confidence ?? base.confidence ?? 0,
    coordinates: detail.coordinates ?? base.coordinates ?? { lat: 0, lng: 0 },
    defectClass: detail.defectClass ?? base.defectClass ?? 'No defect detected',
    runId: detail.runId ?? base.runId ?? 'RUN-UNKNOWN',
    priorFlags: detail.priorFlags ?? base.priorFlags ?? 0,
    notes: detail.notes ?? base.notes,
    totalDetections: detail.totalDetections ?? base.totalDetections ?? 0,
    noticeUrl: detail.noticeUrl ?? base.noticeUrl ?? null,
    isEnforceable: detail.isEnforceable ?? base.isEnforceable ?? false,
    detections: detail.detections ?? base.detections ?? [],
    segmentHistory: detail.segmentHistory ?? base.segmentHistory ?? [],
  };
}

function fromSummary(row: BackendSummaryRow): RoadCase {
  return mergeCase({}, {
    inspectionId: row.inspection_id,
    id: toCaseId(row.inspection_id),
    pipelineStatus: row.pipeline_status,
    failureReason: row.failure_reason,
    severity: toSeverity(row.highest_severity),
    evidenceUrl: row.image_url ? `${API_BASE}${row.image_url}` : placeholderEvidence(row.road_name),
    roadSegment: row.road_name,
    ward: `${row.ward_id} / ${row.zone_id}`,
    wardId: row.ward_id,
    zoneId: row.zone_id,
    contractor: row.contractor_name || 'No contract on file',
    contractorEmail: row.contractor_email,
    contractId: row.contract_id,
    dlpStatus: toDlpStatus(row.dlp_status),
    dlpExpiry: row.dlp_end_date,
    recommendation: row.recommendation,
    created: row.timestamp,
    status: row.pipeline_status === 'FAILED' ? 'Escalated' : 'Awaiting Review',
    confidence: 0,
    coordinates: { lat: row.lat, lng: row.lng },
    defectClass: describeDefect(row.total_defects, row.highest_severity, row.pipeline_status, null),
    runId: toRunId(row.timestamp),
    priorFlags: row.prior_flags,
    totalDetections: row.total_defects,
    noticeUrl: row.pipeline_status === 'SUCCEEDED' && row.total_defects > 0 ? `/api/v1/notices/${row.inspection_id}` : null,
    isEnforceable: row.is_dlp_active,
    detections: [],
    segmentHistory: [],
  });
}

function fromDetail(detail: BackendDetailResponse, baseCase?: RoadCase): RoadCase {
  const primary = detail.primary_defect;
  return mergeCase(baseCase || {}, {
    inspectionId: detail.inspection_id,
    id: toCaseId(detail.inspection_id),
    pipelineStatus: detail.pipeline_status,
    failureReason: detail.failure_reason,
    severity: toSeverity(primary?.severity_level || 'NONE'),
    evidenceUrl: detail.image_url ? `${API_BASE}${detail.image_url}` : placeholderEvidence(detail.road_segment),
    roadSegment: detail.road_segment,
    ward: `${detail.ward_id} / ${detail.zone_id}`,
    wardId: detail.ward_id,
    zoneId: detail.zone_id,
    contractor: detail.contract.contractor_name || 'No contract on file',
    contractorEmail: detail.contract.contractor_email,
    contractId: detail.contract.contract_id,
    dlpStatus: detail.contract.contract_id
      ? detail.contract.is_dlp_active
        ? 'Active'
        : 'Expired'
      : 'None',
    dlpExpiry: detail.contract.dlp_end_date,
    recommendation: detail.recommendation,
    created: detail.created_at,
    status: detail.pipeline_status === 'FAILED' ? 'Escalated' : baseCase?.status || 'Awaiting Review',
    confidence: primary?.confidence || 0,
    coordinates: { lat: detail.lat, lng: detail.lng },
    defectClass: describeDefect(
      detail.total_detections,
      primary?.severity_level || 'NONE',
      detail.pipeline_status,
      primary?.class_name,
    ),
    runId: toRunId(detail.created_at),
    priorFlags: detail.prior_flags,
    totalDetections: detail.total_detections,
    noticeUrl: detail.notice_url,
    isEnforceable: detail.contract.is_enforceable,
    detections: normalizeDetections(detail.detections),
    segmentHistory: normalizeHistory(detail.segment_history),
  });
}

export async function fetchHealth(): Promise<BackendHealth> {
  return apiFetch<BackendHealth>('/health');
}

export async function fetchCases(): Promise<RoadCase[]> {
  const response = await apiFetch<BackendSummaryResponse>('/api/v1/detections?limit=100');
  return response.results.map(fromSummary);
}

export async function fetchCaseDetail(inspectionId: number, baseCase?: RoadCase): Promise<RoadCase> {
  const response = await apiFetch<BackendDetailResponse>(`/api/v1/detections/${inspectionId}`);
  return fromDetail(response, baseCase);
}

export async function uploadInspection(input: { file: File; lat: number; lng: number }): Promise<RoadCase> {
  const formData = new FormData();
  formData.append('file', input.file);
  formData.append('lat', String(input.lat));
  formData.append('lng', String(input.lng));

  const response = await apiFetch<BackendDetectResponse>('/api/v1/detect', {
    method: 'POST',
    body: formData,
  });

  const now = new Date().toISOString();
  const baseCase = mergeCase({}, {
    inspectionId: response.inspection_id,
    id: toCaseId(response.inspection_id),
    pipelineStatus: response.pipeline_status,
    failureReason: null,
    severity: toSeverity(response.primary_defect?.severity_level || 'NONE'),
    evidenceUrl: response.image_url ? `${API_BASE}${response.image_url}` : placeholderEvidence(response.road_segment),
    roadSegment: response.road_segment,
    ward: `${response.ward_id} / ${response.zone_id}`,
    wardId: response.ward_id,
    zoneId: response.zone_id,
    contractor: response.contract.contractor_name || 'No contract on file',
    contractorEmail: response.contract.contractor_email,
    contractId: response.contract.contract_id,
    dlpStatus: response.contract.contract_id
      ? response.contract.is_dlp_active
        ? 'Active'
        : 'Expired'
      : 'None',
    dlpExpiry: response.contract.dlp_end_date,
    recommendation: response.recommendation,
    created: now,
    status: 'Awaiting Review',
    confidence: response.primary_defect?.confidence || 0,
    coordinates: { lat: response.lat, lng: response.lng },
    defectClass: describeDefect(
      response.total_detections,
      response.primary_defect?.severity_level || 'NONE',
      response.pipeline_status,
      response.primary_defect?.class_name,
    ),
    runId: toRunId(now),
    priorFlags: 0,
    totalDetections: response.total_detections,
    noticeUrl: response.notice_url,
    isEnforceable: response.contract.is_enforceable,
    detections: normalizeDetections(response.all_detections),
    segmentHistory: [],
  });

  return fetchCaseDetail(response.inspection_id, baseCase);
}

export async function openNoticePdf(inspectionId: number): Promise<void> {
  const pdfBlob = await fetchBinary(`/api/v1/notices/${inspectionId}`);
  const objectUrl = URL.createObjectURL(pdfBlob);
  const openedWindow = window.open(objectUrl, '_blank', 'noopener,noreferrer');

  if (!openedWindow) {
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = `ARIA_Notice_${inspectionId}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  }

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

export function getApiBase(): string {
  return API_BASE;
}
