import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function FullscreenWarning({ onClose }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
      <div className="bg-white p-6 rounded-lg shadow-lg max-w-sm text-center">
        <AlertTriangle className="mx-auto text-yellow-600" size={48} />
        <h2 className="mt-4 text-xl font-semibold">Full‑Screen Required</h2>
        <p className="mt-2 text-gray-600">
          You have exited full‑screen mode. The interview must remain in full‑screen for
          proper proctoring. Please re‑enter full‑screen.
        </p>
        <button
          onClick={onClose}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          OK
        </button>
      </div>
    </div>
  );
}
