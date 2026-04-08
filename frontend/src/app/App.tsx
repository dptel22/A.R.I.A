import { useEffect, useState } from 'react';

import Layout from './Layout';
import CaseDetail from '../features/case-detail/CaseDetail';
import DecisionHistory from '../features/history/DecisionHistory';
import ReviewQueue from '../features/queue/ReviewQueue';
import IngestionRuns from '../features/runs/IngestionRuns';
import { fetchCaseDetail, fetchCases, fetchHealth, uploadInspection } from '../shared/api';
import { AppTab, BackendHealth, RoadCase } from '../shared/types/app';

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('queue');
  const [cases, setCases] = useState<RoadCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [caseDetails, setCaseDetails] = useState<Record<number, RoadCase>>({});
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [loadingCases, setLoadingCases] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadHealth() {
    try {
      setHealth(await fetchHealth());
    } catch {
      setHealth(null);
    }
  }

  async function loadCases() {
    setLoadingCases(true);
    setError(null);
    try {
      const nextCases = await fetchCases();
      setCases(nextCases);
      if (!selectedCaseId && nextCases.length > 0) {
        setSelectedCaseId(nextCases[0].inspectionId);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load inspection queue.');
    } finally {
      setLoadingCases(false);
    }
  }

  async function loadDetail(inspectionId: number) {
    setLoadingDetail(true);
    try {
      const baseCase = cases.find((item) => item.inspectionId === inspectionId);
      const detail = await fetchCaseDetail(inspectionId, baseCase);
      setCaseDetails((current) => ({ ...current, [inspectionId]: detail }));
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Failed to load case detail.');
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    loadHealth();
    loadCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId && activeTab === 'detail' && !caseDetails[selectedCaseId]) {
      loadDetail(selectedCaseId);
    }
  }, [selectedCaseId, activeTab, cases]);

  async function handleSelectCase(inspectionId: number) {
    setSelectedCaseId(inspectionId);
    setActiveTab('detail');
    if (!caseDetails[inspectionId]) {
      await loadDetail(inspectionId);
    }
  }

  async function handleRefresh() {
    await Promise.all([loadHealth(), loadCases()]);
  }

  async function handleUpload(payload: { file: File; lat: number; lng: number }) {
    const uploaded = await uploadInspection(payload);
    setCaseDetails((current) => ({ ...current, [uploaded.inspectionId]: uploaded }));
    await Promise.all([loadHealth(), loadCases()]);
    setSelectedCaseId(uploaded.inspectionId);
    setActiveTab('detail');
  }

  const selectedCase =
    (selectedCaseId ? caseDetails[selectedCaseId] : null) ||
    cases.find((item) => item.inspectionId === selectedCaseId) ||
    null;

  function renderContent() {
    switch (activeTab) {
      case 'queue':
        return (
          <ReviewQueue
            cases={cases}
            loading={loadingCases}
            error={error}
            health={health}
            onSelectCase={handleSelectCase}
            onRefresh={handleRefresh}
            onUpload={handleUpload}
          />
        );
      case 'detail':
        return (
          <CaseDetail
            caseData={selectedCase}
            loading={loadingDetail}
            onBack={() => setActiveTab('queue')}
            onSelectRelatedCase={handleSelectCase}
          />
        );
      case 'history':
        return (
          <DecisionHistory
            cases={cases}
            caseDetails={caseDetails}
            onLoadCaseDetail={loadDetail}
          />
        );
      case 'runs':
        return <IngestionRuns cases={cases} health={health} onRefresh={handleRefresh} />;
      default:
        return (
          <ReviewQueue
            cases={cases}
            loading={loadingCases}
            error={error}
            health={health}
            onSelectCase={handleSelectCase}
            onRefresh={handleRefresh}
            onUpload={handleUpload}
          />
        );
    }
  }

  return (
    <Layout activeTab={activeTab} setActiveTab={setActiveTab} health={health}>
      {renderContent()}
    </Layout>
  );
}
