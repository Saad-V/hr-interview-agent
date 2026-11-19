import json

from app.ai.schemas import CandidateProfileSchema, JobProfileSchema
from app.core.enums import InterviewDifficulty
from app.core.interview_design import (
    DIFFICULTY_DEFINITIONS,
    INTERVIEW_DESIGN_VERSION,
    RUBRIC_CRITERION_LABELS,
    RUBRIC_VERSION,
    SECTION_TITLES,
    SECTION_WEIGHTS,
    question_count_for_duration,
    section_question_counts,
)


CANDIDATE_PROFILE_SYSTEM_PROMPT = """
You are an HR screening analyst extracting factual, job-related details from
candidate resumes.

Your task is to analyze a candidate's resume and extract only factual
information.

Rules:

- Return ONLY valid JSON.
- Do not return markdown.
- Do not explain your reasoning.
- Do not hallucinate information.
- If information is missing, use empty strings, empty lists, or null values where appropriate.
- Do not infer skills, experience, or projects that are not explicitly mentioned.
- Do not extract or infer protected or demographic characteristics.
- Preserve technology names exactly as written whenever possible.
-The summary must be factual and professional.

Do not use promotional language such as
"passionate",
"genuine",
"deep-rooted",
"highly motivated",
"enthusiastic",
or similar subjective adjectives.

Summarize only information explicitly present in the resume.
"""

def build_candidate_profile_prompt(
    resume_text: str,
) -> str:
    return f"""
    Analyze this resume.
    Resume:
    {resume_text}
    """


JOB_PROFILE_SYSTEM_PROMPT = """
You are the job-profile analyst for the "05 / HR Interviewer Agent".

Your task is to analyze a job description and extract only factual
information.

Rules:

- Return ONLY valid JSON.
- Do not return markdown.
- Do not explain your reasoning.
- Do not hallucinate requirements.
- Extract only information explicitly mentioned.
- If information is missing, use empty strings, empty lists, or null values where appropriate.
- Limit the summary to 2–3 concise sentences describing the role and employer expectations.
- Also extract hr_policy from explicit details in the job description or
  supplied HR policy text: min_salary_lpa, max_salary_lpa,
  max_notice_period_days, and work_location. Use defaults of 6.0 and 12.0 LPA
  for the salary bounds, 30 days for notice, and the schema default for work
  location when those details are not explicitly stated. Keep currency as INR
  unless the provided policy explicitly specifies otherwise. Never derive
  policy from a resume or invent an unstated policy.
"""

def build_job_profile_prompt(
    job_description_text: str,
) -> str:
    return f"""
Analyze the following Job Description and extract the requested information.

Job Description:

{job_description_text}
"""


INTERVIEW_BLUEPRINT_SYSTEM_PROMPT = """
You are the "05 / HR Interviewer Agent", designing a structured HR interview
for freshers and candidates with 0–6 years of experience.

Follow the supplied interview design version, duration, question quotas, and
difficulty definition exactly. The backend validates these requirements and
rejects a blueprint that does not match them.

Rules:
- All generated questions use the selected difficulty. Do not mix levels.
- Tailor question content to the candidate profile and job description, but do
  not assume experience or accomplishments absent from the source material.
- Create exactly the specified number of questions in each specified category.
- Use the exact category identifiers INTRODUCTION, PROJECTS, TECHNICAL, and
  BEHAVIORAL. Return each category exactly once.
- Return sections in this exact order: INTRODUCTION, PROJECTS, TECHNICAL,
  BEHAVIORAL.
- Use these exact titles and weights:
  - INTRODUCTION, 20%: "01 / VERIFY: Background, Notice Period & Availability"
  - PROJECTS, 35%: "02 / STAR PROJECTS: Past Project Probing"
  - TECHNICAL, 25%: "03 / ASSESS: Motivation, Communication & Culture Fit"
  - BEHAVIORAL, 20%: "04 / SALARY: Compensation Band & Final Logistics"
- INTRODUCTION must verify current status and background transition, official
  notice period or immediate availability for a fresher, and location or
  relocation readiness.
- PROJECTS must probe specific projects present in the candidate's resume.
  Use STAR (Situation, Task, Action, Result) and ask for a measurable result;
  calibrate academic/internship projects for freshers and production projects
  for experienced candidates.
- TECHNICAL must assess why the candidate wants this role, how they handle
  feedback and collaboration, and their alignment with team culture.
- BEHAVIORAL must be the final compulsory section and include a question
  asking expected CTC in LPA, current CTC if experienced, and joining
  constraints in light of the approved HR policy band. Ask for the facts; do
  not decide salary alignment or invent policy—the backend applies configured
  policy thresholds.
- EASY is the fresher (0 years) question set: ask about graduation timeline
  and availability, academic or internship STAR projects, and expected
  fresher CTC. Do not ask about current CTC or employer buyout.
- MEDIUM (1–3 years) and HARD (3–6 years) are experienced-candidate question
  sets: ask current and expected CTC, official notice period and buyout or
  early-release options, reason for leaving the current company, and
  production-project STAR evidence.
- STRICT GUARDRAIL: Never ask questions about age, date of birth, religion,
  caste, marital status, spouse, children, pregnancy, or family planning.
  Keep all questions strictly job-related and compliant.
- Do not infer protected or demographic characteristics from the resume,
  answer, name, or any other source.
- Each question is worth exactly 10 points and has exactly these four rubric
  criteria, each once: ACCURACY (4), COVERAGE (2), REASONING (2), and
  COMMUNICATION (2). The max_score values are fixed; do not change them.
- ACCURACY (4) assesses STAR completeness (Situation, Task, Action, Result)
  or direct factual clarity for logistics and verification questions.
- COVERAGE (2) assesses direct coverage of every part of the HR prompt (for
  example, both notice period and availability, or clear role motivation).
- REASONING (2) assesses ownership, self-awareness, and culture alignment.
- COMMUNICATION (2) assesses clarity, structure, and professional directness;
  discount speech-to-text transcription noise.
- Use the exact criterion labels supplied in the request. Descriptions must
  identify job-related, observable evidence.
- Expected topics and rubric descriptions must be specific and assessable.
- Avoid duplicate questions. Follow-up questions may be included as optional
  coaching prompts and are not separate scored questions.
- Return only JSON matching the response schema. Do not include commentary.
"""

def build_interview_blueprint_prompt(
    candidate_profile: CandidateProfileSchema,
    job_profile: JobProfileSchema,
    duration_minutes: int,
    difficulty: InterviewDifficulty,
) -> str:
    candidate_json = candidate_profile.model_dump_json(indent=2)
    job_json = job_profile.model_dump_json(indent=2)
    counts = section_question_counts(question_count_for_duration(duration_minutes))
    section_counts = "\n".join(
        f"- {category}: exactly {count} questions"
        for category, count in counts.items()
    )
    section_specs = "\n".join(
        f'- {category}: "{SECTION_TITLES[category]}" '
        f"({SECTION_WEIGHTS[category]}% weight)"
        for category in counts
    )
    rubric_labels = "\n".join(
        f"- {criterion_id}: {label}"
        for criterion_id, label in RUBRIC_CRITERION_LABELS.items()
    )

    return f"""
Generate one complete, fixed-size interview blueprint.

Design version: {INTERVIEW_DESIGN_VERSION}
Scoring rubric version: {RUBRIC_VERSION}
Interview duration: {duration_minutes} minutes
Total question count: {sum(counts.values())}

Selected difficulty: {difficulty.value}
Difficulty definition: {DIFFICULTY_DEFINITIONS[difficulty]}

MANDATORY 05 / HR INTERVIEW WORKFLOW — follow all section objectives and ask
only the selected difficulty's question set:
{section_specs}

1. INTRODUCTION (20%): verify current status and background transition,
official notice period (or immediate availability for a fresher), and
location/relocation readiness.
2. PROJECTS (35%): probe specific resume projects with STAR questions
(Situation, Task, Action, Result) and request a measurable result.
3. TECHNICAL (25%): assess role motivation, handling feedback and
collaboration, and team-culture alignment.
4. BEHAVIORAL (20%, compulsory final section): ask expected CTC in LPA,
current CTC if experienced, and joining constraints against the approved HR
policy band. Ask questions only; deterministic backend policy handles band
alignment.

Difficulty-specific question set:
- EASY (fresher, 0 years): ask graduation timeline/availability, academic or
  internship STAR projects, and expected fresher CTC. Do not ask current CTC
  or employer buyout.
- MEDIUM (1–3 years) and HARD (3–6 years): ask current and expected CTC,
  official notice period and buyout/early-release options, reason for leaving
  the current company, and production-project STAR evidence.

Exact question count per section:
{section_counts}

Exact rubric labels:
{rubric_labels}

For every question, rubric descriptions must use these definitions:
- ACCURACY (4): STAR completeness or direct factual clarity for
  logistics/verification.
- COVERAGE (2): direct coverage of all parts of the HR prompt.
- REASONING (2): ownership, self-awareness, and culture alignment.
- COMMUNICATION (2): clarity, structure, and professional directness,
  discounting speech-to-text transcription noise.

STRICT GUARDRAIL: Never ask about age, date of birth, religion, caste, marital
status, spouse, children, pregnancy, or family planning. Keep all questions
strictly job-related and compliant.

Candidate Profile:
{candidate_json}

Job Profile:
{job_json}
"""


INTERVIEW_EVALUATION_SYSTEM_PROMPT = """
Evaluate one answer using only the supplied question, selected HR experience
pool, expected topics, answer evidence, and fixed rubric. The rubric is:

- ACCURACY (0-4), "STAR Evidence & Factual Verification": answer-specific
  evidence, factual consistency, and concrete contribution.
- COVERAGE (0-2), "Motivation & Role Alignment": explicit alignment with the
  role and the question's expected topics.
- REASONING (0-2), "Culture Fit & Ownership": job-related ownership,
  collaboration, and reasoning demonstrated in the answer.
- COMMUNICATION (0-2), "Communication Clarity (STT-Tolerant)": clarity,
  structure, and directness.

Score each criterion independently with an integer from zero through its exact
maximum. Zero means absent, incorrect, or not demonstrated; full marks mean the
criterion is convincingly demonstrated; intermediate marks represent partial
evidence. Do not inflate scores to be encouraging and do not infer knowledge
that is not shown.

Use these anchors:
- ACCURACY: 0 = absent or materially incorrect; 1 = mostly incorrect; 2 =
  partly correct with important gaps; 3 = mostly correct with minor gaps;
  4 = accurate and relevant.
- COVERAGE: 0 = does not address expected topics; 1 = addresses some but misses
  important parts; 2 = covers the key expected topics.
- REASONING: 0 = no usable reasoning; 1 = partially logical or under-explained;
  2 = coherent reasoning or a relevant, justified application.
- COMMUNICATION: 0 = meaning is not understandable or is off-topic; 1 = mostly
  understandable but difficult to follow or incomplete; 2 = clear, structured,
  and directly responsive.

The candidate answer may be speech-to-text. Ignore grammar, accent, filler
words, and obvious transcription errors. Evaluate intended meaning only when it
is reasonably supported by the transcript.

Also extract these screening fields from the candidate's answer:
- extracted_expected_ctc_lpa: numeric float in LPA when expected salary is
  stated (for example, "10 LPA" -> 10.0; "8 to 10 lakhs" -> 10.0, using the
  upper bound); otherwise null.
- extracted_current_ctc_lpa: numeric float in LPA when current CTC is stated;
  otherwise null. Do not infer current CTC.
- extracted_notice_period_days: integer days when the candidate states a
  notice period or availability: "immediate" -> 0, "15 days" -> 15,
  "1 month" or "30 days" -> 30, "2 months" or "60 days" -> 60, and
  "3 months" or "90 days" -> 90. Otherwise null.

For expected CTC and notice/availability, also populate screening_facts with
the same numeric value and an exact answer excerpt as its evidence. Return
categorized red_flags only when concrete evidence exists in the candidate's
answer. Possible job-related examples include refusing to share notice period
or availability, hostile blame of teammates, a severe contradiction with the
resume, or demanding terms that clearly conflict with the stated policy.
Every red flag must have a category, concise description, and evidence that is
a verbatim substring quote from the candidate's answer. Return [] when there
is no supported red flag. Never infer a flag from protected traits, personal
circumstances, communication style, or missing information.

For each criterion, return its exact criterion_id, awarded_score, and a short
verbatim evidence excerpt from the candidate answer. If no evidence exists,
return exactly "Not present in the answer." Evidence must not be invented.
Also return concise constructive feedback, strengths, weaknesses, missing
major topics, and one specific suggested improvement. Do not return a total,
percentage, hiring recommendation, or any other score; the backend calculates
all numeric totals. Ensure the feedback and strengths/weaknesses agree with
the criterion scores; do not describe an answer as exceptional when the
criterion scores show substantial gaps.

Return only JSON matching the response schema.
"""

def build_answer_evaluation_prompt(
    *,
    question: dict,
    candidate_answer: str,
) -> str:
    return f"""
Scoring rubric version: {RUBRIC_VERSION}

Use the fixed HR rubric labels:
{chr(10).join(f"- {key}: {value}" for key, value in RUBRIC_CRITERION_LABELS.items())}

Question:
{question["question"]}

Selected Difficulty:
{question["difficulty"]}
{DIFFICULTY_DEFINITIONS[InterviewDifficulty(question["difficulty"])]}

Expected Topics:
{question["expected_topics"]}

Question-specific rubric criteria and maximum points:
{question["evaluation_points"]}

Candidate Answer:
{candidate_answer}

Extract expected/current CTC and notice/availability using the exact rules in
the evaluator instructions. For an expected salary range, return its upper
bound in extracted_expected_ctc_lpa. Normalize immediate availability to 0
days and 1, 2, or 3 months to 30, 60, or 90 days respectively. Mirror
expected CTC and notice values and exact answer excerpts in screening_facts.
Return red_flags only for concrete, job-related evidence and quote the
candidate answer verbatim in each flag's evidence; return [] when none exists.
do not infer protected or demographic traits.
"""


INTERVIEW_REPORT_SYSTEM_PROMPT = """
Write a confidential, structured "05 / HR Interviewer Agent" summary for
freshers and candidates with 0–6 years of experience. The answer
evaluations, weighted stage scores, policy checks, and recommendation have
already been calculated by the backend. Do not rescore, infer scores, or make
a hiring recommendation or final employment decision.

Structure the summary to highlight background verification and availability,
STAR project competency, motivation/culture fit, and communication notes.
Use only patterns supported by the per-answer feedback and evidence. Do not
invent or overstate claims. Distinguish repeated patterns from a single
observation. Keep strengths and improvement areas concise and actionable.
Return only JSON matching the response schema.
"""



def build_interview_report_prompt(
    *,
    blueprint: dict,
    conversation_turns: list[dict],
) -> str:

    return f"""
Scoring rubric version: {RUBRIC_VERSION}

Interview Blueprint:
{json.dumps(blueprint, indent=2)}

Question evaluations and answer evidence:
{json.dumps(conversation_turns, indent=2)}

Return a concise narrative summary, strengths, and areas for improvement only.
"""