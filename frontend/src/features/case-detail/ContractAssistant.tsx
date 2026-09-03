import React, { useState } from 'react';
import {
  BookOpenCheck,
  FileText,
  LoaderCircle,
  Send,
  ShieldQuestion,
  Upload,
} from 'lucide-react';
import {
  askContractQuestion,
  fetchContractDocuments,
  uploadContractDocument,
} from '../../shared/api';
import { BackendAskResponse, BackendContractDocument } from '../../shared/api/contracts';

interface ContractAssistantProps {
  inspectionId: number;
  contractId: number | null;
}

/**
 * Grounded contract Q&A for a single inspection. Advisory only — answers cite
 * the contract document applicable at inspection time and never influence
 * enforcement decisions or notices.
 */
export default function ContractAssistant({ inspectionId, contractId }: ContractAssistantProps) {
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<BackendAskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<BackendContractDocument[] | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleAsk() {
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setError(null);
    try {
      setAnswer(await askContractQuestion(inspectionId, trimmed));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to query contract.');
    } finally {
      setAsking(false);
    }
  }

  async function loadDocuments() {
    if (contractId == null || documents) return;
    try {
      setDocuments(await fetchContractDocuments(contractId));
    } catch {
      setDocuments([]);
    }
  }

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || contractId == null) return;
    setUploading(true);
    setError(null);
    try {
      await uploadContractDocument(contractId, file);
      setDocuments(await fetchContractDocuments(contractId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Document upload failed.');
    } finally {
      setUploading(false);
    }
  }

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <BookOpenCheck size={13} style={{ color: 'var(--color-authority-blue)' }} />
        <h3 className="text-[9px] font-bold uppercase tracking-widest text-ink-soft">
          Contract Assistant
        </h3>
      </div>
      <div className="surface-nested p-4 rounded-sm">
        <p className="text-[9px] text-ink-soft italic mb-3">
          Answers are grounded in the contract document applicable at inspection time, with
          page/clause citations. Advisory only — enforcement decisions remain deterministic.
        </p>

        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder={
              contractId == null
                ? 'No contract on file for this inspection'
                : 'e.g. What is the repair deadline under the DLP clause?'
            }
            disabled={contractId == null || asking}
            className="flex-1 border border-hairline rounded-sm px-3 py-2 text-xs bg-white focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={handleAsk}
            disabled={contractId == null || asking || !question.trim()}
            className="btn-primary px-3 py-2 rounded-sm flex items-center gap-2 text-[9px] uppercase tracking-wider disabled:opacity-50"
          >
            {asking ? <LoaderCircle size={11} className="animate-spin" /> : <Send size={11} />}
            Ask
          </button>
        </div>

        {error && (
          <div className="mt-3 text-[9px] p-2 bg-red-50 border border-red-100 rounded-sm" style={{ color: 'var(--color-signal-red)' }}>
            {error}
          </div>
        )}

        {asking && (
          <div className="mt-3 flex items-center gap-2 text-[9px] text-ink-soft">
            <LoaderCircle size={11} className="animate-spin" />
            Retrieving evidence from the applicable contract…
          </div>
        )}

        {answer && !asking && (
          <div className="mt-3 border-t border-hairline pt-3">
            {answer.supported ? (
              <div className="text-xs text-ink leading-5">{answer.answer}</div>
            ) : (
              <div className="flex items-start gap-2 text-xs">
                <ShieldQuestion size={14} className="shrink-0 text-hazard-amber" />
                <div>
                  <div className="text-ink-soft italic">{answer.answer}</div>
                  <div className="text-[9px] text-ink-soft mt-1 font-bold uppercase tracking-wider">
                    Insufficient evidence in the applicable contract
                  </div>
                </div>
              </div>
            )}

            {answer.sources.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {answer.sources.map((source) => (
                  <div key={source.chunk_id} className="bg-white border border-hairline rounded-sm p-2">
                    <div className="flex flex-wrap gap-1.5 mb-1">
                      <span className="badge badge-none">p.{source.page}</span>
                      {source.clause && <span className="badge badge-none">Clause {source.clause}</span>}
                      {source.section && <span className="badge badge-none">{source.section}</span>}
                      <span className="text-[8px] text-ink-soft mono-text ml-auto">v{answer.document.version}</span>
                    </div>
                    <div className="text-[9px] text-ink-soft italic">"{source.quote}"</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Document management */}
        <div className="mt-4 border-t border-hairline pt-3">
          <div className="flex items-center justify-between">
            <button
              onClick={loadDocuments}
              className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-ink-soft hover:underline"
            >
              <FileText size={11} />
              {documents ? 'Contract documents' : 'View contract documents'}
            </button>
            {contractId != null && (
              <label
                className={`flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider cursor-pointer hover:underline ${
                  uploading ? 'opacity-50 pointer-events-none' : ''
                }`}
                style={{ color: 'var(--color-authority-blue)' }}
              >
                {uploading ? <LoaderCircle size={11} className="animate-spin" /> : <Upload size={11} />}
                {uploading ? 'Processing…' : 'Upload PDF'}
                <input type="file" accept="application/pdf" className="hidden" onChange={handleUpload} />
              </label>
            )}
          </div>

          {documents && (
            <div className="mt-2 space-y-1">
              {documents.length === 0 ? (
                <div className="text-[9px] text-ink-soft italic">
                  No documents uploaded for this contract yet. Upload the contract PDF to enable grounded answers.
                </div>
              ) : (
                documents.map((doc) => (
                  <div key={doc.document_id} className="flex items-center justify-between text-[9px] bg-white border border-hairline rounded-sm px-2 py-1.5">
                    <span className="mono-text truncate">{doc.file_name} (v{doc.version})</span>
                    <span
                      className={
                        doc.status === 'READY' ? 'badge badge-dlp' : doc.status === 'FAILED' ? 'badge badge-critical' : 'badge badge-none'
                      }
                    >
                      {doc.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
