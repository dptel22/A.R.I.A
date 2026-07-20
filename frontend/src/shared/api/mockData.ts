/**
 * mockData.ts
 *
 * Fully-typed fixture data for Intake clusters and Road Segments.
 * ImageKit URLs are sourced directly from the repo's
 * data/demo/blr_potholes/manifest.jsonl — real, public citizen-submission
 * photos from the warlockdn/blr-potholes-data project, appropriate as
 * fixture data for citizen_submission clusters.
 *
 * This module is imported only by mockClient.ts.
 * Nothing here ships as a public HTTP asset.
 */

import { RoadCase, RoadSegment, SubmissionCluster } from '../types/app';

/* ─────────────────────────────────────────
   Real ImageKit thumbnails from manifest
───────────────────────────────────────── */
const IK = 'https://ik.imagekit.io/blrpotholes';
const THUMB = (id: string) => `${IK}/tr:n-ik_ml_thumbnail/${id}`;
const FULL  = (id: string) => `${IK}/${id}`;

// Identifiers pulled from lines 1-10 of manifest.jsonl
const IMG = {
  a: '1782575163916-x5i6f20km3jpg_dKSm7gmvYx',
  b: '1781662435727-g5sn444re7hjpeg_6GtGcIkFu',
  c: '1781662417360-8vm7fdqey7mjpeg_wHfz08F3L',
  d: '1781262811783-qc30qgpq1jkjpeg_tck0FoGxN',
  e: '1781262811786-62qc4se9z8ejpeg_QTDtj13-M',
  f: '1781262810806-dt5ffrxy4shjpeg_pXDjxXsYd6',
};

/* ─────────────────────────────────────────
   Intake — Submission Clusters
───────────────────────────────────────── */
export const MOCK_CLUSTERS: SubmissionCluster[] = [
  {
    id: 1,
    centerLat: 13.0049,
    centerLng: 77.6200,
    submissionCount: 4,
    firstSubmittedAt: '2026-06-27T10:14:00.000Z',
    lastSubmittedAt:  '2026-06-27T15:46:08.625Z',
    sourceTypes: ['citizen_submission'],
    segmentMatches: [
      { segmentId: 1, segmentName: 'MG Road Stretch A', contractorName: 'Buildwell Infra Ltd', isDlpActive: true },
    ],
    submissions: [
      {
        id: 101, batchId: 10, imageUrl: FULL(IMG.a), lat: 13.0049, lng: 77.6200,
        exifLat: 13.0050, exifLng: 77.6201, exifTimestamp: '2026-06-27T15:45:55.000Z',
        gpsMismatchFlag: false, clusterId: 1, status: 'unreviewed',
        submittedAt: '2026-06-27T15:46:08.625Z', source: 'citizen_submission',
      },
      {
        id: 102, batchId: 10, imageUrl: FULL(IMG.b), lat: 13.0052, lng: 77.6198,
        exifLat: 13.0060, exifLng: 77.6180, exifTimestamp: '2026-06-27T10:14:00.000Z',
        gpsMismatchFlag: true, clusterId: 1, status: 'unreviewed',
        submittedAt: '2026-06-27T10:14:22.000Z', source: 'citizen_submission',
      },
      {
        id: 103, batchId: 10, imageUrl: FULL(IMG.c), lat: 13.0048, lng: 77.6202,
        exifLat: null, exifLng: null, exifTimestamp: null,
        gpsMismatchFlag: false, clusterId: 1, status: 'unreviewed',
        submittedAt: '2026-06-27T13:22:11.000Z', source: 'citizen_submission',
      },
      {
        id: 104, batchId: 11, imageUrl: FULL(IMG.d), lat: 13.0047, lng: 77.6203,
        exifLat: 13.0047, exifLng: 77.6203, exifTimestamp: '2026-06-27T14:10:00.000Z',
        gpsMismatchFlag: false, clusterId: 1, status: 'unreviewed',
        submittedAt: '2026-06-27T14:10:30.000Z', source: 'roadcam_survey',
      },
    ],
  },

  {
    // Ambiguous — two segment bbox overlap
    id: 2,
    centerLat: 12.9154,
    centerLng: 77.6989,
    submissionCount: 2,
    firstSubmittedAt: '2026-06-12T11:13:31.355Z',
    lastSubmittedAt:  '2026-06-12T11:13:52.151Z',
    sourceTypes: ['citizen_submission'],
    segmentMatches: [
      { segmentId: 2, segmentName: 'Hosur Road Zone B', contractorName: 'Metro Build Co.', isDlpActive: true },
      { segmentId: 3, segmentName: 'Hosur Road Zone C', contractorName: 'Metro Build Co.', isDlpActive: false },
    ],
    submissions: [
      {
        id: 201, batchId: 20, imageUrl: FULL(IMG.e), lat: 12.9154, lng: 77.6989,
        exifLat: 12.9155, exifLng: 77.6990, exifTimestamp: '2026-06-12T11:13:30.000Z',
        gpsMismatchFlag: false, clusterId: 2, status: 'unreviewed',
        submittedAt: '2026-06-12T11:13:31.355Z', source: 'citizen_submission',
      },
      {
        id: 202, batchId: 20, imageUrl: FULL(IMG.f), lat: 12.9153, lng: 77.6988,
        exifLat: 12.9200, exifLng: 77.7010, exifTimestamp: '2026-06-12T11:13:50.000Z',
        gpsMismatchFlag: true, clusterId: 2, status: 'unreviewed',
        submittedAt: '2026-06-12T11:13:52.151Z', source: 'citizen_submission',
      },
    ],
  },

  {
    // No segment match
    id: 3,
    centerLat: 12.9148,
    centerLng: 77.7537,
    submissionCount: 1,
    firstSubmittedAt: '2026-06-03T03:34:32.469Z',
    lastSubmittedAt:  '2026-06-03T03:34:32.469Z',
    sourceTypes: ['roadcam_survey'],
    segmentMatches: [],
    submissions: [
      {
        id: 301, batchId: 30, imageUrl: THUMB(IMG.a), lat: 12.9148, lng: 77.7537,
        exifLat: 12.9148, exifLng: 77.7537, exifTimestamp: '2026-06-03T03:34:00.000Z',
        gpsMismatchFlag: false, clusterId: 3, status: 'unreviewed',
        submittedAt: '2026-06-03T03:34:32.469Z', source: 'roadcam_survey',
      },
    ],
  },
];

/* ─────────────────────────────────────────
   Road Segments
───────────────────────────────────────── */
export const MOCK_SEGMENTS: RoadSegment[] = [
  {
    id: 1,
    name: 'MG Road Stretch A',
    wardId: 'W-076',
    zoneId: 'Z-East',
    bbox: { minLat: 12.9750, maxLat: 13.0200, minLng: 77.5900, maxLng: 77.6400 },
    activeContract: {
      id: 201, contractorName: 'Buildwell Infra Ltd',
      contractorEmail: 'b***@buildwell.co.in',
      dlpEndDate: '2027-03-31', isDlpActive: true,
      contractValue: 18500000, createdAt: '2024-04-01T00:00:00.000Z',
    },
    contractHistory: [
      {
        id: 201, contractorName: 'Buildwell Infra Ltd',
        contractorEmail: 'b***@buildwell.co.in',
        dlpEndDate: '2027-03-31', isDlpActive: true,
        contractValue: 18500000, createdAt: '2024-04-01T00:00:00.000Z',
      },
      {
        id: 102, contractorName: 'Civic Roads Pvt Ltd',
        contractorEmail: 'c***@civicroads.in',
        dlpEndDate: '2024-03-31', isDlpActive: false,
        contractValue: 14200000, createdAt: '2022-04-01T00:00:00.000Z',
      },
    ],
    caseCount: 12,
  },
  {
    id: 2,
    name: 'Hosur Road Zone B',
    wardId: 'W-150',
    zoneId: 'Z-South',
    bbox: { minLat: 12.9100, maxLat: 12.9200, minLng: 77.6900, maxLng: 77.7050 },
    activeContract: {
      id: 301, contractorName: 'Metro Build Co.',
      contractorEmail: 'm***@metrobuild.com',
      dlpEndDate: '2026-09-30', isDlpActive: true,
      contractValue: 22000000, createdAt: '2023-10-01T00:00:00.000Z',
    },
    contractHistory: [
      {
        id: 301, contractorName: 'Metro Build Co.',
        contractorEmail: 'm***@metrobuild.com',
        dlpEndDate: '2026-09-30', isDlpActive: true,
        contractValue: 22000000, createdAt: '2023-10-01T00:00:00.000Z',
      },
    ],
    caseCount: 7,
  },
  {
    id: 3,
    name: 'Hosur Road Zone C',
    wardId: 'W-151',
    zoneId: 'Z-South',
    bbox: { minLat: 12.9050, maxLat: 12.9150, minLng: 77.6980, maxLng: 77.7100 },
    activeContract: null,
    contractHistory: [
      {
        id: 205, contractorName: 'Metro Build Co.',
        contractorEmail: 'm***@metrobuild.com',
        dlpEndDate: '2025-06-30', isDlpActive: false,
        contractValue: 9800000, createdAt: '2023-07-01T00:00:00.000Z',
      },
    ],
    caseCount: 3,
  },
  {
    id: 4,
    name: 'Indiranagar 100ft Road',
    wardId: 'W-089',
    zoneId: 'Z-East',
    bbox: { minLat: 12.9700, maxLat: 12.9850, minLng: 77.6380, maxLng: 77.6520 },
    activeContract: {
      id: 410, contractorName: 'Renova Infra Solutions',
      contractorEmail: 'r***@renovainfra.in',
      dlpEndDate: '2025-12-31', isDlpActive: false,
      contractValue: 11000000, createdAt: '2023-01-15T00:00:00.000Z',
    },
    contractHistory: [
      {
        id: 410, contractorName: 'Renova Infra Solutions',
        contractorEmail: 'r***@renovainfra.in',
        dlpEndDate: '2025-12-31', isDlpActive: false,
        contractValue: 11000000, createdAt: '2023-01-15T00:00:00.000Z',
      },
      {
        id: 310, contractorName: 'Buildwell Infra Ltd',
        contractorEmail: 'b***@buildwell.co.in',
        dlpEndDate: '2022-12-31', isDlpActive: false,
        contractValue: 8500000, createdAt: '2021-01-15T00:00:00.000Z',
      },
    ],
    caseCount: 5,
  },
];

/* ─────────────────────────────────────────
   Segment-linked cases stub
   (used by Road Segments detail pane)
───────────────────────────────────────── */
function mockCase(input: {
  inspectionId: number;
  roadSegment: string;
  wardId: string;
  zoneId: string;
  contractor: string;
  contractorEmail?: string;
  contractId?: number | null;
  dlpStatus: RoadCase['dlpStatus'];
  dlpExpiry?: string | null;
  severity: RoadCase['severity'];
  source: RoadCase['source'];
  created: string;
  evidenceUrl: string;
  coordinates: RoadCase['coordinates'];
  defectClass: string;
  confidence: number;
  priorFlags: number;
}): RoadCase {
  const recommendation: RoadCase['recommendation'] =
    input.severity === 'Critical' ? 'Block Payment' :
    input.dlpStatus === 'Active' ? 'Issue Notice' :
    input.severity === 'Low' ? 'No Action' :
    'Escalate Manual Inspection';

  return {
    inspectionId: input.inspectionId,
    id: `ARIA-${String(input.inspectionId).padStart(6, '0')}`,
    pipelineStatus: 'SUCCEEDED',
    failureReason: null,
    severity: input.severity,
    evidenceUrl: input.evidenceUrl,
    roadSegment: input.roadSegment,
    ward: `${input.wardId} / ${input.zoneId}`,
    wardId: input.wardId,
    zoneId: input.zoneId,
    contractor: input.contractor,
    contractorEmail: input.contractorEmail ?? null,
    contractId: input.contractId ?? null,
    dlpStatus: input.dlpStatus,
    dlpExpiry: input.dlpExpiry ?? null,
    recommendation,
    created: input.created,
    status: 'Awaiting Review',
    confidence: input.confidence,
    coordinates: input.coordinates,
    defectClass: input.defectClass,
    runId: `MOCK-RUN-${String(input.inspectionId).padStart(4, '0')}`,
    priorFlags: input.priorFlags,
    totalDetections: 1,
    noticeUrl: null,
    isEnforceable: input.dlpStatus === 'Active',
    detections: [
      {
        className: input.defectClass,
        confidence: input.confidence,
        bboxX: 0.52,
        bboxY: 0.56,
        bboxW: 0.32,
        bboxH: 0.28,
        severityScore: input.severity === 'Critical' ? 0.93 :
          input.severity === 'High' ? 0.78 :
          input.severity === 'Medium' ? 0.52 :
          0.26,
        severityLevel: input.severity,
      },
    ],
    segmentHistory: [],
    source: input.source,
  };
}

export const MOCK_SEGMENT_CASES: Record<number, RoadCase[]> = {
  1: [
    mockCase({
      inspectionId: 42, roadSegment: 'MG Road Stretch A', wardId: 'W-076', zoneId: 'Z-East',
      contractor: 'Buildwell Infra Ltd', contractorEmail: 'b***@buildwell.co.in', contractId: 201,
      dlpStatus: 'Active', dlpExpiry: '2027-03-31', severity: 'Critical',
      created: '2026-06-28T08:10:00.000Z', source: 'citizen_submission',
      evidenceUrl: FULL(IMG.a), coordinates: { lat: 13.0049, lng: 77.6200 },
      defectClass: 'Pothole', confidence: 0.94, priorFlags: 3,
    }),
    mockCase({
      inspectionId: 39, roadSegment: 'MG Road Stretch A', wardId: 'W-076', zoneId: 'Z-East',
      contractor: 'Buildwell Infra Ltd', contractorEmail: 'b***@buildwell.co.in', contractId: 201,
      dlpStatus: 'Active', dlpExpiry: '2027-03-31', severity: 'High',
      created: '2026-06-20T11:05:00.000Z', source: 'roadcam_survey',
      evidenceUrl: FULL(IMG.b), coordinates: { lat: 13.0052, lng: 77.6198 },
      defectClass: 'Alligator cracking', confidence: 0.87, priorFlags: 2,
    }),
    mockCase({
      inspectionId: 31, roadSegment: 'MG Road Stretch A', wardId: 'W-076', zoneId: 'Z-East',
      contractor: 'Buildwell Infra Ltd', contractorEmail: 'b***@buildwell.co.in', contractId: 201,
      dlpStatus: 'Active', dlpExpiry: '2027-03-31', severity: 'Medium',
      created: '2026-06-10T09:00:00.000Z', source: 'manual_upload',
      evidenceUrl: FULL(IMG.c), coordinates: { lat: 13.0048, lng: 77.6202 },
      defectClass: 'Longitudinal crack', confidence: 0.71, priorFlags: 1,
    }),
  ],
  2: [
    mockCase({
      inspectionId: 44, roadSegment: 'Hosur Road Zone B', wardId: 'W-150', zoneId: 'Z-South',
      contractor: 'Metro Build Co.', contractorEmail: 'm***@metrobuild.com', contractId: 301,
      dlpStatus: 'Active', dlpExpiry: '2026-09-30', severity: 'High',
      created: '2026-06-15T07:30:00.000Z', source: 'citizen_submission',
      evidenceUrl: FULL(IMG.d), coordinates: { lat: 12.9154, lng: 77.6989 },
      defectClass: 'Pothole', confidence: 0.84, priorFlags: 1,
    }),
  ],
  3: [
    mockCase({
      inspectionId: 35, roadSegment: 'Hosur Road Zone C', wardId: 'W-151', zoneId: 'Z-South',
      contractor: 'Metro Build Co.', contractorEmail: 'm***@metrobuild.com', contractId: 205,
      dlpStatus: 'Expired', dlpExpiry: '2025-06-30', severity: 'Low',
      created: '2026-06-05T16:20:00.000Z', source: 'manual_upload',
      evidenceUrl: FULL(IMG.e), coordinates: { lat: 12.9153, lng: 77.6988 },
      defectClass: 'Transverse crack', confidence: 0.66, priorFlags: 0,
    }),
  ],
  4: [
    mockCase({
      inspectionId: 40, roadSegment: 'Indiranagar 100ft Road', wardId: 'W-089', zoneId: 'Z-East',
      contractor: 'Renova Infra Solutions', contractorEmail: 'r***@renovainfra.in', contractId: 410,
      dlpStatus: 'Expired', dlpExpiry: '2025-12-31', severity: 'Medium',
      created: '2026-06-22T14:50:00.000Z', source: 'roadcam_survey',
      evidenceUrl: FULL(IMG.f), coordinates: { lat: 12.9801, lng: 77.6442 },
      defectClass: 'Alligator cracking', confidence: 0.73, priorFlags: 1,
    }),
    mockCase({
      inspectionId: 33, roadSegment: 'Indiranagar 100ft Road', wardId: 'W-089', zoneId: 'Z-East',
      contractor: 'Renova Infra Solutions', contractorEmail: 'r***@renovainfra.in', contractId: 410,
      dlpStatus: 'Expired', dlpExpiry: '2025-12-31', severity: 'High',
      created: '2026-06-08T10:10:00.000Z', source: 'manual_upload',
      evidenceUrl: THUMB(IMG.a), coordinates: { lat: 12.9784, lng: 77.6419 },
      defectClass: 'Pothole', confidence: 0.81, priorFlags: 2,
    }),
  ],
};
