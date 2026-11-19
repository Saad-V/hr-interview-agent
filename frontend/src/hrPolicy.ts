import { InterviewDifficulty } from './types/interview';

export const hrDifficultyPools = [
  {
    value: InterviewDifficulty.EASY,
    label: 'Fresher (0 Yrs)',
    description: 'Entry-level question set · Academic STAR & immediate joining',
    activeClass: 'active-easy',
    defaultSalaryBand: { min: 4, max: 7 },
    maxNoticeDays: 15,
  },
  {
    value: InterviewDifficulty.MEDIUM,
    label: 'Junior (1–3 Yrs)',
    description: 'Early-career question set · Production STAR & notice check',
    activeClass: 'active-medium',
    defaultSalaryBand: { min: 7, max: 14 },
    maxNoticeDays: 30,
  },
  {
    value: InterviewDifficulty.HARD,
    label: 'Mid-Level (3–6 Yrs)',
    description: 'Experienced question set · Ownership STAR & band check',
    activeClass: 'active-hard',
    defaultSalaryBand: { min: 14, max: 24 },
    maxNoticeDays: 60,
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
    title: '02 / STAR PROJECTS: Past Project Probing',
    weight: 35,
  },
  {
    category: 'TECHNICAL',
    title: '03 / ASSESS: Motivation, Communication & Culture Fit',
    weight: 25,
  },
  {
    category: 'BEHAVIORAL',
    title: '04 / SALARY: Compensation Band & Final Logistics',
    weight: 20,
  },
] as const;

export const hrPolicySafeguards = [
  'Keep questions job-related and grounded in evidence from the candidate’s answers.',
  'Do not ask about age, religion, caste, marital or family status, pregnancy, or medical history.',
  'Salary bands and notice thresholds are set by the hiring team; exceptions and evidence-backed concerns are routed for human review.',
] as const;
