import {
  BackendDetailResponse,
  BackendDetection,
  BackendDismissedCluster,
  BackendRawSubmission,
  BackendRoadSegment,
  BackendSegmentCase,
  BackendSegmentDetailResponse,
  BackendSegmentHistoryItem,
  BackendSegmentMatch,
  BackendSeverity,
  BackendSubmissionCluster,
  BackendSummaryRow,
  BackendContractSummary,
} from './contracts';
import {
  ContractSummary, DLPStatus, DetectionBox, RawSubmission, RoadCase, RoadSegment,
  SegmentHistoryItem, SegmentMatch, Severity, SubmissionCluster, SubmissionSource,
} from '../types/app';
import { getApiBase } from './client';

export function toSeverity(level: BackendSeverity): Severity {
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

export function toDlpStatus(value: 'ACTIVE' | 'EXPIRED' | 'NONE'): DLPStatus {
  if (value === 'ACTIVE') {
    return 'Active';
  }
  if (value === 'EXPIRED') {
    return 'Expired';
  }
  return 'None';
}

export function toCaseId(inspectionId: number): string {
  return `ARIA-${inspectionId.toString().padStart(6, '0')}`;
}

export function toRunId(timestamp: string): string {
  return `RUN-${timestamp.slice(0, 10)}`;
}

export function placeholderEvidence(label: string): string {
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

export function normalizeDetections(detections: BackendDetection[]): DetectionBox[] {
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

export function normalizeHistory(items: BackendSegmentHistoryItem[]): SegmentHistoryItem[] {
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

export function describeDefect(
  totalDetections: number,
  severity: BackendSeverity,
  pipelineStatus: RoadCase['pipelineStatus'],
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

export function mergeCase(base: Partial<RoadCase>, detail: Partial<RoadCase>): RoadCase {
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
    source: (detail.source ?? base.source ?? 'manual_upload') as SubmissionSource,
  };
}

export function fromSummary(row: BackendSummaryRow): RoadCase {
  return mergeCase({}, {
    inspectionId: row.inspection_id,
    id: toCaseId(row.inspection_id),
    pipelineStatus: row.pipeline_status,
    failureReason: row.failure_reason,
    severity: toSeverity(row.highest_severity),
    evidenceUrl: row.image_url ? `${getApiBase()}${row.image_url}` : placeholderEvidence(row.road_name),
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
    noticeUrl: row.notice_url,
    isEnforceable: row.is_dlp_active,
    detections: [],
    segmentHistory: [],
  });
}

export function fromDetail(detail: BackendDetailResponse, baseCase?: RoadCase): RoadCase {
  const primary = detail.primary_defect;
  return mergeCase(baseCase || {}, {
    inspectionId: detail.inspection_id,
    id: toCaseId(detail.inspection_id),
    pipelineStatus: detail.pipeline_status,
    failureReason: detail.failure_reason,
    severity: toSeverity(primary?.severity_level || 'NONE'),
    evidenceUrl: detail.image_url ? `${getApiBase()}${detail.image_url}` : placeholderEvidence(detail.road_segment),
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

export function fromRawSubmissionResponse(row: BackendRawSubmission): RawSubmission {
  return {
    id: row.id,
    batchId: row.batch_id,
    imageUrl: row.image_url.startsWith('/uploads/') ? `${getApiBase()}${row.image_url}` : row.image_url,
    lat: row.lat,
    lng: row.lng,
    exifLat: row.exif_lat,
    exifLng: row.exif_lng,
    exifTimestamp: row.exif_timestamp,
    gpsMismatchFlag: row.gps_mismatch_flag,
    clusterId: row.cluster_id,
    status: row.status,
    submittedAt: row.submitted_at,
    source: row.source as SubmissionSource,
  };
}

export function fromSegmentMatchResponse(row: BackendSegmentMatch): SegmentMatch {
  return {
    segmentId: row.segment_id,
    segmentName: row.segment_name,
    contractorName: row.contractor_name,
    isDlpActive: row.is_dlp_active,
  };
}

export function fromClusterResponse(row: BackendSubmissionCluster): SubmissionCluster {
  return {
    id: row.id,
    centerLat: row.center_lat,
    centerLng: row.center_lng,
    submissionCount: row.submission_count,
    firstSubmittedAt: row.first_submitted_at,
    lastSubmittedAt: row.last_submitted_at,
    sourceTypes: row.source_types as SubmissionSource[],
    submissions: row.submissions.map(fromRawSubmissionResponse),
    segmentMatches: row.segment_matches.map(fromSegmentMatchResponse),
  };
}

export function fromDismissedClusterResponse(row: BackendDismissedCluster) {
  return {
    cluster: fromClusterResponse(row.cluster),
    reason: row.reason,
    dismissedAt: row.dismissed_at,
  };
}

export function fromContractSummaryResponse(row: BackendContractSummary): ContractSummary {
  return {
    id: row.id,
    contractorName: row.contractor_name,
    contractorEmail: row.contractor_email,
    dlpEndDate: row.dlp_end_date,
    isDlpActive: row.is_dlp_active,
    contractValue: row.contract_value,
    createdAt: row.created_at,
  };
}

export function fromSegmentResponse(row: BackendRoadSegment): RoadSegment {
  return {
    id: row.id,
    name: row.name,
    wardId: row.ward_id,
    zoneId: row.zone_id,
    bbox: {
      minLat: row.bbox.min_lat,
      maxLat: row.bbox.max_lat,
      minLng: row.bbox.min_lng,
      maxLng: row.bbox.max_lng,
    },
    activeContract: row.active_contract ? fromContractSummaryResponse(row.active_contract) : null,
    contractHistory: row.contract_history.map(fromContractSummaryResponse),
    caseCount: row.case_count,
  };
}

function fromSegmentCaseResponse(row: BackendSegmentCase): RoadCase {
  return mergeCase({}, {
    inspectionId: row.inspection_id,
    id: row.id,
    severity: toSeverity(row.severity),
    evidenceUrl: row.image_url ? `${getApiBase()}${row.image_url}` : placeholderEvidence(row.road_segment),
    roadSegment: row.road_segment,
    recommendation: row.recommendation,
    created: row.created,
    status: row.status,
    defectClass: describeDefect(row.severity === 'NONE' ? 0 : 1, row.severity, 'SUCCEEDED', null),
    source: 'manual_upload',
  });
}

export function fromSegmentDetailResponse(row: BackendSegmentDetailResponse): { segment: RoadSegment; cases: RoadCase[] } {
  return {
    segment: fromSegmentResponse(row.segment),
    cases: row.cases.map(fromSegmentCaseResponse),
  };
}
