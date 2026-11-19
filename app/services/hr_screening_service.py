from app.core.interview_design import (
    band_lookup_tool,
    evaluate_human_checkpoint,
)


def build_hr_screening_result(
    evaluated_answers: list[dict],
    *,
    min_band_lpa: float | None,
    max_band_lpa: float | None,
    max_notice_days: int,
) -> dict[str, object]:
    if (min_band_lpa is None) != (max_band_lpa is None):
        raise ValueError("Both approved salary band bounds must be configured together.")

    expected_ctc_lpa = None
    current_ctc_lpa = None
    salary_evidence = None
    stated_notice_days = None
    notice_evidence = None
    red_flags = []

    for answer in reversed(evaluated_answers):
        evaluation = answer.get("evaluation")
        if not isinstance(evaluation, dict):
            raise ValueError("Every screening answer must include an evaluation.")
        facts = evaluation.get("screening_facts") or {}
        if not isinstance(facts, dict):
            raise ValueError("Screening facts must be an object.")
        expected_value = evaluation.get("extracted_expected_ctc_lpa")
        if expected_value is None:
            expected_value = facts.get("expected_ctc_lpa")
        notice_value = evaluation.get("extracted_notice_period_days")
        if notice_value is None:
            notice_value = facts.get("stated_notice_days")
        if expected_ctc_lpa is None and expected_value is not None:
            expected_ctc_lpa = expected_value
            salary_evidence = facts.get("salary_evidence")
        if current_ctc_lpa is None:
            current_ctc_lpa = evaluation.get("extracted_current_ctc_lpa")
        if stated_notice_days is None and notice_value is not None:
            stated_notice_days = notice_value
            notice_evidence = facts.get("notice_evidence")

    for answer in evaluated_answers:
        evaluation = answer.get("evaluation")
        if not isinstance(evaluation, dict):
            raise ValueError("Every screening answer must include an evaluation.")
        facts = evaluation.get("screening_facts") or {}
        if not isinstance(facts, dict):
            raise ValueError("Screening facts must be an object.")
        raw_flags = evaluation.get("red_flags") or facts.get("red_flags", [])
        if not isinstance(raw_flags, list):
            raise ValueError("Screening red flags must be a list.")
        for flag in raw_flags:
            if not isinstance(flag, dict):
                raise ValueError("Evidence-backed red flags must be objects.")
            category = flag.get("category", "SCREENING_CONCERN")
            if (
                not isinstance(category, str)
                or not category.strip()
                or not flag.get("description")
                or not flag.get("evidence")
            ):
                raise ValueError(
                    "Every red flag must include a category, description, and evidence."
                )
            red_flags.append({
                "turn_number": answer.get("turn_number"),
                "section_title": answer.get("section_title"),
                "category": category,
                "description": flag["description"],
                "evidence": flag["evidence"],
            })

    policy_configured = min_band_lpa is not None and max_band_lpa is not None
    if min_band_lpa is not None and max_band_lpa is not None:
        alignment = band_lookup_tool(
            expected_ctc_lpa=expected_ctc_lpa,
            min_band_lpa=min_band_lpa,
            max_band_lpa=max_band_lpa,
            stated_notice_days=stated_notice_days,
            max_notice_days=max_notice_days,
        )
        salary_alignment_status = alignment["salary_alignment_status"]
        notice_alignment_status = alignment["notice_alignment_status"]
    else:
        notice_alignment_status = (
            "NOT_DISCLOSED"
            if stated_notice_days is None
            else "EXCEEDS_POLICY"
            if stated_notice_days > max_notice_days
            else "ALIGNED"
        )
        alignment = {
            "approved_min_lpa": None,
            "approved_max_lpa": None,
            "candidate_expected_lpa": expected_ctc_lpa,
            "candidate_current_ctc_lpa": current_ctc_lpa,
            "salary_alignment_status": "NOT_CONFIGURED",
            "max_notice_days": max_notice_days,
            "candidate_notice_days": stated_notice_days,
            "notice_alignment_status": notice_alignment_status,
        }
        salary_alignment_status = "NOT_CONFIGURED"

    alignment["candidate_current_ctc_lpa"] = current_ctc_lpa
    checkpoint = evaluate_human_checkpoint(
        salary_alignment_status=salary_alignment_status,
        notice_alignment_status=notice_alignment_status,
        red_flags=red_flags,
    )
    return {
        **alignment,
        "salary_evidence": salary_evidence,
        "notice_evidence": notice_evidence,
        "policy_configured": policy_configured,
        "red_flags": red_flags,
        **checkpoint,
    }
