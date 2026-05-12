import React, { useState } from "react";
import { Link } from "react-router-dom";
import StatusBadge from "./StatusBadge";
import DeleteConfirmModal from "./DeleteConfirmModal";
import { Calendar, Eye, Trash2 } from "lucide-react";

export default function CandidateTable({ candidates, onDeleteCandidate, onScheduleCandidate }) {
  const [deleteModal, setDeleteModal] = useState({ open: false, candidate: null });

  const handleDeleteClick = (candidate) => {
    setDeleteModal({ open: true, candidate });
  };

  const handleConfirmDelete = async () => {
    if (deleteModal.candidate && onDeleteCandidate) {
      await onDeleteCandidate(deleteModal.candidate);
      setDeleteModal({ open: false, candidate: null });
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Candidate</th>
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Role/Domain</th>
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Resume Score</th>
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Decision</th>
            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {!candidates.length ? (
            <tr>
              <td colSpan={6} className="px-6 py-12 text-center text-sm text-slate-500 dark:text-slate-400">
                No candidates found.
              </td>
            </tr>
          ) : candidates.map((candidate) => (
            <tr key={candidate.uid || candidate.candidate_uid || candidate.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
              <td className="px-6 py-4">
                <div className="flex items-center">
                  <img src={candidate.avatar} alt="" className="w-9 h-9 rounded-full bg-slate-100 mr-3" />
                  <div>
                    <div className="font-medium text-slate-900 dark:text-white">{candidate.name}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">{candidate.email}</div>
                  </div>
                </div>
              </td>
              <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-300">{candidate.role}</td>
              <td className="px-6 py-4">
                <div className="flex items-center">
                  <div className="w-12 bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full mr-2">
                    <div 
                      className={`h-full rounded-full ${candidate.resumeScore > 80 ? "bg-emerald-500" : candidate.resumeScore > 60 ? "bg-blue-500" : "bg-yellow-500"}`} 
                      style={{ width: `${candidate.resumeScore || 0}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold">{candidate.resumeScore || 0}%</span>
                </div>
              </td>
              <td className="px-6 py-4">
                <StatusBadge status={candidate.status} />
              </td>
              <td className="px-6 py-4">
                <StatusBadge status={candidate.finalDecision || candidate.status} />
              </td>
              <td className="px-6 py-4">
                <div className="flex items-center space-x-2">
                  <Link
                    to={`/hr/candidates/${candidate.uid || candidate.candidate_uid}`}
                    aria-label={`Open ${candidate.name || "candidate"} profile`}
                    className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition-all"
                  >
                    <Eye size={18} />
                  </Link>
                  <button
                    type="button"
                    onClick={() => onScheduleCandidate?.(candidate)}
                    aria-label={`Schedule interview for ${candidate.name || "candidate"}`}
                    className="p-1.5 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 rounded-md transition-all"
                  >
                    <Calendar size={18} />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(candidate)}
                    aria-label={`Delete ${candidate.name || "candidate"}`}
                    className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-all"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={deleteModal.open}
        onClose={() => setDeleteModal({ open: false, candidate: null })}
        onConfirm={handleConfirmDelete}
        title="Delete Candidate"
        message="Are you sure you want to delete this candidate? All their data and interview sessions will be permanently removed."
        itemName={deleteModal.candidate?.name}
        confirmText="Delete Candidate"
      />
    </div>
  );
}