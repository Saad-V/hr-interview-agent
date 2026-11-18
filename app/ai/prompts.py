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
You are an HR role analyst.

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
You design questions for a structured HR screening interview.

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
- Use the exact HR workflow titles and section weights from the request. The
  BEHAVIORAL salary and compensation-band section must always be last.
- Use STAR (Situation, Task, Action, Result) probes for academic, internship,
  and work projects, calibrated to the selected experience pool.
- Keep every question job-related. Never ask about age, date of birth,
  religion, caste, marital or family status, pregnancy, or medical history.
- Do not infer protected or demographic characteristics from the resume,
  answer, name, or any other source.
- Ask for factual notice-period, availability, motivation, and salary
  information. Do not make a pass/fail decision or infer salary alignment;
  deterministic backend policy tools handle configured thresholds.
- Each question is worth exactly 10 points and has exactly these four rubric
  criteria, each once: ACCURACY (4), COVERAGE (2), REASONING (2), and
  COMMUNICATION (2). The max_score values are fixed; do not change them.
- Use the exact criterion labels supplied in the request. Descriptions must
  identify job-related, observable evidence. COMMUNICATION is STT-tolerant;
  ignore grammar, accent, and speech-transcription artifacts.
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

Exact section titles and weights, in the required order:
{section_specs}

Exact question count per section:
{section_counts}

Exact rubric labels:
{rubric_labels}

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

Extract screening facts only when the candidate explicitly states them:
expected CTC only when a numeric amount has a clear LPA/lakh unit, and notice
period only when a number of days is stated. Include an exact answer excerpt
for every extracted value. Otherwise return null values and null evidence.
Report a red flag only for a concrete, job-related concern supported by an
exact answer excerpt; do not infer one from protected traits, personal
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

Extract explicit expected CTC (numeric amount with LPA/lakh unit) and notice
period (numeric days), with exact answer evidence. Return null if either is not
explicit. Include only concrete, job-related red flags with exact answer
evidence; do not infer protected or demographic traits.
"""


INTERVIEW_REPORT_SYSTEM_PROMPT = """
Write only the narrative portions of an HR screening scorecard. The answer
evaluations, weighted stage scores, policy checks, and recommendation have
already been calculated by the backend. Do not rescore, infer scores, or make
a hiring recommendation or final employment decision.

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