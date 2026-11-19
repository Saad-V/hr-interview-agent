import { ArrowRight, Check } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

const steps = [
  ['01', 'Candidate', 'Ingest the candidate resume, experience tier (Fresher or 0–6 yrs), and HR policy.'],
  ['02', 'Verify', 'Confirm background details, official notice period, and earliest joining availability.'],
  ['03', 'Assess', 'Probe past projects with STAR questions and evaluate motivation and culture fit.'],
  ['04', 'Salary', 'Check compensation expectations deterministically against the approved salary band.'],
  ['05', 'HR Notes', 'Generate a confidential HR scorecard, structured notes, and final recommendation.'],
  ['HC', 'Human Checkpoint', 'Automatically escalate out-of-band salary requests or evidence-backed red flags.'],
];

const features = [
  ['Fresher & 0–6 Yr Tracks', 'Separate question sets tailored for freshers and experienced candidates.'],
  ['Prohibited-Question Filter', 'Strict guardrail blocking inquiries on age, religion, marital, or family status.'],
  ['Salary Band Lookup', 'Compares expected CTC against approved bands before final-round handoff.'],
  ['Red Flags with Evidence', 'Every flagged risk is backed by a verbatim quote from the candidate transcript.'],
  ['Chat & Voice Room', 'Supports text and voice responses with speech-to-text artifact tolerance.'],
  ['Confidential Scorecard', 'Exportable HR notes, salary alignment status, and ATS-ready summary.'],
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <main>
      <section className="landing-shell hero">
        <div>
          <p className="eyebrow text-text-muted">05 / HR ROUND · AUTOMATED SCREENING AGENT</p>
          <h1 className="editorial hero-title">
            Run the HR round <em>with structure and guardrails.</em>
          </h1>
          <p className="hero-copy">
            Automate HR screening for freshers and 0–6 year candidates. Verify notice periods,
            probe past projects with STAR questions, check salary bands, and escalate red flags
            to human review.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-6">
            <button className="primary-action" onClick={() => navigate('/setup')} type="button">
              Start HR screening <ArrowRight size={17} />
            </button>
          </div>
        </div>

        <aside className="preview-card" aria-label="HR screening agent preview">
          <div className="flex items-center justify-between gap-4">
            <p className="eyebrow text-text-muted">AGENT PREVIEW</p>
            <span className="mono text-text-muted">04 / SALARY CHECK</span>
          </div>
          <h2 className="editorial mt-8 text-3xl leading-tight">
            Could you confirm your official notice period and expected annual CTC for this role?
          </h2>
          <div className="preview-evaluation">
            <p className="eyebrow text-text-muted">AGENT CORE OUTPUT</p>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-start gap-2 font-medium">
                <Check size={16} aria-hidden="true" />
                <span>Notice Period: 30 days · Verified</span>
              </div>
              <div className="flex items-start gap-2 font-medium">
                <Check size={16} aria-hidden="true" />
                <span>Salary Band: ₹10.5 LPA (Approved: ₹8–12 LPA) · Within Band</span>
              </div>
              <div className="flex items-start gap-2 font-medium">
                <Check size={16} aria-hidden="true" />
                <span>Guardrails: Compliant · 0 Red Flags</span>
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="landing-shell landing-section" id="how-it-works">
        <p className="eyebrow text-text-muted">END-TO-END OPERATING FLOW</p>
        <h2 className="editorial mt-3 text-4xl">From resume to HR scorecard.</h2>
        <div className="numbered-grid">
          {steps.map(([number, title, description]) => (
            <article key={number}>
              <p className="mono text-text-muted">{number}</p>
              <h3 className="mt-5 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-shell landing-section">
        <div className="mb-8">
          <p className="eyebrow text-text-muted">GUARDRAILS &amp; CAPABILITIES</p>
          <h2 className="editorial mt-3 text-4xl">Built for compliant, repeatable screening.</h2>
        </div>
        <div className="feature-grid">
          {features.map(([title, description]) => (
            <article key={title}>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-shell mt-24 border-t border-border py-8">
        <div className="flex flex-wrap items-center justify-between gap-4 text-sm text-text-secondary">
          <span>© {new Date().getFullYear()} HR Interviewer Agent · Confidential HR Workspace</span>
          <div className="flex gap-5">
            <Link className="text-link" to="/login">Sign in</Link>
            <a className="text-link" href="#how-it-works">How it works</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
