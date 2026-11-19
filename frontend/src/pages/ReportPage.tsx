import { useNavigate } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { useInterview, useInterviewDispatch } from '../hooks/useInterview';
import ATSExportButton from '../components/ATSExportButton';
import HRReportSummary, { HRCompetencyBars } from '../components/HRReportSummary';

export default function ReportPage() {
  const navigate = useNavigate();
  const { report, sessionId } = useInterview();
  const dispatch = useInterviewDispatch();

  const handleNewInterview = () => {
    dispatch({ type: 'RESET' });
    navigate('/setup');
  };

  if (!report) {
    return (
      <main className="flex min-h-screen items-center justify-center px-5 pt-20">
        <section className="text-center">
          <p className="text-text-secondary">No report is available yet.</p>
          <button className="primary-action mt-5" onClick={handleNewInterview} type="button">
            Start an interview
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-5 pb-20 pt-28 sm:px-8">
      <header className="border-b border-border pb-8">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow text-text-muted">Confidential HR screening report</p>
            <h1 className="editorial mt-5 text-5xl sm:text-6xl">
              HR Scorecard &amp; Interviewer Notes
            </h1>
            <p className="mt-3 max-w-xl text-text-secondary">
              Evidence-backed stage scores and policy checks to support a consistent human review.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className="primary-action"
              onClick={() => window.print()}
              type="button"
            >
              Export Scorecard (PDF / Print)
            </button>
          </div>
        </div>
      </header>

      <HRReportSummary report={report} />

      <section className="grid gap-8 border-b border-border py-9 sm:grid-cols-[1fr_1.2fr] sm:items-center">
        <div>
          <p className="eyebrow text-text-muted">
            {report.scorecard ? 'Weighted HR score' : 'Overall score'}
          </p>
          <p className="editorial mt-2 text-8xl leading-none">
            {Math.round(report.overall_score)}
            <span className="ml-2 text-3xl text-text-muted">/100</span>
          </p>
          <p className="mt-3 text-xs text-text-muted">
            {report.scorecard
              ? `Weighted across HR stages; raw rubric total is ${report.total_awarded_score ?? '—'} / ${report.total_maximum_score ?? '—'}.`
              : report.rubric_version && report.total_awarded_score !== null
              && report.total_awarded_score !== undefined
              && report.total_maximum_score !== null
              && report.total_maximum_score !== undefined
              ? `Calculated from ${report.total_awarded_score} / ${report.total_maximum_score} rubric points across ${report.question_count} answers.`
              : 'Legacy AI-generated score; not calculated from the current rubric.'}
          </p>
          {sessionId && report.rubric_version === 'hr-rubric-v1' && (
            <div className="mt-5">
              <ATSExportButton sessionId={sessionId} />
            </div>
          )}
        </div>
        {report.scorecard ? (
          <div className="space-y-3">
            <p className="eyebrow text-text-muted">Decision support</p>
            <p className="text-sm leading-7 text-text-secondary">
              Four HR stages are weighted by the configured policy. Use the stage and evidence breakdown below as support for recruiter judgment, not as an automatic employment decision.
            </p>
          </div>
        ) : (
          <HRCompetencyBars
            technicalScore={report.technical_score}
            communicationScore={report.communication_score}
          />
        )}
      </section>

      {report.scorecard && (
        <section className="border-b border-border py-9">
          <p className="eyebrow text-text-muted">Weighted stage scorecard</p>
          <p className="mt-2 text-sm text-text-secondary">
            Recommendations are decision support. Human review is required when a checkpoint is raised.
          </p>
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            {report.scorecard.sections.map((section) => (
              <div key={section.category}>
                <div className="mb-2 flex items-start justify-between gap-4 text-sm">
                  <span>{section.title}</span>
                  <span className="mono shrink-0 text-text-secondary">
                    {Math.round(section.score_percentage)}% · {section.weight}%
                  </span>
                </div>
                <div
                  className="score-bar"
                  aria-label={`${section.title}: ${section.score_percentage} percent, weighted ${section.weight} percent`}
                >
                  <span style={{ width: `${Math.min(100, Math.max(0, section.score_percentage))}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <p className="eyebrow text-text-muted">HR competencies</p>
            <div className="mt-4">
              <HRCompetencyBars
                technicalScore={report.technical_score}
                communicationScore={report.communication_score}
              />
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-10 border-b border-border py-9 sm:grid-cols-2">
        <div>
          <p className="eyebrow text-text-muted">Strengths</p>
          <ul className="mt-4 space-y-3">
            {report.strengths.map((strength, index) => (
              <li className="border-t border-border pt-3 text-sm leading-6" key={`${index}-${strength}`}>
                {strength}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="eyebrow text-text-muted">Improvements</p>
          <ul className="mt-4 space-y-3">
            {report.areas_for_improvement.map((area, index) => (
              <li className="border-t border-border pt-3 text-sm leading-6" key={`${index}-${area}`}>
                {area}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="grid gap-8 py-9 sm:grid-cols-2">
        <div>
          <p className="eyebrow text-text-muted">Deterministic recommendation</p>
          <h2 className="editorial mt-3 text-3xl">{report.recommendation}</h2>
        </div>
        <div>
          <p className="eyebrow text-text-muted">Summary</p>
          <p className="mt-3 text-sm leading-7 text-text-secondary">{report.summary}</p>
        </div>
      </section>

      <div className="border-t border-border pt-7">
        <button className="primary-action" onClick={handleNewInterview} type="button">
          <RotateCcw size={16} />
          Start a new interview
        </button>
      </div>
    </main>
  );
}
