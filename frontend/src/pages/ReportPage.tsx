import { useNavigate } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { useInterview, useInterviewDispatch } from '../hooks/useInterview';
import ATSExportButton from '../components/ATSExportButton';

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

  const scores = report.scorecard?.criteria.map((criterion) => [
    criterion.label,
    criterion.score_percentage,
  ] as const) ?? [
    ['Technical', report.technical_score],
    ['Communication', report.communication_score],
  ] as const;

  return (
    <main className="mx-auto max-w-4xl px-5 pb-20 pt-28 sm:px-8">
      <header className="border-b border-border pb-8">
        <p className="eyebrow text-text-muted">HR screening report</p>
        <h1 className="editorial mt-5 text-5xl sm:text-6xl">Screening scorecard</h1>
        <p className="mt-3 max-w-xl text-text-secondary">
          Evidence-backed stage scores and policy checks to support a consistent human review.
        </p>
      </header>

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
          <div className="space-y-6">
            {scores.map(([label, score]) => (
              <div key={label}>
                <div className="mb-2 flex items-center justify-between gap-4 text-sm">
                  <span>{label}</span>
                  <span className="mono text-text-secondary">{Math.round(score)} / 100</span>
                </div>
                <div className="score-bar" aria-label={`${label} score ${score} out of 100`}>
                  <span style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
                </div>
              </div>
            ))}
          </div>
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
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              {scores.map(([label, score]) => (
                <div key={label}>
                  <div className="mb-2 flex items-center justify-between gap-4 text-sm">
                    <span>{label}</span>
                    <span className="mono text-text-secondary">{Math.round(score)}%</span>
                  </div>
                  <div className="score-bar" aria-label={`${label} score ${score} percent`}>
                    <span style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {report.screening_summary && (
        <section className="border-b border-border py-9">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="eyebrow text-text-muted">Screening policy checks</p>
            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                report.screening_summary.human_checkpoint_required
                  ? 'bg-danger/10 text-danger'
                  : 'bg-surface-elevated text-text-secondary'
              }`}
              role="status"
            >
              {report.screening_summary.human_checkpoint_required
                ? 'Human review required'
                : 'No human checkpoint raised'}
            </span>
          </div>
          {!report.screening_summary.policy_configured && (
            <p className="mt-4 text-sm text-text-secondary">
              Approved salary bands are not configured, so salary alignment was not assessed.
            </p>
          )}
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="eyebrow text-text-muted">Expected salary</dt>
              <dd className="mt-1 text-sm">
                {report.screening_summary.candidate_expected_lpa === null
                  ? 'Not disclosed'
                  : `${report.screening_summary.candidate_expected_lpa} LPA · ${report.screening_summary.salary_alignment_status.replaceAll('_', ' ')}`}
              </dd>
              {report.screening_summary.salary_evidence && (
                <dd className="mt-1 text-xs text-text-muted">
                  Evidence: “{report.screening_summary.salary_evidence}”
                </dd>
              )}
            </div>
            <div>
              <dt className="eyebrow text-text-muted">Notice period</dt>
              <dd className="mt-1 text-sm">
                {report.screening_summary.candidate_notice_days === null
                  ? 'Not disclosed'
                  : `${report.screening_summary.candidate_notice_days} days · ${report.screening_summary.notice_alignment_status.replaceAll('_', ' ')}`}
              </dd>
              {report.screening_summary.notice_evidence && (
                <dd className="mt-1 text-xs text-text-muted">
                  Evidence: “{report.screening_summary.notice_evidence}”
                </dd>
              )}
            </div>
          </dl>
          {report.screening_summary.checkpoint_reasons.length > 0 && (
            <ul className="mt-5 space-y-2 text-sm text-danger">
              {report.screening_summary.checkpoint_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          {report.screening_summary.red_flags.length > 0 && (
            <ul className="mt-5 space-y-3">
              {report.screening_summary.red_flags.map((flag, index) => (
                <li className="border-t border-border pt-3 text-sm" key={`${index}-${flag.description}`}>
                  <p>{flag.description}</p>
                  <p className="mt-1 text-xs text-text-muted">Evidence: “{flag.evidence}”</p>
                </li>
              ))}
            </ul>
          )}
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
