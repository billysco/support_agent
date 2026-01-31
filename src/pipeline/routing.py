"""
Routing logic for support tickets.
Determines team assignment, SLA, and escalation based on triage and account tier.
"""

from ..schemas import (
    TriageResult, RoutingDecision, AccountTier, Team, Urgency, Category
)


# SLA matrix: (account_tier, urgency) -> hours
sla_matrix = {
    # Enterprise tier
    (AccountTier.enterprise, Urgency.p0): 1,
    (AccountTier.enterprise, Urgency.p1): 4,
    (AccountTier.enterprise, Urgency.p2): 24,
    (AccountTier.enterprise, Urgency.p3): 72,
    
    # Professional tier
    (AccountTier.professional, Urgency.p0): 4,
    (AccountTier.professional, Urgency.p1): 8,
    (AccountTier.professional, Urgency.p2): 48,
    (AccountTier.professional, Urgency.p3): 120,
    
    # Starter tier
    (AccountTier.starter, Urgency.p0): 8,
    (AccountTier.starter, Urgency.p1): 24,
    (AccountTier.starter, Urgency.p2): 72,
    (AccountTier.starter, Urgency.p3): 168,
    
    # Free tier
    (AccountTier.free, Urgency.p0): 24,
    (AccountTier.free, Urgency.p1): 48,
    (AccountTier.free, Urgency.p2): 168,
    (AccountTier.free, Urgency.p3): 336,
}


# Category to team mapping
category_team_map = {
    Category.billing: Team.billing,
    Category.bug: Team.engineering,
    Category.outage: Team.engineering,
    Category.feature_request: Team.customer_success,
    Category.security: Team.security,
    Category.onboarding: Team.customer_success,
    Category.other: Team.support,
}


def compute_routing(
    triage: TriageResult,
    account_tier: AccountTier
) -> RoutingDecision:
    """
    Compute routing decision based on triage results and account tier.
    
    Args:
        triage: Triage classification results
        account_tier: Customer's account tier
    
    Returns:
        RoutingDecision with team, SLA, and escalation info
    """
    # Determine team based on category
    team = category_team_map.get(triage.category, Team.support)
    
    # Override for critical issues
    if triage.urgency == Urgency.p0:
        if triage.category == Category.security:
            team = Team.security
        elif triage.category in [Category.outage, Category.bug]:
            team = Team.engineering
    
    # Calculate SLA
    sla_hours = sla_matrix.get(
        (account_tier, triage.urgency),
        72  # Default to 72 hours
    )
    
    # Determine escalation
    escalation = _should_escalate(triage, account_tier)
    
    # Build reasoning
    reasoning = _build_routing_reasoning(triage, account_tier, team, escalation)
    
    return RoutingDecision(
        team=team,
        sla_hours=sla_hours,
        escalation=escalation,
        reasoning=reasoning
    )


def _should_escalate(triage: TriageResult, account_tier: AccountTier) -> bool:
    """
    Determine if a ticket should be escalated.
    
    Escalation criteria:
    - P0 for any tier
    - P1 for Enterprise
    - Security issues for Enterprise/Professional
    - Negative sentiment + P1/P2 for Enterprise
    """
    # Always escalate P0
    if triage.urgency == Urgency.p0:
        return True
    
    # Escalate P1 for Enterprise
    if triage.urgency == Urgency.p1 and account_tier == AccountTier.enterprise:
        return True
    
    # Escalate security issues for higher tiers
    if triage.category == Category.security:
        if account_tier in [AccountTier.enterprise, AccountTier.professional]:
            return True
    
    # Escalate negative sentiment + high urgency for Enterprise
    if account_tier == AccountTier.enterprise:
        if triage.sentiment.value == "negative" and triage.urgency in [Urgency.p1, Urgency.p2]:
            return True
    
    return False


def _build_routing_reasoning(
    triage: TriageResult,
    account_tier: AccountTier,
    team: Team,
    escalation: bool
) -> str:
    """Build human-readable reasoning for the routing decision."""
    
    reasons = []
    
    # Team assignment reason
    team_reasons = {
        Team.engineering: f"Routed to engineering due to {triage.category.value} classification",
        Team.billing: "Routed to billing team for invoice/payment handling",
        Team.security: "Routed to security team for security-related concern",
        Team.customer_success: f"Routed to customer success for {triage.category.value}",
        Team.support: "Routed to general support for initial handling",
    }
    reasons.append(team_reasons.get(team, f"Routed to {team.value}"))
    
    # SLA reason
    reasons.append(f"SLA set based on {account_tier.value} tier and {triage.urgency.value} priority")
    
    # Escalation reason
    if escalation:
        if triage.urgency == Urgency.p0:
            reasons.append("Escalated due to P0 critical priority")
        elif account_tier == AccountTier.enterprise:
            reasons.append("Escalated per enterprise account policy")
        elif triage.category == Category.security:
            reasons.append("Escalated due to security classification")
    
    return ". ".join(reasons) + "."


def get_sla_description(sla_hours: int) -> str:
    """Convert SLA hours to human-readable description."""
    if sla_hours <= 1:
        return "1 hour"
    elif sla_hours < 24:
        return f"{sla_hours} hours"
    elif sla_hours == 24:
        return "24 hours (1 day)"
    elif sla_hours < 168:
        days = sla_hours // 24
        return f"{sla_hours} hours ({days} days)"
    else:
        weeks = sla_hours // 168
        return f"{sla_hours} hours ({weeks} week{'s' if weeks > 1 else ''})"


