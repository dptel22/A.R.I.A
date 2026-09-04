import React, { useState } from 'react';
import { LoaderCircle, Upload, X } from 'lucide-react';

interface UploadInspectionModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { file: File; lat: number; lng: number }) => Promise<void>;
}

export default function UploadInspectionModal({
  open,
  onClose,
  onSubmit,
}: UploadInspectionModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError('Select a JPEG or PNG inspection image first.');
      return;
    }

    const latValue = Number(lat);
    const lngValue = Number(lng);
    if (Number.isNaN(latValue) || Number.isNaN(lngValue)) {
      setError('Latitude and longitude must be valid numbers.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ file, lat: latValue, lng: lngValue });
      setFile(null);
      setLat('');
      setLng('');
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Upload failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div className="w-full max-w-xl surface-base p-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 id="upload-modal-title" className="text-lg font-bold text-civic-blue">Run Detection</h2>
            <p className="text-sm text-slate-500 mt-1">
              Upload a geo-tagged inspection image to the live FastAPI detection pipeline.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-2 text-slate-400 hover:text-slate-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-authority-blue rounded-xs"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="upload-file" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
              Inspection Image
            </label>
            <label className="flex items-center justify-center gap-3 border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-sm text-slate-600 cursor-pointer hover:border-civic-blue transition-colors">
              <Upload size={18} className="text-civic-blue" />
              <span>{file ? file.name : 'Choose JPEG or PNG evidence'}</span>
              <input
                id="upload-file"
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="upload-lat" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
                Latitude
              </label>
              <input
                id="upload-lat"
                type="number"
                step="any"
                value={lat}
                onChange={(event) => setLat(event.target.value)}
                placeholder="12.9310"
                className="w-full bg-white border border-stone-200 px-3 py-2 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-civic-blue/20"
              />
            </div>
            <div>
              <label htmlFor="upload-lng" className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
                Longitude
              </label>
              <input
                id="upload-lng"
                type="number"
                step="any"
                value={lng}
                onChange={(event) => setLng(event.target.value)}
                placeholder="77.6450"
                className="w-full bg-white border border-stone-200 px-3 py-2 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-civic-blue/20"
              />
            </div>
          </div>

          <div className="surface-nested p-3 text-xs text-slate-600">
            Use coordinates that fall within a seeded road segment. Example Bengaluru demo points:{' '}
            <button
              type="button"
              onClick={() => { setLat('12.9310'); setLng('77.6450'); }}
              className="mono-text underline underline-offset-2 hover:text-authority-blue focus:outline-none focus-visible:ring-1 focus-visible:ring-authority-blue rounded-xs cursor-pointer"
              title="Click to fill coordinates"
            >
              12.9310, 77.6450
            </button>{' '}
            or{' '}
            <button
              type="button"
              onClick={() => { setLat('13.0600'); setLng('77.5950'); }}
              className="mono-text underline underline-offset-2 hover:text-authority-blue focus:outline-none focus-visible:ring-1 focus-visible:ring-authority-blue rounded-xs cursor-pointer"
              title="Click to fill coordinates"
            >
              13.0600, 77.5950
            </button>.
          </div>

          {error && <div className="text-sm text-red-700 bg-red-50 border border-red-100 px-3 py-2 rounded-sm">{error}</div>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={submitting}>
              {submitting ? <LoaderCircle size={16} className="animate-spin" /> : <Upload size={16} />}
              {submitting ? 'Processing...' : 'Submit to Backend'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
