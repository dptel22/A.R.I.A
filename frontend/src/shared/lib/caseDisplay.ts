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

export function pipelineBadgeClass(status: PipelineStatus): string {
  if (status === 'FAILED') {
    return 'badge-pipeline-failed';
  }
  if (status === 'NO_DETECTIONS') {
    return 'badge-pipeline-empty';
  }
  return 'badge-pipeline-ok';
}

export function pipelineLabel(status: PipelineStatus): string {
  if (status === 'FAILED') {
    return 'Pipeline Failed';
  }
  if (status === 'NO_DETECTIONS') {
    return 'No Defects';
  }
  return 'Detected';
}

export function severityRank(value: Severity): number {
  switch (value) {
    case 'Critical':
      return 4;
    case 'High':
      return 3;
    case 'Medium':
      return 2;
    case 'Low':
      return 1;
    default:
      return 0;
  }
}
