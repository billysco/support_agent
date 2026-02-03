# Onboarding Guide

## Overview

Welcome! This guide will help you get started with our platform quickly and successfully.

## Getting Started

### Account Setup

1. **Verify your email**: Click the link in your welcome email
2. **Set your password**: Create a strong password following our requirements
3. **Enable MFA**: Recommended for all accounts, required for Enterprise
4. **Complete your profile**: Add your name and contact information

### Organization Setup

1. **Name your organization**: This appears in your dashboard and invoices
2. **Invite team members**: Add colleagues who need access
3. **Set up roles**: Assign Admin, Developer, or Viewer roles
4. **Configure SSO**: Enterprise accounts can enable SAML/OIDC

## API Integration

### Getting Your API Key

1. Navigate to Settings > API Keys
2. Click "Create New Key"
3. Name your key (e.g., "Production", "Development")
4. Copy the key immediately - it won't be shown again
5. Store securely in environment variables

### First API Call

```bash
curl -X GET "https://api.example.com/v1/status" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### SDK Installation

**Python**:
```bash
pip install example-sdk
```

**Node.js**:
```bash
npm install @example/sdk
```

**Go**:
```bash
go get github.com/example/sdk-go
```

## Common Setup Tasks

### Webhooks Configuration

1. Go to Settings > Webhooks
2. Add your endpoint URL
3. Select events to subscribe to
4. Save and test with a sample event

### Environment Configuration

We recommend separate API keys for:
- Development (local testing)
- Staging (pre-production testing)
- Production (live traffic)

### Rate Limits

| Tier | Requests/minute | Burst |
|------|-----------------|-------|
| Starter | 100 | 150 |
| Professional | 1,000 | 1,500 |
| Enterprise | Custom | Custom |

## Troubleshooting

### Common Issues

**"Invalid API Key" error**:
- Verify key is copied correctly (no extra spaces)
- Check key hasn't been revoked
- Ensure using correct environment's key

**"Rate Limited" error**:
- Implement exponential backoff
- Check your current usage in dashboard
- Consider upgrading tier if consistently hitting limits

**"Permission Denied" error**:
- Verify your role has required permissions
- Check API key scope includes needed endpoints
- Contact admin to adjust permissions

## Getting Help

### Support Channels

- **Documentation**: docs.example.com
- **Community Forum**: community.example.com
- **Email Support**: support@example.com
- **Enterprise Slack**: Available for Enterprise tier

### Office Hours

We host weekly office hours for new customers:
- Tuesdays at 10am PT
- Thursdays at 2pm PT
- Register at example.com/office-hours

## Next Steps

After completing setup:

1. Review our API documentation
2. Try the interactive API explorer
3. Join our developer community
4. Schedule an onboarding call (Professional/Enterprise)



