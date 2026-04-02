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
export type AppTab = 'queue' | 'detail' | 'history' | 'runs' | 'repair';

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
}

export interface DerivedRun {
  id: string;
  name: string;
  timestamp: string;
  status: 'Successful' | 'Processing';
  inspections: number;
  detections: number;
  dlpActiveCases: number;
  duration: string;
  region: string;
  load: number;
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
