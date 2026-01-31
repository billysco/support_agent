# Bug Reporting and Handling

## Overview

This document describes how we handle bug reports from initial submission through resolution.

## Submitting a Bug Report

### Required Information

For fastest resolution, please include:

1. **Environment**: Production, staging, or development
2. **Steps to reproduce**: Detailed sequence of actions
3. **Expected behavior**: What should happen
4. **Actual behavior**: What actually happens
5. **Error messages**: Full text of any errors
6. **Screenshots/recordings**: Visual evidence if applicable
7. **Browser/OS**: For frontend issues
8. **API version**: For API-related bugs

### Optional but Helpful

- Account ID or organization name
- Timestamp of when issue occurred
- Frequency (always, sometimes, once)
- Workarounds discovered

## Triage Process

### Initial Assessment

All bug reports are triaged within:
- 4 hours for Enterprise customers
- 8 hours for Professional customers
- 24 hours for Starter customers

### Severity Assignment

| Severity | Criteria | Response SLA |
|----------|----------|--------------|
| Critical | Production down, data loss | 1 hour |
| High | Major feature broken, no workaround | 4 hours |
| Medium | Feature impaired, workaround exists | 24 hours |
| Low | Minor issue, cosmetic | 72 hours |

## Bug Lifecycle

### Status Definitions

- **New**: Just submitted, awaiting triage
- **Triaged**: Severity assigned, in queue
- **In Progress**: Engineer actively working
- **In Review**: Fix ready, awaiting code review
- **Testing**: Fix deployed to staging
- **Resolved**: Fix deployed to production
- **Closed**: Verified by customer or auto-closed

### Resolution Types

- **Fixed**: Bug corrected in code
- **By Design**: Behavior is intentional
- **Cannot Reproduce**: Unable to replicate issue
- **Duplicate**: Same as existing bug
- **Won't Fix**: Not planned for resolution

## Communication

### Update Frequency

- Critical bugs: Every 2 hours until resolved
- High bugs: Daily updates
- Medium/Low bugs: Weekly updates or on status change

### Notification Channels

- Email to ticket submitter
- In-app notification
- Slack integration (Enterprise)

## Known Issues

### Checking Known Issues

Before submitting a bug, please check our known issues page. If your issue is listed, you can subscribe for updates.

### Workarounds

When available, workarounds are documented in the known issues list. We recommend using workarounds while awaiting permanent fixes.

## Escalation

### When to Escalate

- Bug blocking critical business process
- No response within SLA
- Disagreement with severity assignment
- Security implications discovered

### How to Escalate

Contact your account manager (Enterprise) or reply to the ticket with "ESCALATE" in the subject line.


