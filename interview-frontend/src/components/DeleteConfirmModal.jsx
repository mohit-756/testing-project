import React from "react";
import { AlertTriangle, X, Loader2 } from "lucide-react";

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title = "Delete Item",
  message = "Are you sure you want to delete this? This action cannot be undone.",
  itemName,
  confirmText = "Delete",
  loading = false,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl max-w-md w-full mx-4 p-6 animate-fadeIn">
        {/* Close button */}
        <button
          onClick={onClose}
          disabled={loading}
          className="absolute top-4 right-4 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
        >
          <X size={20} />
        </button>

        {/* Icon */}
        <div className="flex justify-center mb-4">
          <div className="bg-red-100 dark:bg-red-900/30 p-4 rounded-full">
            <AlertTriangle size={28} className="text-red-600 dark:text-red-400" />
          </div>
        </div>

        {/* Content */}
        <div className="text-center space-y-3">
          <h3 className="text-xl font-bold text-slate-900 dark:text-white">
            {title}
          </h3>
          <p className="text-slate-600 dark:text-slate-400">
            {message}
          </p>
          {itemName && (
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg px-4 py-2 mt-2">
              <p className="text-sm font-semibold text-slate-900 dark:text-white">
                {itemName}
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 py-3 px-4 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-semibold rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 py-3 px-4 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Deleting...
              </>
            ) : (
              confirmText
            )}
          </button>
        </div>
      </div>
    </div>
  );
}