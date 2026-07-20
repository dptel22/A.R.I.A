/**
 * mockClient.ts
 *
 * In-memory handlers for the new Intake and Road Segments endpoints.
 * Imported only by api/index.ts behind the USE_MOCKS flag.
 * Simulates network delay to surface loading states properly.
 */

import { MOCK_CLUSTERS, MOCK_SEGMENT_CASES, MOCK_SEGMENTS } from './mockData';
import { RoadCase, RoadSegment, SubmissionCluster } from '../types/app';

/** Simulated network delay (ms) */
const MOCK_DELAY = 280;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY));
}

/* ─────────────────────────────────────────
   In-memory mutable state
───────────────────────────────────────── */
let clusters: SubmissionCluster[] = MOCK_CLUSTERS.map((c) => ({ ...c }));

export type DismissReason = 'spam' | 'duplicate' | 'not_a_road_defect' | 'other';

interface DismissedCluster {
  cluster: SubmissionCluster;
  reason: DismissReason;
  dismissedAt: string;
}

let dismissed: DismissedCluster[] = [];

/* ─────────────────────────────────────────
   Cluster handlers
───────────────────────────────────────── */
export function mockFetchClusters(): Promise<SubmissionCluster[]> {
  return delay(clusters.filter((c) =>
    c.submissions.some((s) => s.status === 'unreviewed'),
  ));
}

export function mockFetchClusterDetail(id: number): Promise<SubmissionCluster> {
  const cluster = clusters.find((c) => c.id === id);
  if (!cluster) {
    return Promise.reject(new Error(`Cluster ${id} not found.`));
  }
  return delay(cluster);
}

export function mockPromoteCluster(
  id: number,
  segmentId: number,
): Promise<void> {
  clusters = clusters.map((c) => {
    if (c.id !== id) return c;
    return {
      ...c,
      submissions: c.submissions.map((s) =>
        s.status === 'unreviewed' ? { ...s, status: 'promoted' as const } : s,
      ),
    };
  });
  console.info(`[mock] Cluster ${id} promoted to segment ${segmentId}`);
  return delay(undefined);
}

export function mockDismissCluster(
  id: number,
  reason: DismissReason,
): Promise<void> {
  const cluster = clusters.find((c) => c.id === id);
  if (cluster) {
    dismissed = [...dismissed, { cluster, reason, dismissedAt: new Date().toISOString() }];
    clusters = clusters.map((c) => {
      if (c.id !== id) return c;
      return {
        ...c,
        submissions: c.submissions.map((s) =>
          s.status === 'unreviewed' ? { ...s, status: 'dismissed' as const } : s,
        ),
      };
    });
  }
  console.info(`[mock] Cluster ${id} dismissed (reason: ${reason})`);
  return delay(undefined);
}

export function mockGetDismissed(): DismissedCluster[] {
  return dismissed;
}

/* ─────────────────────────────────────────
   Segment handlers
───────────────────────────────────────── */
export function mockFetchSegments(): Promise<RoadSegment[]> {
  return delay(MOCK_SEGMENTS);
}

export function mockFetchSegmentDetail(
  id: number,
): Promise<{ segment: RoadSegment; cases: Partial<RoadCase>[] }> {
  const segment = MOCK_SEGMENTS.find((s) => s.id === id);
  if (!segment) {
    return Promise.reject(new Error(`Segment ${id} not found.`));
  }
  return delay({ segment, cases: MOCK_SEGMENT_CASES[id] ?? [] });
}
