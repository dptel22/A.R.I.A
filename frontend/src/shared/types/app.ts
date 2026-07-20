import { LucideIcon } from 'lucide-react';

export type Severity = 'Critical' | 'High' | 'Medium' | 'Low' | 'None';
export type DLPStatus = 'Active' | 'Expired' | 'None';
export type ReviewStatus = 'Awaiting Review' | 'Approved' | 'Escalated' | 'Dismissed';
export type PipelineStatus = 'SUCCEEDED' | 'NO_DETECTIONS' | 'FAILED';
export type Decision =
  | 'No Action'
  | 'Issue Notice'
  | 'Block Payment'
  | 'Escalate Manual Inspection';

export type SubmissionSource = 'citizen_submission' | 'roadcam_survey' | 'manual_upload';

export type AppTab = 'queue' | 'detail' | 'history' | 'runs' | 'intake' | 'segments';

export interface DetectionBox {
  id?: number;
  className: string;
  confidence: number;
  bboxX: number;
  bboxY: number;
  bboxW: number;
  bboxH: number;
  severityScore: number;
  severityLevel: Severity;
}

export interface SegmentHistoryItem {
  inspectionId: number;
  created: string;
  pipelineStatus: PipelineStatus;
  severity: Severity;
  totalDetections: number;
  recommendation: Decision;
  noticeUrl?: string | null;
}

export interface RoadCase {
  inspectionId: number;
  id: string;
  pipelineStatus: PipelineStatus;
  failureReason?: string | null;
  severity: Severity;
  evidenceUrl: string;
  roadSegment: string;
  ward: string;
  wardId: string;
  zoneId: string;
  contractor: string;
  contractorEmail?: string | null;
  contractId?: number | null;
  dlpStatus: DLPStatus;
  dlpExpiry?: string | null;
  recommendation: Decision;
  created: string;
  status: ReviewStatus;
  confidence: number;
  coordinates: { lat: number; lng: number };
  defectClass: string;
  runId: string;
  priorFlags: number;
  notes?: string;
  totalDetections: number;
  noticeUrl?: string | null;
  isEnforceable: boolean;
  detections: DetectionBox[];
  segmentHistory: SegmentHistoryItem[];
  /** Defaults to 'manual_upload' for all pre-existing cases. */
  source: SubmissionSource;
}

export interface BackendHealth {
  status: string;
  model_loaded: boolean;
  version: string;
}

export interface NavItem {
  label: string;
  icon: LucideIcon;
  id: AppTab;
  disabled?: boolean;
}

/* ─────────────────────────────────────────
   Intake — new types
───────────────────────────────────────── */

export interface RawSubmission {
  id: number;
  batchId: number;
  imageUrl: string;
  lat: number;
  lng: number;
  exifLat?: number | null;
  exifLng?: number | null;
  exifTimestamp?: string | null;
  gpsMismatchFlag: boolean;
  clusterId: number | null;
  status: 'unreviewed' | 'promoted' | 'dismissed';
  submittedAt: string;
  source: SubmissionSource;
}

export interface SegmentMatch {
  segmentId: number;
  segmentName: string;
  contractorName: string;
  isDlpActive: boolean;
}

export interface SubmissionCluster {
  id: number;
  centerLat: number;
  centerLng: number;
  submissionCount: number;
  firstSubmittedAt: string;
  lastSubmittedAt: string;
  sourceTypes: SubmissionSource[];
  submissions: RawSubmission[];
  /** 0 = no match, 1 = clean, >1 = ambiguous bbox overlap */
  segmentMatches: SegmentMatch[];
}

/* ─────────────────────────────────────────
   Road Segments — new types
───────────────────────────────────────── */

export interface ContractSummary {
  id: number;
  contractorName: string;
  contractorEmail: string; // pre-masked by backend, e.g. "c***@domain.com"
  dlpEndDate: string | null;
  isDlpActive: boolean;
  contractValue?: number | null;
  createdAt: string;
}

export interface RoadSegment {
  id: number;
  name: string;
  wardId: string;
  zoneId: string;
  bbox: { minLat: number; maxLat: number; minLng: number; maxLng: number };
  activeContract: ContractSummary | null;
  contractHistory: ContractSummary[];
  caseCount: number;
}
