import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MetricCard from "../components/MetricCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { hrApi } from "../services/api";
import { formatPercent } from "../utils/formatters";
import "./CandidateComparisonPage.css";

function parseIds(searchParams) {
  const raw = searchParams.get("ids") || "";
  return raw
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isInteger(value) && value > 0)
    .slice(0, 3);
}

function summaryText(summary) {
  if (!summary) return "No interview data yet.";
  return (summary?.strengths_summary || []).join(" ") || summary?.hiring_recommendation || "No interview data yet.";
}

export default function CandidateComparisonPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [allCandidates, setAllCandidates] = useState([]);
  const [selectedResultIds, setSelectedResultIds] = useState([]);
  const [compareData, setCompareData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [compareLoading, setCompareLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setSelectedResultIds(parseIds(searchParams));
  }, [searchParams]);

  useEffect(() => {
    async function loadAllCandidates() {
      setLoading(true);
      setError("");
      try {
        let allResults = [];
        let page = 1;
        let hasMore = true;

        while (hasMore) {
          const response = await hrApi.listCandidates({ page, sort: "highest_score" });
          allResults = allResults.concat(response.candidates || []);
          hasMore = response.has_next || false;
          page += 1;
        }

        setAllCandidates(allResults.filter((item) => item?.result_id));
      } catch (loadError) {
        setError(loadError.message || "Failed to load candidates.");
      } finally {
        setLoading(false);
      }
    }
    loadAllCandidates();
  }, []);

  useEffect(() => {
    async function loadCompare() {
      if (selectedResultIds.length < 2) {
        setCompareData([]);
        return;
      }
      setCompareLoading(true);
      setError("");
      try {
        const response = await hrApi.compareCandidates(selectedResultIds);
        setCompareData(Array.isArray(response?.candidates) ? response.candidates : []);
      } catch (loadError) {
        setError(loadError.message || "Failed to load comparison data.");
        setCompareData([]);
      } finally {
        setCompareLoading(false);
      }
    }
    loadCompare();
  }, [selectedResultIds]);

  const selectedCandidates = useMemo(
    () => allCandidates.filter((c) => selectedResultIds.includes(c.result_id)),
    [allCandidates, selectedResultIds],
  );

  const averageFinalScore = compareData.length
    ? formatPercent(compareData.reduce((sum, c) => sum + (Number(c?.final_score ?? c?.score) || 0), 0) / compareData.length)
    : "0%";

  const hasPreselectedCandidates = selectedResultIds.length > 0;
  const invalidSelection = selectedResultIds.length > 0 && selectedResultIds.length < 2;

  function syncSelectedIds(ids) {
    setSearchParams(ids.length ? { ids: ids.join(",") } : {});
  }

  function clearSelection() {
    syncSelectedIds([]);
  }

  if (loading) return <p className="center muted">Loading candidates for comparison...</p>;

  return (
    <div className="stack">
      <PageHeader
        title="Candidate Comparison"
        subtitle="Compare 2-3 candidates side-by-side across ATS score, stage, recommendation, skills, and interview summary."
        actions={
          <>
            <Link to="/hr/candidates" className="button-link subtle-button">
              Back to Candidates
            </Link>
            <button type="button" onClick={clearSelection}>
              Clear Selection
            </button>
          </>
        }
      />

      {error && <p className="alert error">{error}</p>}

      {!hasPreselectedCandidates && (
        <section className="card stack empty-state-card">
          <p className="eyebrow">Comparison</p>
          <h3>Select candidates to compare</h3>
          <p className="muted">Select candidates to compare from the HR candidates page.</p>
          <Link to="/hr/candidates" className="button-link subtle-button">Go to Candidates</Link>
        </section>
      )}

      {invalidSelection && (
        <section className="card stack empty-state-card">
          <p className="muted">Select at least 2 candidates to load comparison data.</p>
        </section>
      )}

      {compareLoading && (
        <section className="card stack empty-state-card">
          <p className="muted">Loading comparison data...</p>
        </section>
      )}

      {compareData.length > 0 && (
        <>
          <section className="card stack">
            <div className="title-row">
              <div>
                <p className="eyebrow">Comparison Matrix</p>
                <h3>Side-by-side candidate review</h3>
              </div>
              <p className="muted">{compareData.length} candidates</p>
            </div>

            <div className="comparison-grid">
              {compareData.map((candidate) => (
                <article key={candidate.result_id} className="question-preview-card stack-sm ats-compare-card">
                  <div className="title-row">
                    <div>
                      <strong>{candidate?.candidate?.name || "Candidate"}</strong>
                      <p className="muted">{candidate?.candidate?.candidate_uid || "N/A"}</p>
                    </div>
                    <StatusBadge status={candidate?.stage} />
                  </div>

                  <div className="metric-grid compact">
                    <MetricCard label="Final score" value={formatPercent(candidate?.final_score ?? candidate?.score)} />
                    <MetricCard label="Match %" value={formatPercent(candidate?.score)} />
                    <MetricCard label="Recommendation" value={candidate?.recommendation || "N/A"} />
                  </div>

                  <div className="stack-sm">
                    <p><strong>Assigned JD:</strong> {candidate?.assigned_jd?.title || candidate?.job?.title || "Not assigned"}</p>
                    <p><strong>Resume/JD:</strong> {formatPercent(candidate?.score_breakdown?.resume_jd_match_score)}</p>
                    <p><strong>Skills:</strong> {formatPercent(candidate?.score_breakdown?.skills_match_score)}</p>
                    <p><strong>Interview:</strong> {formatPercent(candidate?.score_breakdown?.interview_performance_score)}</p>
                    <p><strong>Communication:</strong> {formatPercent(candidate?.score_breakdown?.communication_behavior_score)}</p>
                    <p><strong>Skills:</strong> {(candidate?.parsed_resume?.skills || []).join(", ") || "No skills extracted."}</p>
                    <p><strong>Interview summary:</strong> {summaryText(candidate?.interview_summary)}</p>
                  </div>

                  <Link to={`/hr/candidates/${candidate?.candidate?.candidate_uid}`} className="button-link subtle-button">
                    View Detail
                  </Link>
                </article>
              ))}
            </div>
          </section>

          <section className="comparison-summary">
            <div className="summary-stat">
              <p className="eyebrow">Average Final Score</p>
              <h3>{averageFinalScore}</h3>
            </div>
            <div className="summary-stat">
              <p className="eyebrow">Best Candidate</p>
              <h3>{compareData[0]?.candidate?.name || "N/A"}</h3>
            </div>
            <div className="summary-stat">
              <p className="eyebrow">Selected Stage Count</p>
              <h3>{compareData.filter((c) => c?.stage?.key === "selected").length}</h3>
            </div>
          </section>
        </>
      )}

      {hasPreselectedCandidates && selectedCandidates.length === 0 && !compareLoading && !error && (
        <section className="card stack empty-state-card">
          <p className="muted">No candidates available for the selected comparison IDs.</p>
        </section>
      )}

      {selectedCandidates.length > 0 && compareData.length === 0 && !compareLoading && !error && !invalidSelection && (
        <section className="card stack empty-state-card">
          <p className="muted">No comparison data available yet for the selected candidates.</p>
        </section>
      )}
    </div>
  );
}
