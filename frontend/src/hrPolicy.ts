import { InterviewDifficulty } from './types/interview';

export const hrDifficultyPools = [
  {
    value: InterviewDifficulty.EASY,
    label: 'Fresher pool',
    description: '0 years · academic or internship projects',
    activeClass: 'active-easy',
  },
  {
    value: InterviewDifficulty.MEDIUM,
    label: 'Junior pool',
    description: '1–3 years · hands-on project contributions',
    activeClass: 'active-medium',
  },
  {
    value: InterviewDifficulty.HARD,
    label: 'Mid-level pool',
    description: '3–6 years · ownership and career progression',
    activeClass: 'active-hard',
  },
] as const;

export const hrWorkflowSections = [
  {
    category: 'INTRODUCTION',
    title: '01 / VERIFY: Background, Notice Period & Availability',
    weight: 20,
  },
  {
    category: 'PROJECTS',
    title: '02 / STAR PROJECTS: Past Project Deep-Dive',
    weight: 35,
  },
  {
    category: 'TECHNICAL',
    title: '03 / ASSESS: Motivation, Communication & Culture Fit',
    weight: 25,
  },
  {
    category: 'BEHAVIORAL',
    title: '04 / SALARY: Compensation Expectations & Band Check',
    weight: 20,
  },
] as const;

export const hrPolicySafeguards = [
  'Keep questions job-related and grounded in evidence from the candidate’s answers.',
  'Do not ask about age, religion, caste, marital or family status, pregnancy, or medical history.',
  'Salary bands and notice thresholds are set by the hiring team; exceptions and evidence-backed concerns are routed for human review.',
] as const;
