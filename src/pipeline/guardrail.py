"""
Guardrail checks for reply drafts.
Validates replies for hallucinations, missing citations, and policy compliance.
"""

import re
from ..schemas import ReplyDraft, KBHit, GuardrailStatus
from ..llm_client import LLMProvider, MockProvider


guardrail_system_prompt = """You are a quality assurance system for customer support replies.

Your job is to check draft replies for:
1. Hallucinated claims not supported by the provided KB passages
2. Missing citations for policy/procedure statements
3. Inappropriate commitments or guarantees
4. Potential PII exposure
5. Tone and professionalism issues

Be strict but fair. Flag issues that could cause problems, but don't flag minor style preferences."""

guardrail_user_prompt_template = """Review this draft customer reply for issues.

DRAFT REPLY:
{customer_reply}

AVAILABLE KB PASSAGES:
{kb_passages}

CITATIONS USED:
{citations}

Check for:
1. Claims about policies, pricing, or procedures not supported by KB
2. Guarantees or commitments that shouldn't be made
3. Missing citations where claims are made
4. Any fabricated information
5. Inappropriate tone or content

Respond with JSON:
{{
    "passed": true/false,
    "issues_found": ["list of specific issues found"],
    "fixes_applied": ["list of fixes that should be applied"],
    "severity": "none|low|medium|high"
}}

If no issues found, return passed=true with empty arrays."""


def check_guardrails(
    reply: ReplyDraft,
    kb_hits: list[KBHit],
    llm: LLMProvider
) -> GuardrailStatus:
    """
    Run guardrail checks on a draft reply.
    
    Args:
        reply: The draft reply to check
        kb_hits: KB passages that were available
        llm: LLM provider instance
    
    Returns:
        GuardrailStatus with pass/fail and issues
    """
    # Use mock provider's specialized method if available
    if isinstance(llm, MockProvider):
        return llm.mock_guardrail(reply, kb_hits)
    
    # Run rule-based checks first
    rule_issues = _run_rule_based_checks(reply, kb_hits)
    
    # Run LLM-based checks
    try:
        llm_result = _run_llm_checks(reply, kb_hits, llm)
    except Exception as e:
        print(f"Warning: LLM guardrail check failed: {e}")
        llm_result = GuardrailStatus(passed=True, issues_found=[], fixes_applied=[])
    
    # Combine results
    all_issues = rule_issues + llm_result.issues_found
    all_fixes = llm_result.fixes_applied
    
    # Determine overall pass/fail
    # Fail if any high-severity issues or multiple medium issues
    passed = len(all_issues) == 0 or (
        len(all_issues) <= 2 and 
        not any("guarantee" in issue.lower() or "fabricat" in issue.lower() for issue in all_issues)
    )
    
    return GuardrailStatus(
        passed=passed,
        issues_found=all_issues,
        fixes_applied=all_fixes
    )


def _run_rule_based_checks(reply: ReplyDraft, kb_hits: list[KBHit]) -> list[str]:
    """Run deterministic rule-based checks."""
    issues = []
    reply_lower = reply.customer_reply.lower()
    
    # Check for absolute guarantees
    guarantee_patterns = [
        r"\bguarantee\b",
        r"\b100%\b",
        r"\balways will\b",
        r"\bnever fail\b",
        r"\bdefinitely will\b",
        r"\bpromise\b(?! to look| to review| to investigate)",
    ]
    for pattern in guarantee_patterns:
        if re.search(pattern, reply_lower):
            issues.append(f"Contains potentially problematic guarantee language: '{pattern}'")
    
    # Check for pricing/discount claims without citation
    pricing_patterns = [
        r"\$\d+",
        r"\d+%\s*(?:off|discount)",
        r"free\s+(?:month|trial|upgrade)",
        r"refund\s+(?:of|for)\s+\$?\d+",
    ]
    for pattern in pricing_patterns:
        if re.search(pattern, reply_lower):
            # Check if there's a citation nearby
            if not reply.citations:
                issues.append(f"Pricing/discount claim without KB citation: '{pattern}'")
    
    # Check for timeline commitments
    timeline_patterns = [
        r"will be (?:fixed|resolved|completed) (?:by|within|in) \d+",
        r"(?:fix|resolve|complete) (?:by|within|in) \d+",
    ]
    for pattern in timeline_patterns:
        if re.search(pattern, reply_lower):
            issues.append(f"Specific timeline commitment may need verification: '{pattern}'")
    
    # Check for claims about "our policy" without citation
    policy_patterns = [
        r"our policy (?:is|states|requires)",
        r"per our (?:policy|terms|agreement)",
        r"according to our (?:policy|guidelines)",
    ]
    for pattern in policy_patterns:
        match = re.search(pattern, reply_lower)
        if match and not reply.citations:
            issues.append(f"Policy claim without citation: '{match.group()}'")
    
    # Check for potential PII
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails_in_reply = re.findall(email_pattern, reply.customer_reply)
    # Filter out generic support emails
    suspicious_emails = [e for e in emails_in_reply if not any(
        safe in e.lower() for safe in ["support@", "help@", "billing@", "security@", "example.com"]
    )]
    if suspicious_emails:
        issues.append(f"Potential customer email in reply: {suspicious_emails}")
    
    # Check for missing citation when KB hits exist but none cited
    if kb_hits and not reply.citations:
        issues.append("KB passages available but no citations included in reply")
    
    return issues


def _run_llm_checks(
    reply: ReplyDraft,
    kb_hits: list[KBHit],
    llm: LLMProvider
) -> GuardrailStatus:
    """Run LLM-based semantic checks."""
    
    # Format KB passages
    kb_passages = "\n\n".join([
        f"[{hit.citation}]: {hit.passage[:200]}..."
        for hit in kb_hits[:5]
    ]) if kb_hits else "No KB passages provided"
    
    # Format citations
    citations = ", ".join(reply.citations) if reply.citations else "None"
    
    prompt = guardrail_user_prompt_template.format(
        customer_reply=reply.customer_reply,
        kb_passages=kb_passages,
        citations=citations
    )
    
    response = llm.complete_json(prompt, guardrail_system_prompt)
    
    return GuardrailStatus(
        passed=response.get("passed", True),
        issues_found=response.get("issues_found", []),
        fixes_applied=response.get("fixes_applied", [])
    )


def apply_fixes(reply: ReplyDraft, guardrail: GuardrailStatus) -> ReplyDraft:
    """
    Apply suggested fixes to a reply.
    Currently returns the original reply - fixes would need manual review.
    
    In production, this could:
    1. Remove problematic phrases
    2. Add missing citations
    3. Soften guarantee language
    """
    # For now, just return original - fixes require human review
    # In production, could implement automatic safe fixes
    return reply

