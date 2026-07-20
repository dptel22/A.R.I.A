import { BackendDetectResponse, BackendDetailResponse, BackendHealth, BackendSummaryResponse } from './contracts';
import { apiFetch, fetchBinary, getApiBase } from './client';
import {
  describeDefect, fromDetail, fromSummary, mergeCase,
  normalizeDetections, placeholderEvidence, toCaseId, toRunId, toSeverity,
} from './mappers';
import { RoadCase, RoadSegment, SubmissionCluster } from '../types/app';
import {
  DismissReason,
  mockDismissCluster,
  mockFetchCaseDetail,
  mockFetchClusterDetail,
  mockFetchClusters,
  mockFetchSegmentDetail,
  mockFetchSegments,
  mockGetDismissed,
  mockPromoteCluster,
} from './mockClient';

/**
 * Toggle to swap new Intake + Segments endpoints between mock and real backend.
 * Set to false once the backend implements the section 5 endpoints.
 */
const USE_MOCKS = true;

/* ─────────────────────────────────────────
   Existing production endpoints (unchanged)
───────────────────────────────────────── */
export async function fetchHealth(): Promise<BackendHealth> {
  return apiFetch<BackendHealth>('/health');
}

export async function fetchCases(): Promise<RoadCase[]> {
  const response = await apiFetch<BackendSummaryResponse>('/api/v1/detections?limit=100');
  return response.results.map((row) => ({ ...fromSummary(row), source: 'manual_upload' as const }));
}

export async function fetchCaseDetail(inspectionId: number, baseCase?: RoadCase): Promise<RoadCase> {
  const response = await apiFetch<BackendDetailResponse>(`/api/v1/detections/${inspectionId}`);
  return { ...fromDetail(response, baseCase), source: baseCase?.source ?? 'manual_upload' };
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
    evidenceUrl: response.image_url ? `${getApiBase()}${response.image_url}` : placeholderEvidence(response.road_segment),
    roadSegment: response.road_segment,
    ward: `${response.ward_id} / ${response.zone_id}`,
    wardId: response.ward_id,
    zoneId: response.zone_id,
    contractor: response.contract.contractor_name || 'No contract on file',
    contractorEmail: response.contract.contractor_email,
    contractId: response.contract.contract_id,
    dlpStatus: response.contract.contract_id
      ? response.contract.is_dlp_active ? 'Active' : 'Expired'
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
    source: 'manual_upload',
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

/* ─────────────────────────────────────────
   New endpoints — gated behind USE_MOCKS
───────────────────────────────────────── */
export async function fetchClusters(): Promise<SubmissionCluster[]> {
  if (USE_MOCKS) return mockFetchClusters();
  return apiFetch<SubmissionCluster[]>('/intake/clusters');
}

export async function fetchClusterDetail(id: number): Promise<SubmissionCluster> {
  if (USE_MOCKS) return mockFetchClusterDetail(id);
  return apiFetch<SubmissionCluster>(`/intake/clusters/${id}`);
}

export async function promoteCluster(id: number, segmentId: number): Promise<void> {
  if (USE_MOCKS) return mockPromoteCluster(id, segmentId);
  return apiFetch<void>(`/intake/clusters/${id}/promote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segmentId }),
  });
}

export async function dismissCluster(id: number, reason: DismissReason): Promise<void> {
  if (USE_MOCKS) return mockDismissCluster(id, reason);
  return apiFetch<void>(`/intake/clusters/${id}/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

export { mockGetDismissed };

export async function fetchMockCaseDetail(inspectionId: number): Promise<RoadCase> {
  return mockFetchCaseDetail(inspectionId);
}

export async function fetchSegments(): Promise<RoadSegment[]> {
  if (USE_MOCKS) return mockFetchSegments();
  return apiFetch<RoadSegment[]>('/segments');
}

export async function fetchSegmentDetail(
  id: number,
): Promise<{ segment: RoadSegment; cases: RoadCase[] }> {
  if (USE_MOCKS) return mockFetchSegmentDetail(id);
  return apiFetch<{ segment: RoadSegment; cases: RoadCase[] }>(`/segments/${id}`);
}

export { getApiBase } from './client';
