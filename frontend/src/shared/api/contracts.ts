import { Decision, PipelineStatus } from '../types/app';

export type BackendSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';

export interface BackendHealth {
  status: string;
  model_loaded: boolean;
  version: string;
}

export interface BackendContract {
  contract_id: number | null;
  contractor_name: string | null;
  contractor_email: string | null;
  dlp_end_date: string | null;
  is_dlp_active: boolean;
  is_enforceable: boolean;
}

export interface BackendSummaryRow {
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
  notice_url: string | null;
}

export interface BackendSummaryResponse {
  total_matching: number;
  returned_count: number;
  limit: number;
  offset: number;
  results: BackendSummaryRow[];
}

export interface BackendDetection {
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

export interface BackendSegmentHistoryItem {
  inspection_id: number;
  created_at: string;
  pipeline_status: PipelineStatus;
  highest_severity: BackendSeverity;
  total_detections: number;
  recommendation: Decision;
  notice_url: string | null;
}

export interface BackendDetailResponse {
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

export interface BackendDetectResponse {
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

export interface BackendRawSubmission {
  id: number;
  batch_id: number;
  image_url: string;
  lat: number;
  lng: number;
  exif_lat: number | null;
  exif_lng: number | null;
  exif_timestamp: string | null;
  gps_mismatch_flag: boolean;
  cluster_id: number | null;
  status: 'unreviewed' | 'promoted' | 'dismissed';
  submitted_at: string;
  source: 'citizen_submission' | 'roadcam_survey' | 'manual_upload';
}

export interface BackendSegmentMatch {
  segment_id: number;
  segment_name: string;
  contract_id: number | null;
  contractor_name: string;
  contractor_email: string | null;
  dlp_end_date: string | null;
  is_dlp_active: boolean;
}

export interface BackendSubmissionCluster {
  id: number;
  center_lat: number;
  center_lng: number;
  submission_count: number;
  first_submitted_at: string;
  last_submitted_at: string;
  source_types: ('citizen_submission' | 'roadcam_survey' | 'manual_upload')[];
  submissions: BackendRawSubmission[];
  segment_matches: BackendSegmentMatch[];
}

export interface BackendDismissedCluster {
  cluster: BackendSubmissionCluster;
  reason: 'spam' | 'duplicate' | 'not_a_road_defect' | 'other';
  dismissed_at: string;
}

export interface BackendContractSummary {
  id: number;
  contractor_name: string;
  contractor_email: string;
  dlp_end_date: string | null;
  is_dlp_active: boolean;
  contract_value?: number | null;
  created_at: string;
}

export interface BackendRoadSegment {
  id: number;
  name: string;
  ward_id: string;
  zone_id: string;
  bbox: { min_lat: number; max_lat: number; min_lng: number; max_lng: number };
  active_contract: BackendContractSummary | null;
  contract_history: BackendContractSummary[];
  case_count: number;
}

export interface BackendSegmentCase {
  id: string;
  inspection_id: number;
  road_segment: string;
  severity: BackendSeverity;
  status: 'Awaiting Review' | 'Approved' | 'Escalated' | 'Dismissed';
  created: string;
  recommendation: Decision;
  image_url: string | null;
}

export interface BackendSegmentDetailResponse {
  segment: BackendRoadSegment;
  cases: BackendSegmentCase[];
}
