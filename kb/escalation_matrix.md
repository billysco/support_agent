# Escalation Matrix

## Overview

This document defines when and how to escalate support issues for faster resolution.

## Escalation Criteria

### Automatic Escalation Triggers

Issues are automatically escalated when:

1. **SLA Breach**: Response or resolution time exceeds SLA
2. **Enterprise P0**: Any P0 from Enterprise customer
3. **Security Flag**: Security-related keywords detected
4. **Revenue Impact**: Customer reports revenue loss
5. **Repeated Contact**: Same issue reported 3+ times

### Manual Escalation Triggers

Request escalation when:

1. Issue blocking critical business process
2. Workaround not acceptable for business needs
3. Disagreement with priority assignment
4. Need executive visibility
5. Regulatory or compliance implications

## Escalation Levels

### Level 1: Support Team Lead

**When**: Initial escalation, SLA concerns  
**Response Time**: 1 hour  
**Authority**: 
- Reprioritize tickets
- Assign additional resources
- Approve standard workarounds

### Level 2: Engineering Manager

**When**: Technical complexity, resource needs  
**Response Time**: 2 hours  
**Authority**:
- Pull engineers from other work
- Approve emergency deployments
- Coordinate cross-team efforts

### Level 3: Director of Support/Engineering

**When**: Customer satisfaction risk, extended outages  
**Response Time**: 4 hours  
**Authority**:
- Approve service credits
- Direct customer communication
- Engage vendor support

### Level 4: VP/C-Level

**When**: Major incidents, legal/PR implications  
**Response Time**: Immediate  
**Authority**:
- All decisions
- External communications
- Contract modifications

## Escalation by Customer Tier

### Enterprise Customers

| Situation | Escalation Level | Timeline |
|-----------|------------------|----------|
| P0 Outage | Level 3 | Immediate |
| P1 Not Resolved in 4hr | Level 2 | 4 hours |
| Any SLA Breach | Level 2 | At breach |
| Customer Requests | Level 2 | 1 hour |

### Professional Customers

| Situation | Escalation Level | Timeline |
|-----------|------------------|----------|
| P0 Outage | Level 2 | 1 hour |
| P1 Not Resolved in 8hr | Level 2 | 8 hours |
| SLA Breach | Level 1 | At breach |
| Customer Requests | Level 1 | 4 hours |

### Starter Customers

| Situation | Escalation Level | Timeline |
|-----------|------------------|----------|
| P0 Outage | Level 1 | 2 hours |
| Repeated Issues | Level 1 | On 3rd report |
| SLA Breach | Level 1 | At breach |

## How to Escalate

### For Customers

1. **Reply to ticket** with "ESCALATE" in subject
2. **Call support line** (Enterprise only)
3. **Contact account manager** (Enterprise only)
4. **Use emergency contact** for P0 security issues

### For Support Agents

1. Update ticket with escalation reason
2. Tag appropriate escalation level
3. Notify via Slack #escalations channel
4. Brief incoming escalation owner
5. Remain engaged until handoff complete

## Escalation Communication

### Internal Notification Template

```
ESCALATION: [Level X]
Ticket: [ID]
Customer: [Name] ([Tier])
Issue: [Brief description]
Reason: [Why escalating]
Current Status: [What's been tried]
Needed: [What we need to resolve]
```

### Customer Communication

When escalating, inform the customer:
- Their issue has been escalated
- Who is now handling it
- Expected next update time
- Any interim workarounds

## De-escalation

### When to De-escalate

- Issue resolved
- Customer confirms acceptable workaround
- Priority reassessed and lowered
- Customer withdraws escalation request

### De-escalation Process

1. Confirm resolution with customer
2. Update ticket status
3. Notify escalation chain
4. Document lessons learned
5. Close escalation tracking

## Metrics and Review

### Escalation Metrics Tracked

- Escalation rate by tier
- Time to escalation resolution
- Escalation reasons distribution
- Customer satisfaction post-escalation

### Weekly Review

- All escalations reviewed in weekly support meeting
- Patterns identified for process improvement
- Training needs assessed
- Documentation gaps addressed



