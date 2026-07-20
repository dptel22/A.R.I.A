import { PipelineStatus, Severity } from '../types/app';

export function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Returns the CSS class for the pipeline-status dot+label wrapper. */
export function pipelineStatusClass(status: PipelineStatus): string {
  if (status === 'FAILED') return 'pipeline-status pipeline-failed';
  if (status === 'NO_DETECTIONS') return 'pipeline-status pipeline-empty';
  return 'pipeline-status pipeline-ok';
}

/** Human-readable label for a pipeline status. */
export function pipelineLabel(status: PipelineStatus): string {
  if (status === 'FAILED') return 'Pipeline Failed';
  if (status === 'NO_DETECTIONS') return 'No Defects';
  return 'Detected';
}

/** @deprecated Use pipelineStatusClass instead — badge pills have been replaced. */
export function pipelineBadgeClass(status: PipelineStatus): string {
  return pipelineStatusClass(status);
}

export function severityRank(value: Severity): number {
  switch (value) {
    case 'Critical': return 4;
    case 'High':     return 3;
    case 'Medium':   return 2;
    case 'Low':      return 1;
    default:         return 0;
  }
}

/** Human-readable label for a submission source. */
export function sourceLabel(source: string): string {
  switch (source) {
    case 'citizen_submission': return 'Citizen';
    case 'roadcam_survey':     return 'RoadCam';
    case 'manual_upload':      return 'Manual';
    default:                   return source;
  }
}
