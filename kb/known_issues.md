# Known Issues

## Overview

This page lists currently known issues and their workarounds. Subscribe to issues for updates.

## Active Issues

### API-2024-001: Intermittent 504 Timeouts on Large Exports

**Status**: In Progress  
**Severity**: Medium  
**Affected**: All tiers  
**First Reported**: 2024-01-10

**Description**:
Large data exports (>100MB) may occasionally timeout with a 504 error.

**Workaround**:
- Break exports into smaller chunks using pagination
- Use the async export endpoint for large datasets
- Retry with exponential backoff

**Expected Resolution**: 2024-02-01

---

### API-2024-002: Dashboard Slow Loading with Many Projects

**Status**: Investigating  
**Severity**: Low  
**Affected**: Professional, Enterprise  
**First Reported**: 2024-01-12

**Description**:
Accounts with more than 50 projects may experience slow dashboard loading times (>5 seconds).

**Workaround**:
- Use project filtering to reduce displayed projects
- Access projects directly via bookmarks
- Use API for programmatic access

**Expected Resolution**: 2024-02-15

---

### API-2024-003: Webhook Delivery Delays During Peak Hours

**Status**: Monitoring  
**Severity**: Medium  
**Affected**: All tiers  
**First Reported**: 2024-01-08

**Description**:
Webhook deliveries may be delayed by up to 5 minutes during peak usage hours (9am-11am PT, 2pm-4pm PT).

**Workaround**:
- Implement idempotency in webhook handlers
- Use polling as backup for critical workflows
- Consider async processing of webhook events

**Expected Resolution**: 2024-01-25

---

## Recently Resolved

### API-2023-089: Authentication Failures After Password Reset

**Status**: Resolved  
**Resolved Date**: 2024-01-05

**Description**:
Users were unable to log in for up to 10 minutes after resetting their password.

**Resolution**:
Fixed cache invalidation issue in authentication service.

---

### API-2023-088: Incorrect Usage Metrics in Dashboard

**Status**: Resolved  
**Resolved Date**: 2024-01-03

**Description**:
Usage metrics displayed in dashboard were showing values from previous billing cycle.

**Resolution**:
Corrected date range calculation in metrics aggregation.

---

## Reporting New Issues

If you encounter an issue not listed here:

1. Check our status page: status.example.com
2. Search existing support tickets
3. Submit a new bug report with:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details
   - Screenshots if applicable

## Subscribing to Updates

To receive updates on known issues:

1. Log into your dashboard
2. Navigate to Settings > Notifications
3. Enable "Known Issues Updates"
4. Select severity levels to follow

## Issue Severity Definitions

| Severity | Definition |
|----------|------------|
| Critical | Service unusable, no workaround |
| High | Major feature broken, limited workaround |
| Medium | Feature impaired, workaround available |
| Low | Minor inconvenience, cosmetic issues |

