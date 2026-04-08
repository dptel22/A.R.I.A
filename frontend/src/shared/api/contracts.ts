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
