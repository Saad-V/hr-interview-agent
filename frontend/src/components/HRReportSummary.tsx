import { useState } from 'react';
import type { InterviewReport } from '../types/interview';

interface HRReportSummaryProps {
  report: Pick<
    InterviewReport,
    | 'salary_band_check'
    | 'red_flags'
    | 'human_checkpoint_required'
    | 'human_checkpoint_reasons'
    | 'screening_summary'
  >;
}

interface HRCompetencyBarsProps {
  technicalScore: number | null;
  communicationScore: number | null;
}

export function HRCompetencyBars({
  technicalScore,
  communicationScore,
}: HRCompetencyBarsProps) {
  const scores = [
    ['STAR Competency & Verification', technicalScore],
    ['Communication & Culture Fit', communicationScore],
  ] as const;

  return (
    <div className="space-y-5">
      {scores.map(([label, score]) => (
        <div key={label}>
          <div className="mb-2 flex items-center justify-between gap-4 text-sm">
            <span>{label}</span>
            <span className="mono text-text-secondary">
              {score === null ? '—' : `${Math.round(score)} / 100`}
            </span>
          </div>
          <div
            className="score-bar"
            aria-label={`${label} score ${score ?? 'unavailable'} out of 100`}
          >
            <span
              style={{
                width: `${Math.min(100, Math.max(0, score ?? 0))}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function HRReportSummary({ report }: HRReportSummaryProps) {
  const [managerAction, setManagerAction] = useState<'approved' | 'rejected' | null>(
    null
  );
  const screening = report.screening_summary;
  const salaryCheck = report.salary_band_check;
  const checkpointRequired =
    report.human_checkpoint_required ?? screening?.human_checkpoint_required ?? false;
  const checkpointReasons =
    report.human_checkpoint_reasons ?? screening?.checkpoint_reasons ?? [];
  const flags =
    report.red_flags?.length
      ? report.red_flags
      : screening?.red_flags ?? [];

  const approvedMin = salaryCheck?.approved_min_lpa ?? screening?.approved_min_lpa;
  const approvedMax = salaryCheck?.approved_max_lpa ?? screening?.approved_max_lpa;
  const expectedSalary =
    salaryCheck?.candidate_expected_lpa ?? screening?.candidate_expected_lpa ?? null;
  const salaryStatus =
    salaryCheck?.salary_alignment_status ??
    screening?.salary_alignment_status ??
    'NOT_CONFIGURED';
  const maxNotice =
    salaryCheck?.max_notice_days ?? screening?.max_notice_days;
  const candidateNotice =
    salaryCheck?.candidate_notice_days ?? screening?.candidate_notice_days ?? null;
  const noticeStatus =
    salaryCheck?.notice_alignment_status ??
    screening?.notice_alignment_status ??
    'NOT_DISCLOSED';

  const salaryStatusLabel: Record<string, string> = {
    WITHIN_BAND: 'Aligned',
    OUTSIDE_BAND: 'Requires Human Approval',
    BELOW_BAND: 'Below Band',
    NOT_DISCLOSED: 'Not Disclosed',
    NOT_CONFIGURED: 'Not Configured',
  };
  const noticeStatusLabel: Record<string, string> = {
    ALIGNED: 'Aligned',
    EXCEEDS_POLICY: 'Exceeds Policy',
    NOT_DISCLOSED: 'Not Disclosed',
  };

  return (
    <>
      {checkpointRequired && (
        <section
          className="my-8 rounded-xl border-2 border-danger/50 bg-danger/5 p-6"
          aria-labelledby="human-checkpoint-heading"
        >
          <p className="eyebrow text-danger" id="human-checkpoint-heading">
            HUMAN CHECKPOINT TRIGGERED — ESCALATED FOR APPROVAL
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-text-primary">
            {checkpointReasons.map((reason, index) => (
              <li key={`${index}-${reason}`}>{reason}</li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              className={`rounded-lg border px-4 py-2 text-sm font-medium ${
                managerAction === 'approved'
                  ? 'border-primary bg-primary text-white'
                  : 'border-border bg-surface text-text-primary'
              }`}
              type="button"
              aria-pressed={managerAction === 'approved'}
              onClick={() => setManagerAction('approved')}
            >
              Approve Exception
            </button>
            <button
              className={`rounded-lg border px-4 py-2 text-sm font-medium ${
                managerAction === 'rejected'
                  ? 'border-danger bg-danger text-white'
                  : 'border-border bg-surface text-text-primary'
              }`}
              type="button"
              aria-pressed={managerAction === 'rejected'}
              onClick={() => setManagerAction('rejected')}
            >
              Flag for Rejection
            </button>
            {managerAction && (
              <span className="text-sm text-text-secondary" role="status">
                {managerAction === 'approved'
                  ? 'Exception approved for review.'
                  : 'Flagged for rejection review.'}
              </span>
            )}
          </div>
        </section>
      )}

      <section className="border-b border-border py-8">
        <p className="eyebrow text-text-muted">
          Salary Band &amp; Notice Period Check
        </p>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <article className="card p-5">
            <h2 className="text-base font-semibold">Salary Band Check</h2>
            <dl className="mt-4 space-y-4 text-sm">
              <div>
                <dt className="text-text-muted">Approved Band</dt>
                <dd className="mt-1">
                  {approvedMin === null || approvedMin === undefined ||
                  approvedMax === null || approvedMax === undefined
                    ? 'Not configured'
                    : `₹${approvedMin} – ₹${approvedMax} LPA`}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Candidate Expected CTC</dt>
                <dd className="mt-1">
                  {expectedSalary === null
                    ? 'Not Disclosed'
                    : `₹${expectedSalary} LPA`}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Salary Alignment</dt>
                <dd className="mt-2">
                  <span
                    className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${
                      salaryStatus === 'WITHIN_BAND'
                        ? 'bg-surface-elevated text-text-primary'
                        : 'bg-danger/10 text-danger'
                    }`}
                    role="status"
                  >
                    {salaryStatusLabel[salaryStatus] ?? salaryStatus.replaceAll('_', ' ')}
                  </span>
                </dd>
              </div>
            </dl>
          </article>

          <article className="card p-5">
            <h2 className="text-base font-semibold">Notice Period &amp; Availability</h2>
            <dl className="mt-4 space-y-4 text-sm">
              <div>
                <dt className="text-text-muted">Max Policy Notice</dt>
                <dd className="mt-1">
                  {maxNotice === undefined ? 'Not configured' : `${maxNotice} Days`}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Candidate Stated Notice</dt>
                <dd className="mt-1">
                  {candidateNotice === null
                    ? screening?.notice_evidence
                      ? 'Verified in Transcript'
                      : 'Not Disclosed'
                    : `${candidateNotice} Days`}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Notice Alignment</dt>
                <dd className="mt-2">
                  <span
                    className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${
                      noticeStatus === 'ALIGNED'
                        ? 'bg-surface-elevated text-text-primary'
                        : 'bg-danger/10 text-danger'
                    }`}
                    role="status"
                  >
                    {noticeStatusLabel[noticeStatus] ?? noticeStatus.replaceAll('_', ' ')}
                  </span>
                </dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section className="border-b border-border py-8">
        <p className="eyebrow text-text-muted">
          Red Flags with Verbatim Evidence
        </p>
        {flags.length > 0 ? (
          <ul className="mt-4 space-y-4">
            {flags.map((flag, index) => (
              <li
                className="rounded-lg border border-border p-4"
                key={`${flag.turn_number ?? index}-${flag.category}-${flag.description}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold">
                    {flag.category ?? 'SCREENING_CONCERN'}
                  </span>
                  {flag.turn_number !== undefined && flag.turn_number !== null && (
                    <span className="mono text-xs text-text-muted">
                      Turn {flag.turn_number}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-text-secondary">{flag.description}</p>
                <blockquote className="mt-3 border-l-2 border-border pl-3 text-sm italic text-text-muted">
                  “{flag.evidence}”
                </blockquote>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-text-secondary">
            No Red Flags Detected — Candidate responses passed consistency and behavioral checks.
          </p>
        )}
      </section>
    </>
  );
}
