import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  History,
  Loader2,
  AlertCircle,
  Play,
} from 'lucide-react';
import FileDropZone from '../components/FileDropZone';
import { useInterviewDispatch } from '../hooks/useInterview';
import { interviewService } from '../services/interviewService';
import { resumeService } from '../services/resumeService';
import { jobDescriptionService } from '../services/jobDescriptionService';
import { InterviewDifficulty, InterviewStatus } from '../types/interview';
import { hrDifficultyPools, hrPolicySafeguards, hrWorkflowSections } from '../hrPolicy';

const durationTicks = [
  { value: 10, label: '10m' },
  { value: 30, label: '30m' },
  { value: 60, label: '60m' },
  { value: 90, label: '90m' },
  { value: 120, label: '120m' },
];

export default function SetupPage() {
  const navigate = useNavigate();
  const dispatch = useInterviewDispatch();

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>(
    InterviewDifficulty.MEDIUM
  );
  const [roleTitle, setRoleTitle] = useState('Software Engineer');
  const [minSalaryLpa, setMinSalaryLpa] = useState('7.0');
  const [maxSalaryLpa, setMaxSalaryLpa] = useState('14.0');
  const [maxNoticePeriodDays, setMaxNoticePeriodDays] = useState('30');
  const [workLocation, setWorkLocation] = useState('Hybrid / Bengaluru');
  const [roleRequirements, setRoleRequirements] = useState(
    'Assess communication clarity, STAR project ownership, team collaboration, and compensation alignment.'
  );
  const [duration, setDuration] = useState(30);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const minSalary = Number(minSalaryLpa);
  const maxSalary = Number(maxSalaryLpa);
  const noticeDays = Number(maxNoticePeriodDays);
  const isValid = Boolean(
    resumeFile &&
      roleTitle.trim() &&
      minSalaryLpa !== '' &&
      maxSalaryLpa !== '' &&
      Number.isFinite(minSalary) &&
      Number.isFinite(maxSalary) &&
      minSalary >= 0 &&
      maxSalary > 0 &&
      maxSalary >= minSalary &&
      Number.isFinite(noticeDays) &&
      noticeDays >= 0 &&
      duration >= 10 &&
      duration <= 120
  );

  const handleStart = async () => {
    if (!resumeFile || !isValid) return;

    setIsLoading(true);
    setError(null);

    try {
      // 1. Create session
      const session = await interviewService.createSession({
        planned_duration_minutes: duration,
        difficulty,
      });

      dispatch({
        type: 'SET_SESSION',
        payload: { sessionId: session.id, status: session.status as InterviewStatus },
      });

      // 2. Upload resume
      await resumeService.uploadResume(session.id, resumeFile);

      // 3. Submit the approved HR policy as the interview's role brief
      await jobDescriptionService.submitHrPolicy(session.id, {
        role_title: roleTitle.trim(),
        min_salary_lpa: minSalary,
        max_salary_lpa: maxSalary,
        max_notice_period_days: noticeDays,
        work_location: workLocation.trim(),
        role_requirements: roleRequirements.trim(),
      });

      // Navigate to preparing
      navigate('/preparing');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Something went wrong. Please try again.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen pb-20" style={{ paddingTop: '120px', paddingLeft: '24px', paddingRight: '24px' }}>
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        style={{ maxWidth: '900px', marginLeft: 'auto', marginRight: 'auto' }}
      >
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-10"
        >
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="eyebrow text-text-muted">05 / HR ROUND — INTERVIEWER AGENT</p>
              <h1 className="editorial mt-3 text-5xl md:text-6xl">
                Configure HR Screening Round
              </h1>
              <p className="mt-3 max-w-xl text-text-secondary">
                Upload the candidate resume and set the approved salary band, notice period policy, and experience tier.
              </p>
            </div>
            <Link
              className="text-link inline-flex items-center gap-2 text-sm"
              to="/sessions"
            >
              <History className="h-4 w-4" aria-hidden="true" />
              View past interviews and reports
            </Link>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1, delayChildren: 0.2 }}
          className="space-y-8"
        >
          {/* Candidate and HR policy */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
            className="space-y-4"
          >
            <div className="mb-6">
              <p className="eyebrow text-text-muted">01 — Candidate &amp; role policy</p>
              <h2 className="editorial mt-2 text-3xl">Candidate resume and approved HR policy.</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Resume */}
              <div className="card p-6">
                <h3 className="mb-4 text-sm font-semibold text-text-primary">
                  Candidate Resume (PDF / DOCX) · Required
                </h3>
                <FileDropZone
                  label="Upload your resume"
                  accept=".pdf,.docx"
                  file={resumeFile}
                  onFileSelect={setResumeFile}
                  onClear={() => setResumeFile(null)}
                  disabled={isLoading}
                />
              </div>

              {/* HR Policy */}
              <div className="card p-6">
                <h3 className="mb-5 text-sm font-semibold text-text-primary">
                  HR Policy, Notice Period &amp; Salary Band Sheet
                </h3>
                <div className="space-y-4">
                  <label className="form-label" htmlFor="role-title">
                    Target Role Title
                    <input
                      id="role-title"
                      className="form-control mt-2"
                      value={roleTitle}
                      onChange={(event) => setRoleTitle(event.target.value)}
                      disabled={isLoading}
                      required
                    />
                  </label>

                  <fieldset>
                    <legend className="form-label">Approved Salary Band (INR LPA)</legend>
                    <div className="grid grid-cols-2 gap-3">
                      <label className="form-label" htmlFor="min-salary-lpa">
                        Min LPA
                        <input
                          id="min-salary-lpa"
                          className="form-control mt-2"
                          type="number"
                          min="0"
                          step="0.1"
                          value={minSalaryLpa}
                          onChange={(event) => setMinSalaryLpa(event.target.value)}
                          disabled={isLoading}
                          required
                        />
                      </label>
                      <label className="form-label" htmlFor="max-salary-lpa">
                        Max LPA
                        <input
                          id="max-salary-lpa"
                          className="form-control mt-2"
                          type="number"
                          min="0"
                          step="0.1"
                          value={maxSalaryLpa}
                          onChange={(event) => setMaxSalaryLpa(event.target.value)}
                          disabled={isLoading}
                          required
                        />
                      </label>
                    </div>
                    {maxSalaryLpa !== '' && minSalaryLpa !== '' && maxSalary < minSalary && (
                      <p className="mt-2 text-sm text-danger" role="alert">
                        Maximum salary must be greater than or equal to minimum salary.
                      </p>
                    )}
                  </fieldset>

                  <label className="form-label" htmlFor="max-notice-days">
                    Max Notice Period Allowed (Days)
                    <select
                      id="max-notice-days"
                      className="form-control mt-2"
                      value={maxNoticePeriodDays}
                      onChange={(event) => setMaxNoticePeriodDays(event.target.value)}
                      disabled={isLoading}
                    >
                      <option value="0">0 / Immediate</option>
                      <option value="15">15 Days</option>
                      <option value="30">30 Days</option>
                      <option value="60">60 Days</option>
                      <option value="90">90 Days</option>
                    </select>
                  </label>

                  <label className="form-label" htmlFor="work-location">
                    Work Location
                    <input
                      id="work-location"
                      className="form-control mt-2"
                      value={workLocation}
                      onChange={(event) => setWorkLocation(event.target.value)}
                      disabled={isLoading}
                    />
                  </label>

                  <label className="form-label" htmlFor="role-requirements">
                    Role &amp; Culture Notes
                    <textarea
                      id="role-requirements"
                      className="form-control mt-2 min-h-28 resize-y"
                      value={roleRequirements}
                      onChange={(event) => setRoleRequirements(event.target.value)}
                      disabled={isLoading}
                    />
                  </label>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Settings Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
            className="space-y-4"
          >
            <div className="mb-6">
              <p className="eyebrow text-text-muted">02 — Your session</p>
              <h2 className="editorial mt-2 text-3xl">Choose how you want to practice.</h2>
            </div>

            <div className="space-y-8">
              {/* Difficulty Level */}
              <div className="card p-8">
                <h3 className="text-lg font-semibold text-text-primary mb-6">Experience Pool</h3>
                <div className="grid grid-cols-3 gap-4">
                  {hrDifficultyPools.map((d) => (
                    <motion.button
                      key={d.value}
                      type="button"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => {
                        setDifficulty(d.value);
                        setMinSalaryLpa(d.defaultSalaryBand.min.toFixed(1));
                        setMaxSalaryLpa(d.defaultSalaryBand.max.toFixed(1));
                        setMaxNoticePeriodDays(String(d.maxNoticeDays));
                      }}
                      disabled={isLoading}
                      className={`
                        difficulty-btn
                        ${difficulty === d.value ? `active ${d.activeClass}` : ''}
                        ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
                      `}
                    >
                      <p className="text-sm font-semibold text-text-primary">
                        {d.label}
                      </p>
                      <p className="text-xs text-text-muted mt-2">{d.description}</p>
                    </motion.button>
                  ))}
                </div>
              </div>

              {/* Duration */}
              <div className="card p-8">
                <div className="flex items-end justify-between mb-6">
                  <div>
                    <h3 className="text-lg font-semibold text-text-primary">Session Duration</h3>
                  </div>
                  <div className="text-right">
                    <span className="mono text-3xl font-medium text-text-primary">
                      {duration}
                    </span>
                    <span className="text-sm text-text-muted ml-2">minutes</span>
                  </div>
                </div>

                <div className="mb-8">
                  <input
                    type="range"
                    min={10}
                    max={120}
                    step={5}
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    disabled={isLoading}
                    style={{ '--value': Math.round(((duration - 10) / 110) * 100) } as React.CSSProperties}
                  />
                </div>

                <div className="flex justify-between px-1">
                  {durationTicks.map((tick) => (
                    <motion.button
                      key={tick.value}
                      type="button"
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setDuration(tick.value)}
                      disabled={isLoading}
                      className={`
                        text-xs font-medium transition-all
                        ${
                          duration === tick.value
                            ? 'text-primary'
                            : 'text-text-muted hover:text-text-secondary'
                        }
                        ${isLoading ? 'cursor-not-allowed' : 'cursor-pointer'}
                      `}
                    >
                      {tick.label}
                    </motion.button>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          <section className="card space-y-6 p-8" aria-labelledby="hr-policy-title">
            <div>
              <p className="eyebrow text-text-muted">03 — Screening policy</p>
              <h2 className="editorial mt-2 text-3xl" id="hr-policy-title">A consistent, job-related process.</h2>
            </div>
            <ol className="divide-y divide-border border-y border-border">
              {hrWorkflowSections.map((section) => (
                <li className="flex flex-wrap items-start justify-between gap-3 py-3" key={section.category}>
                  <span className="text-sm text-text-primary">{section.title}</span>
                  <span className="mono text-sm text-text-muted">{section.weight}%</span>
                </li>
              ))}
            </ol>
            <ul className="space-y-2 text-sm leading-6 text-text-secondary">
              {hrPolicySafeguards.map((safeguard) => (
                <li className="border-l-2 border-border pl-3" key={safeguard}>{safeguard}</li>
              ))}
            </ul>
          </section>

          <p className="rounded-lg border border-border-subtle bg-surface-elevated px-4 py-3 text-center text-xs leading-5 text-text-muted">
            Active Guardrails: Equal Opportunity Filter (No Age, Religion, Marital, or Family Status Questions) · Confidential Notes · Out-of-Band Human Checkpoint
          </p>

          {/* Error Message */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 p-4 rounded-lg bg-danger/10 border border-danger/30"
            >
              <AlertCircle className="w-5 h-5 text-danger shrink-0" />
              <p className="text-sm text-danger">{error}</p>
            </motion.div>
          )}

          {/* Start Button */}
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
            whileHover={isValid && !isLoading ? { scale: 1.01 } : undefined}
            whileTap={isValid && !isLoading ? { scale: 0.98 } : undefined}
            onClick={handleStart}
            disabled={!isValid || isLoading}
            className={`
              w-full flex items-center justify-center gap-3 py-4 px-6 rounded-lg font-semibold text-lg transition-all duration-300
              ${isValid && !isLoading
                ? 'btn-gradient'
                : 'bg-surface-elevated text-text-muted cursor-not-allowed border border-border-subtle'
              }
            `}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Setting up interview...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                <span>Start Interview</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </motion.button>
        </motion.div>
      </motion.div>
    </div>
  );
}
