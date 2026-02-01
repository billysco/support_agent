/**
 * SupportHub - Zendesk-style Support Ticket System
 */

// State management
const state = {
    tickets: [],
    currentTicket: null,
    currentResult: null,
    mode: 'unknown',
    kbSearchTimeout: null
};

// DOM Elements
const elements = {
    // Navigation
    navItems: document.querySelectorAll('.nav-item'),
    modeIndicator: document.getElementById('modeIndicator'),
    
    // Views
    viewTickets: document.getElementById('viewTickets'),
    viewCreate: document.getElementById('viewCreate'),
    viewDetail: document.getElementById('viewDetail'),
    viewKb: document.getElementById('viewKb'),
    viewAdmin: document.getElementById('viewAdmin'),
    
    // Tickets list
    ticketsList: document.getElementById('ticketsList'),
    ticketCount: document.getElementById('ticketCount'),
    emptyState: document.getElementById('emptyState'),
    newTicketBtn: document.getElementById('newTicketBtn'),
    emptyCreateBtn: document.getElementById('emptyCreateBtn'),
    
    // Create form
    ticketForm: document.getElementById('ticketForm'),
    backFromCreate: document.getElementById('backFromCreate'),
    cancelCreate: document.getElementById('cancelCreate'),
    submitTicket: document.getElementById('submitTicket'),
    kbSuggestions: document.getElementById('kbSuggestions'),
    suggestionsContent: document.getElementById('suggestionsContent'),
    
    // Form fields
    customerName: document.getElementById('customerName'),
    customerEmail: document.getElementById('customerEmail'),
    accountTier: document.getElementById('accountTier'),
    product: document.getElementById('product'),
    subject: document.getElementById('subject'),
    body: document.getElementById('body'),
    
    // Detail view
    backFromDetail: document.getElementById('backFromDetail'),
    detailTicketId: document.getElementById('detailTicketId'),
    detailSubject: document.getElementById('detailSubject'),
    detailUrgency: document.getElementById('detailUrgency'),
    detailCategory: document.getElementById('detailCategory'),
    detailSentiment: document.getElementById('detailSentiment'),
    detailCustomer: document.getElementById('detailCustomer'),
    detailAccount: document.getElementById('detailAccount'),
    detailTeam: document.getElementById('detailTeam'),
    detailSla: document.getElementById('detailSla'),
    detailAvatar: document.getElementById('detailAvatar'),
    detailSenderName: document.getElementById('detailSenderName'),
    detailTime: document.getElementById('detailTime'),
    detailMessageSubject: document.getElementById('detailMessageSubject'),
    detailMessageBody: document.getElementById('detailMessageBody'),
    detailFieldsGrid: document.getElementById('detailFieldsGrid'),
    
    // Agent response in conversation
    agentResponseItem: document.getElementById('agentResponseItem'),
    agentResponseBody: document.getElementById('agentResponseBody'),
    agentResponseTime: document.getElementById('agentResponseTime'),
    autoSentBadge: document.getElementById('autoSentBadge'),

    // Follow-up reply
    followUpMessages: document.getElementById('followUpMessages'),
    replyBox: document.getElementById('replyBox'),
    customerReplyInput: document.getElementById('customerReplyInput'),
    sendCustomerReply: document.getElementById('sendCustomerReply'),
    
    // Agent panel
    panelTabs: document.querySelectorAll('.panel-tab'),
    panelReasoning: document.getElementById('panelReasoning'),
    panelKb: document.getElementById('panelKb'),
    panelReply: document.getElementById('panelReply'),
    panelNotes: document.getElementById('panelNotes'),
    reasoningStages: document.getElementById('reasoningStages'),
    kbResults: document.getElementById('kbResults'),
    replyContent: document.getElementById('replyContent'),
    notesContent: document.getElementById('notesContent'),
    guardrailStatus: document.getElementById('guardrailStatus'),
    copyReply: document.getElementById('copyReply'),
    sendReply: document.getElementById('sendReply'),

    // Citation modal
    citationModal: document.getElementById('citationModal'),
    citationModalTitle: document.getElementById('citationModalTitle'),
    citationModalClose: document.getElementById('citationModalClose'),
    citationSourceLabel: document.getElementById('citationSourceLabel'),
    citationPassage: document.getElementById('citationPassage'),
    citationRelevance: document.getElementById('citationRelevance'),
    
    // KB view
    kbSearchInput: document.getElementById('kbSearchInput'),
    kbSearchResults: document.getElementById('kbSearchResults'),
    
    // Admin view
    knownIssueForm: document.getElementById('knownIssueForm'),
    clearIssueForm: document.getElementById('clearIssueForm'),
    submitIssue: document.getElementById('submitIssue'),
    issueId: document.getElementById('issueId'),
    issueTitle: document.getElementById('issueTitle'),
    issueStatus: document.getElementById('issueStatus'),
    issueSeverity: document.getElementById('issueSeverity'),
    issueAffected: document.getElementById('issueAffected'),
    issueExpectedResolution: document.getElementById('issueExpectedResolution'),
    issueDescription: document.getElementById('issueDescription'),
    issueWorkaround: document.getElementById('issueWorkaround'),
    
    // Toast
    toast: document.getElementById('toast')
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initTicketsList();
    initCreateForm();
    initDetailView();
    initKbView();
    initAdminView();
    checkMode();
    loadSampleTickets();
});

// Navigation
function initNavigation() {
    elements.navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewName) {
    // Update nav
    elements.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });
    
    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    
    switch (viewName) {
        case 'tickets':
            elements.viewTickets.classList.add('active');
            updateTicketsList();
            break;
        case 'create':
            elements.viewCreate.classList.add('active');
            resetCreateForm();
            break;
        case 'kb':
            elements.viewKb.classList.add('active');
            break;
        case 'detail':
            elements.viewDetail.classList.add('active');
            break;
        case 'admin':
            elements.viewAdmin.classList.add('active');
            break;
    }
}

// Check API mode
async function checkMode() {
    try {
        const response = await fetch('/api/mode');
        if (response.ok) {
            const data = await response.json();
            state.mode = data.mode;
            updateModeDisplay();
        }
    } catch (error) {
        console.error('Failed to check mode:', error);
    }
}

function updateModeDisplay() {
    const indicator = elements.modeIndicator;
    const label = indicator.querySelector('.mode-label');
    
    indicator.className = 'mode-indicator ' + state.mode;
    label.textContent = state.mode === 'real' ? 'Live Mode' : 'Demo Mode';
}

// Tickets List
function initTicketsList() {
    elements.newTicketBtn.addEventListener('click', () => switchView('create'));
    elements.emptyCreateBtn.addEventListener('click', () => switchView('create'));
}

function updateTicketsList() {
    const count = state.tickets.length;
    elements.ticketCount.textContent = `${count} ticket${count !== 1 ? 's' : ''}`;
    
    if (count === 0) {
        elements.ticketsList.innerHTML = '';
        elements.emptyState.classList.add('visible');
        return;
    }
    
    elements.emptyState.classList.remove('visible');
    elements.ticketsList.innerHTML = state.tickets.map(ticket => createTicketCard(ticket)).join('');
    
    // Add click handlers
    elements.ticketsList.querySelectorAll('.ticket-card').forEach(card => {
        card.addEventListener('click', () => {
            const ticketId = card.dataset.ticketId;
            openTicketDetail(ticketId);
        });
    });
}

function createTicketCard(ticket) {
    const initials = getInitials(ticket.customer_name);
    const urgencyClass = ticket.result?.triage?.urgency?.toLowerCase() || '';
    const sentimentClass = ticket.result?.triage?.sentiment?.toLowerCase() || '';
    
    return `
        <div class="ticket-card" data-ticket-id="${ticket.ticket_id}">
            <div class="ticket-card-header">
                <div class="avatar">${initials}</div>
                <div class="ticket-card-info">
                    <div class="ticket-card-subject">${escapeHtml(ticket.subject)}</div>
                    <div class="ticket-card-meta">
                        <span>${ticket.customer_name}</span>
                        <span>${formatTime(ticket.created_at)}</span>
                    </div>
                </div>
            </div>
            <div class="ticket-card-preview">${escapeHtml(truncate(ticket.body, 120))}</div>
            <div class="ticket-card-badges">
                ${ticket.result ? `
                    ${ticket.result.auto_reply?.is_auto_reply ? '<span class="badge badge-auto-reply">Auto-Reply</span>' : ''}
                    <span class="badge badge-urgency ${urgencyClass}">${ticket.result.triage.urgency}</span>
                    <span class="badge badge-category">${ticket.result.triage.category}</span>
                    <span class="badge badge-sentiment ${sentimentClass}">${ticket.result.triage.sentiment}</span>
                ` : '<span class="badge">Pending</span>'}
            </div>
        </div>
    `;
}

// Load sample tickets for demo
async function loadSampleTickets() {
    try {
        const response = await fetch('/api/samples');
        if (response.ok) {
            const samples = await response.json();
            // Add first sample as a demo ticket
            if (samples.length > 0) {
                const demoTicket = {
                    ...samples[0],
                    result: null
                };
                state.tickets = [demoTicket];
                updateTicketsList();
            }
        }
    } catch (error) {
        console.error('Failed to load samples:', error);
    }
}

// Create Form
function initCreateForm() {
    elements.backFromCreate.addEventListener('click', () => switchView('tickets'));
    elements.cancelCreate.addEventListener('click', () => switchView('tickets'));
    elements.ticketForm.addEventListener('submit', handleSubmitTicket);
    
    // Real-time KB suggestions as user types
    let debounceTimer;
    const triggerKbSearch = () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchKbSuggestions();
        }, 500);
    };
    
    elements.subject.addEventListener('input', triggerKbSearch);
    elements.body.addEventListener('input', triggerKbSearch);
}

function resetCreateForm() {
    elements.ticketForm.reset();
    elements.suggestionsContent.innerHTML = '<p class="suggestions-hint">Start typing your issue to see related help articles and known issues.</p>';
}

async function searchKbSuggestions() {
    const subject = elements.subject.value.trim();
    const body = elements.body.value.trim();
    
    if (!subject && !body) {
        elements.suggestionsContent.innerHTML = '<p class="suggestions-hint">Start typing your issue to see related help articles and known issues.</p>';
        return;
    }
    
    const query = `${subject} ${body}`.trim();
    if (query.length < 10) return;
    
    elements.suggestionsContent.innerHTML = '<div class="suggestions-loading">Searching...</div>';
    
    try {
        const response = await fetch('/api/kb/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, k: 4 })
        });
        
        if (response.ok) {
            const results = await response.json();
            displayKbSuggestions(results);
        }
    } catch (error) {
        console.error('KB search failed:', error);
        elements.suggestionsContent.innerHTML = '<p class="suggestions-hint">Unable to search knowledge base.</p>';
    }
}

function displayKbSuggestions(results) {
    if (!results || results.length === 0) {
        elements.suggestionsContent.innerHTML = '<p class="suggestions-hint">No related articles found. Your ticket will be reviewed by our support team.</p>';
        return;
    }
    
    elements.suggestionsContent.innerHTML = results.map(hit => `
        <div class="suggestion-item">
            <div class="suggestion-source">${escapeHtml(hit.doc_name)} - ${escapeHtml(hit.section)}</div>
            <div class="suggestion-text">${escapeHtml(truncate(hit.passage, 150))}</div>
        </div>
    `).join('');
}

async function handleSubmitTicket(e) {
    e.preventDefault();
    
    const submitBtn = elements.submitTicket;
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    
    // Build ticket data
    const ticket = {
        ticket_id: `TKT-${Date.now()}`,
        created_at: new Date().toISOString(),
        customer_name: elements.customerName.value.trim(),
        customer_email: elements.customerEmail.value.trim(),
        account_tier: elements.accountTier.value,
        product: elements.product.value.trim(),
        subject: elements.subject.value.trim(),
        body: elements.body.value.trim(),
        attachments: null
    };
    
    try {
        // Process ticket through the pipeline
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ticket)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to process ticket');
        }
        
        const result = await response.json();
        
        // Add to tickets list
        const newTicket = { ...ticket, result };
        state.tickets.unshift(newTicket);
        
        showToast('Ticket submitted successfully!', 'success');
        
        // Open the ticket detail view
        state.currentTicket = newTicket;
        state.currentResult = result;
        displayTicketDetail();
        switchView('detail');
        
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

// Detail View
function initDetailView() {
    elements.backFromDetail.addEventListener('click', () => switchView('tickets'));

    // Panel tabs
    elements.panelTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const panel = tab.dataset.panel;
            switchPanel(panel);
        });
    });

    // Reply actions
    elements.copyReply.addEventListener('click', copyReplyToClipboard);
    elements.sendReply.addEventListener('click', handleSendReply);

    // Citation modal
    elements.citationModalClose.addEventListener('click', closeCitationModal);
    elements.citationModal.addEventListener('click', (e) => {
        if (e.target === elements.citationModal) closeCitationModal();
    });

    // Follow-up reply
    elements.sendCustomerReply.addEventListener('click', handleCustomerFollowUp);
    elements.customerReplyInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            handleCustomerFollowUp();
        }
    });
}

function switchPanel(panelName) {
    elements.panelTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.panel === panelName);
    });

    document.querySelectorAll('.panel-content').forEach(panel => {
        panel.classList.remove('active');
    });

    switch (panelName) {
        case 'reasoning':
            elements.panelReasoning.classList.add('active');
            break;
        case 'kb':
            elements.panelKb.classList.add('active');
            break;
        case 'reply':
            elements.panelReply.classList.add('active');
            break;
        case 'notes':
            elements.panelNotes.classList.add('active');
            break;
    }
}

function openTicketDetail(ticketId) {
    const ticket = state.tickets.find(t => t.ticket_id === ticketId);
    if (!ticket) return;
    
    state.currentTicket = ticket;
    state.currentResult = ticket.result;
    
    if (!ticket.result) {
        // Process ticket if not already processed
        processTicketForDetail(ticket);
    } else {
        displayTicketDetail();
        switchView('detail');
    }
}

async function processTicketForDetail(ticket) {
    showToast('Processing ticket...', 'info');
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ticket)
        });
        
        if (!response.ok) {
            throw new Error('Failed to process ticket');
        }
        
        const result = await response.json();
        ticket.result = result;
        state.currentResult = result;
        
        displayTicketDetail();
        switchView('detail');
        
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

function displayTicketDetail() {
    const ticket = state.currentTicket;
    const result = state.currentResult;

    if (!ticket || !result) return;

    // Clear any previous follow-up messages
    elements.followUpMessages.innerHTML = '';
    elements.customerReplyInput.value = '';
    
    // Header
    elements.detailTicketId.textContent = ticket.ticket_id;
    elements.detailSubject.textContent = truncate(ticket.subject, 60);
    
    // Badges
    const urgency = result.triage.urgency;
    elements.detailUrgency.textContent = urgency;
    elements.detailUrgency.className = `badge badge-urgency ${urgency.toLowerCase()}`;
    
    elements.detailCategory.textContent = result.triage.category;
    
    const sentiment = result.triage.sentiment;
    elements.detailSentiment.textContent = sentiment;
    elements.detailSentiment.className = `badge badge-sentiment ${sentiment.toLowerCase()}`;
    
    // Meta info
    elements.detailCustomer.textContent = `${ticket.customer_name} (${ticket.customer_email})`;
    elements.detailAccount.textContent = capitalizeFirst(ticket.account_tier);
    elements.detailTeam.textContent = capitalizeFirst(result.routing.team);
    elements.detailSla.textContent = formatSla(result.routing.sla_hours);
    
    // Message
    elements.detailAvatar.textContent = getInitials(ticket.customer_name);
    elements.detailSenderName.textContent = ticket.customer_name;
    elements.detailTime.textContent = formatTime(ticket.created_at);
    elements.detailMessageSubject.textContent = ticket.subject;
    elements.detailMessageBody.textContent = ticket.body;
    
    // Extracted fields
    displayExtractedFields(result.extracted_fields);

    // Chain of thought (AI Reasoning)
    displayChainOfThought(ticket, result);

    // KB results
    displayKbResults(result.kb_hits);

    // Reply with citation highlighting
    displayReply(result);

    // Agent response in the main conversation (below customer message)
    displayAgentResponse(result);

    // Notes
    displayNotes(result);
}

function displayExtractedFields(fields) {
    const fieldItems = [
        { label: 'Environment', value: fields.environment },
        { label: 'Region', value: fields.region },
        { label: 'Error Message', value: fields.error_message },
        { label: 'Impact', value: fields.impact },
        { label: 'Order/Invoice', value: fields.order_id },
        { label: 'Requested Action', value: fields.requested_action }
    ];
    
    elements.detailFieldsGrid.innerHTML = fieldItems
        .filter(field => field.value)
        .map(field => `
            <div class="field-item">
                <div class="field-label">${field.label}</div>
                <div class="field-value">${escapeHtml(truncate(field.value, 80))}</div>
            </div>
        `).join('');
    
    if (fields.missing_fields && fields.missing_fields.length > 0) {
        elements.detailFieldsGrid.innerHTML += `
            <div class="field-item" style="grid-column: 1 / -1; background: rgba(240, 180, 41, 0.1); border-left: 3px solid var(--urgency-p2);">
                <div class="field-label">Missing Information</div>
                <div class="field-value">${escapeHtml(fields.missing_fields.join(', '))}</div>
            </div>
        `;
    }
}

function displayKbResults(kbHits) {
    if (!kbHits || kbHits.length === 0) {
        elements.kbResults.innerHTML = '<p class="suggestions-hint">No related knowledge base articles found.</p>';
        return;
    }

    elements.kbResults.innerHTML = kbHits.slice(0, 5).map(hit => `
        <div class="kb-item">
            <div class="kb-item-source">[KB:${escapeHtml(hit.doc_name)}#${escapeHtml(hit.section)}]</div>
            <div class="kb-item-text">${escapeHtml(truncate(hit.passage, 200))}</div>
            <div class="kb-item-score">Relevance: ${(hit.relevance_score * 100).toFixed(0)}%</div>
        </div>
    `).join('');
}

function displayChainOfThought(ticket, result) {
    const stages = [];

    // Stage 1: Input Guardrails
    const inputGuardrail = result.input_guardrail_status;
    if (inputGuardrail) {
        const riskColors = { low: '#10b981', medium: '#f0b429', high: '#e67e22', critical: '#d64545' };
        const riskColor = riskColors[inputGuardrail.risk_level] || '#6b6b6b';
        stages.push({
            title: 'Input Security Check',
            icon: inputGuardrail.passed ? '✓' : (inputGuardrail.blocked ? '✕' : '⚠'),
            status: inputGuardrail.blocked ? 'blocked' : (inputGuardrail.passed ? 'passed' : 'warning'),
            items: [
                { label: 'Security scan', value: inputGuardrail.passed ? 'Passed' : 'Flagged' },
                { label: 'Risk level', value: `<span style="color: ${riskColor}; font-weight: 600;">${(inputGuardrail.risk_level || 'low').toUpperCase()}</span>` },
                ...(inputGuardrail.issues_found?.length > 0 ? [{ label: 'Issues detected', value: inputGuardrail.issues_found.join(', ') }] : [])
            ]
        });
    }

    // Stage 2: Triage Analysis
    const triage = result.triage;
    const urgencyColors = { P0: '#d64545', P1: '#e67e22', P2: '#f0b429', P3: '#7d9f80' };
    const sentimentColors = { negative: '#d64545', neutral: '#6b6b6b', positive: '#10b981' };

    // Extract keywords from ticket for display
    const keywords = extractKeywords(ticket.subject + ' ' + ticket.body);

    stages.push({
        title: 'Triage Analysis',
        icon: '🔍',
        status: 'passed',
        items: [
            { label: 'Detected keywords', value: keywords.slice(0, 5).map(k => `<span class="cot-keyword">${k}</span>`).join(' ') },
            { label: 'Customer sentiment', value: `<span style="color: ${sentimentColors[triage.sentiment]};">${capitalizeFirst(triage.sentiment)}</span> (${(triage.confidence * 100).toFixed(0)}% confidence)` },
            { label: 'Category match', value: `<span class="cot-category">${triage.category}</span>` },
            { label: 'Urgency decision', value: `<span style="color: ${urgencyColors[triage.urgency]}; font-weight: 700;">${triage.urgency}</span>` },
            { label: 'Rationale', value: `<em>"${truncate(triage.rationale, 150)}"</em>` }
        ]
    });

    // Stage 3: Auto-Reply Check
    const autoReply = result.auto_reply;
    if (autoReply) {
        stages.push({
            title: 'Similarity Check',
            icon: autoReply.is_auto_reply ? '⚡' : '🔄',
            status: autoReply.is_auto_reply ? 'auto' : 'passed',
            items: [
                { label: 'Best match score', value: `${(autoReply.similarity_score * 100).toFixed(1)}%` },
                { label: 'Threshold', value: '80%' },
                ...(autoReply.is_auto_reply ? [
                    { label: 'Matched ticket', value: `<strong>${autoReply.matched_ticket_id}</strong>` },
                    { label: 'Decision', value: '<span style="color: #10b981; font-weight: 600;">AUTO-REPLY TRIGGERED</span>' }
                ] : [
                    { label: 'Decision', value: 'Generate new response' }
                ])
            ]
        });
    }

    // Stage 4: KB Retrieval
    const kbHits = result.kb_hits || [];
    const topHit = kbHits[0];
    stages.push({
        title: 'Knowledge Base Search',
        icon: '📚',
        status: kbHits.length > 0 ? 'passed' : 'warning',
        items: [
            { label: 'Search query', value: `<code>${truncate(ticket.subject, 50)}</code>` },
            { label: 'Results found', value: `${kbHits.length} articles` },
            ...(topHit ? [
                { label: 'Top match', value: `[KB:${topHit.doc_name}#${topHit.section}]` },
                { label: 'Top relevance', value: `<strong>${(topHit.relevance_score * 100).toFixed(0)}%</strong>` }
            ] : [])
        ]
    });

    // Stage 5: Routing Decision
    const routing = result.routing;
    stages.push({
        title: 'Routing Decision',
        icon: '🎯',
        status: routing.escalation ? 'warning' : 'passed',
        items: [
            { label: 'Assigned team', value: `<strong>${capitalizeFirst(routing.team)}</strong>` },
            { label: 'SLA target', value: formatSla(routing.sla_hours) },
            { label: 'Escalation', value: routing.escalation ? '<span style="color: #d64545; font-weight: 600;">YES - ESCALATED</span>' : 'No' },
            { label: 'Reasoning', value: `<em>"${truncate(routing.reasoning, 120)}"</em>` }
        ]
    });

    // Stage 6: Response Generation
    const citations = result.reply.citations || [];
    stages.push({
        title: 'Response Generation',
        icon: '✍️',
        status: 'passed',
        items: [
            { label: 'KB citations used', value: citations.length > 0 ? citations.slice(0, 3).join(', ') : 'None' },
            { label: 'Response length', value: `${result.reply.customer_reply.length} characters` }
        ]
    });

    // Stage 7: Output Guardrails
    const outputGuardrail = result.guardrail_status;
    stages.push({
        title: 'Output Validation',
        icon: outputGuardrail.passed ? '✓' : '⚠',
        status: outputGuardrail.passed ? 'passed' : 'warning',
        items: [
            { label: 'Hallucination check', value: outputGuardrail.passed ? 'Passed' : 'Review needed' },
            { label: 'Policy compliance', value: outputGuardrail.passed ? 'Passed' : 'Issues found' },
            ...(outputGuardrail.issues_found?.length > 0 ? [{ label: 'Issues', value: outputGuardrail.issues_found.join(', ') }] : []),
            ...(outputGuardrail.fixes_applied?.length > 0 ? [{ label: 'Fixes applied', value: outputGuardrail.fixes_applied.join(', ') }] : [])
        ]
    });

    // Render stages
    elements.reasoningStages.innerHTML = stages.map((stage, index) => `
        <div class="cot-stage ${stage.status}" data-stage="${index}">
            <div class="cot-stage-header" onclick="toggleCotStage(${index})">
                <span class="cot-stage-icon">${stage.icon}</span>
                <span class="cot-stage-title">${stage.title}</span>
                <span class="cot-stage-toggle">▼</span>
            </div>
            <div class="cot-stage-content">
                ${stage.items.map(item => `
                    <div class="cot-item">
                        <span class="cot-item-label">→ ${item.label}:</span>
                        <span class="cot-item-value">${item.value}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function toggleCotStage(index) {
    const stage = document.querySelector(`.cot-stage[data-stage="${index}"]`);
    if (stage) {
        stage.classList.toggle('collapsed');
    }
}

function extractKeywords(text) {
    // Simple keyword extraction - find important words
    const stopWords = new Set(['the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that', 'these', 'those', 'am', 'i', 'we', 'you', 'he', 'she', 'it', 'they', 'my', 'our', 'your', 'his', 'her', 'its', 'their', 'what', 'which', 'who', 'whom', 'please', 'hi', 'hello', 'thanks', 'thank', 'dear', 'sincerely', 'regards']);

    const words = text.toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(word => word.length > 2 && !stopWords.has(word));

    // Count frequency and return top words
    const freq = {};
    words.forEach(word => { freq[word] = (freq[word] || 0) + 1; });

    return Object.entries(freq)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([word]) => word);
}

function displayReply(result) {
    const outputGuardrail = result.guardrail_status;
    const inputGuardrail = result.input_guardrail_status;

    // Determine overall guardrail status
    const inputPassed = !inputGuardrail || inputGuardrail.passed;
    const outputPassed = outputGuardrail.passed;
    const blocked = inputGuardrail?.blocked;

    let statusClass = 'passed';
    let statusText = 'Approved';

    if (blocked) {
        statusClass = 'blocked';
        statusText = 'Blocked';
    } else if (!inputPassed || !outputPassed) {
        statusClass = 'failed';
        statusText = 'Review Required';
    }

    elements.guardrailStatus.className = `guardrail-status ${statusClass}`;
    elements.guardrailStatus.querySelector('.guardrail-text').textContent = statusText;

    // Display reply with citation highlighting
    const replyText = result.reply.customer_reply;
    const suggestedDraft = result.reply.suggested_draft;
    
    let replyHtml = '';
    
    // If there's a suggested draft, it means low confidence - show notification sent + AI draft for review
    if (suggestedDraft) {
        replyHtml = `
            <div class="reply-section sent-reply flagged-section">
                <div class="reply-section-header">
                    <span class="reply-section-label sent-label">Notification Sent to Customer</span>
                    <span class="reply-section-badge flagged-badge">Low Confidence</span>
                </div>
                <div class="reply-section-content">${highlightCitations(replyText, result.kb_hits)}</div>
            </div>
            <div class="reply-section draft-reply">
                <div class="reply-section-header">
                    <span class="reply-section-label draft-label">AI Suggested Response</span>
                    <span class="reply-section-badge draft-badge">Needs Agent Review</span>
                </div>
                <div class="reply-section-content">${highlightCitations(suggestedDraft, result.kb_hits)}</div>
            </div>
        `;
    } else {
        // High confidence - full response was sent
        replyHtml = `
            <div class="reply-section-header-inline">
                <span class="reply-section-badge sent-badge-inline">High Confidence - Response Sent</span>
            </div>
            ${highlightCitations(replyText, result.kb_hits)}
        `;
    }
    
    elements.replyContent.innerHTML = replyHtml;
}

function displayAgentResponse(result) {
    // Show the agent response in the main conversation panel (below customer message)
    const reply = result.reply;
    
    console.log('displayAgentResponse called');
    console.log('reply object:', reply);
    console.log('should_send value:', reply ? reply.should_send : 'reply is null');
    console.log('agentResponseItem element:', elements.agentResponseItem);
    
    if (!reply) {
        console.error('No reply in result');
        return;
    }
    
    if (!elements.agentResponseItem) {
        console.error('agentResponseItem element not found');
        return;
    }
    
    // ALWAYS show the agent response - should_send should always be true now
    // (either full response or notification is sent)
    elements.agentResponseItem.style.display = 'block';
    elements.agentResponseBody.innerHTML = highlightCitations(reply.customer_reply, result.kb_hits);
    elements.agentResponseTime.textContent = 'Just now';
    
    // Check if this is a low-confidence response (has suggested_draft means notification was sent)
    if (reply.suggested_draft) {
        // Low confidence - notification was sent, draft available for review
        elements.autoSentBadge.textContent = 'Flagged for Review';
        elements.autoSentBadge.style.display = 'inline-block';
        elements.autoSentBadge.className = 'auto-sent-badge flagged';
    } else {
        // High confidence - full response was sent
        elements.autoSentBadge.textContent = 'Response Sent';
        elements.autoSentBadge.style.display = 'inline-block';
        elements.autoSentBadge.className = 'auto-sent-badge sent';
    }
    
    console.log('Agent response displayed successfully');
}

function highlightCitations(text, kbHits) {
    // Parse and highlight [KB:doc#section] citations
    const citationRegex = /\[KB:([^\]]+)\]/g;

    return escapeHtml(text).replace(citationRegex, (match, citation) => {
        // Find matching KB hit
        const [docName, section] = citation.split('#');
        const hit = kbHits?.find(h =>
            h.doc_name === docName && (section ? h.section === section : true)
        );

        if (hit) {
            const relevance = (hit.relevance_score * 100).toFixed(0);
            return `<span class="citation-link" data-doc="${escapeHtml(docName)}" data-section="${escapeHtml(section || '')}" data-relevance="${relevance}" onclick="showCitationSource(this)">[KB:${escapeHtml(citation)}]</span>`;
        }
        return `<span class="citation-link citation-unmatched">[KB:${escapeHtml(citation)}]</span>`;
    });
}

function showCitationSource(element) {
    const docName = element.dataset.doc;
    const section = element.dataset.section;
    const relevance = element.dataset.relevance;

    // Find the KB hit
    const result = state.currentResult;
    const hit = result?.kb_hits?.find(h =>
        h.doc_name === docName && (section ? h.section === section : true)
    );

    if (hit) {
        elements.citationModalTitle.textContent = `Knowledge Base Source`;
        elements.citationSourceLabel.textContent = `[KB:${hit.doc_name}#${hit.section}]`;
        elements.citationPassage.textContent = hit.passage;
        elements.citationRelevance.innerHTML = `<strong>Relevance Score:</strong> ${relevance}%`;
        elements.citationModal.classList.add('visible');
    }
}

function closeCitationModal() {
    elements.citationModal.classList.remove('visible');
}

async function handleCustomerFollowUp() {
    const replyText = elements.customerReplyInput.value.trim();
    if (!replyText) return;

    const ticket = state.currentTicket;
    const result = state.currentResult;
    if (!ticket || !result) return;

    // Get conversation ID from the result
    const conversationId = result.conversation?.conversation_id;
    console.log('[DEBUG] Current result:', result);
    console.log('[DEBUG] Conversation info:', result.conversation);
    console.log('[DEBUG] Conversation ID:', conversationId);

    // Disable input while processing
    elements.customerReplyInput.disabled = true;
    elements.sendCustomerReply.disabled = true;
    elements.sendCustomerReply.classList.add('loading');

    // Add customer's follow-up message to conversation
    addFollowUpMessage(ticket.customer_name, replyText, 'customer');

    // Clear input
    elements.customerReplyInput.value = '';

    try {
        let response;

        // Always construct conversation_id from original ticket
        const originalTicketId = ticket.ticket_id.split('-followup-')[0]; // Get original ID
        const convId = conversationId || `conv-${originalTicketId}`;

        console.log('[DEBUG] Original ticket ID:', originalTicketId);
        console.log('[DEBUG] Using conversation ID:', convId);

        if (conversationId) {
            // Use the conversation follow-up endpoint
            const followUpData = {
                ticket_id: originalTicketId + '-followup-' + Date.now(),
                created_at: new Date().toISOString(),
                body: replyText  // Just the follow-up text, not concatenated
            };

            console.log('[DEBUG] Sending to /api/conversations/' + convId + '/followup:', followUpData);

            response = await fetch(`/api/conversations/${convId}/followup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(followUpData)
            });
        } else {
            // Fallback: use /api/process with explicit conversation flags
            // Don't use spread - construct explicitly to avoid stale data
            const followUpTicket = {
                ticket_id: originalTicketId + '-followup-' + Date.now(),
                created_at: new Date().toISOString(),
                customer_name: ticket.customer_name,
                customer_email: ticket.customer_email,
                account_tier: ticket.account_tier,
                product: ticket.product,
                subject: `Re: ${ticket.subject}`,
                body: replyText,
                attachments: null,
                conversation_id: convId,
                is_followup: true
            };

            console.log('[DEBUG] Sending to /api/process:', followUpTicket);

            response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(followUpTicket)
            });
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to process follow-up');
        }

        const newResult = await response.json();

        // Add agent's response to conversation
        addFollowUpMessage('Support Agent', newResult.reply.customer_reply, 'agent', newResult.kb_hits);

        // Update the current result for context
        state.currentResult = newResult;

        // Update extracted fields display with merged data
        if (newResult.extracted_fields) {
            displayExtractedFields(newResult.extracted_fields);
        }

        showToast('Follow-up processed', 'success');

    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
        // Remove the customer message if processing failed
        const lastMessage = elements.followUpMessages.lastElementChild;
        if (lastMessage) lastMessage.remove();
    } finally {
        elements.customerReplyInput.disabled = false;
        elements.sendCustomerReply.disabled = false;
        elements.sendCustomerReply.classList.remove('loading');
    }
}

function addFollowUpMessage(senderName, content, type, kbHits = []) {
    const initials = type === 'customer' ? getInitials(senderName) : 'AI';
    const avatarClass = type === 'customer' ? '' : 'agent-avatar';
    const itemClass = type === 'customer' ? 'follow-up-message' : 'follow-up-response';
    const labelClass = type === 'customer' ? 'customer' : 'agent';
    const label = type === 'customer' ? 'Customer Reply' : 'Agent Response';

    const messageHtml = `
        <div class="conversation-item ${itemClass}">
            <div class="message-header">
                <div class="avatar ${avatarClass}">${initials}</div>
                <div class="message-meta">
                    <span class="sender-name">${escapeHtml(senderName)}</span>
                    <span class="message-time">Just now</span>
                </div>
            </div>
            <div class="message-content">
                <span class="follow-up-label ${labelClass}">${label}</span>
                <div class="message-body">${type === 'agent' ? highlightCitations(content, kbHits) : escapeHtml(content)}</div>
            </div>
        </div>
    `;

    elements.followUpMessages.insertAdjacentHTML('beforeend', messageHtml);

    // Scroll to the new message
    elements.followUpMessages.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function displayNotes(result) {
    const notes = result.reply.internal_notes;
    const triage = result.triage;
    const routing = result.routing;
    const inputGuardrail = result.input_guardrail_status;
    const outputGuardrail = result.guardrail_status;

    let notesHtml = '';

    // Input guardrail notice
    if (inputGuardrail && (inputGuardrail.blocked || !inputGuardrail.passed)) {
        const bgColor = inputGuardrail.blocked ? 'rgba(239, 68, 68, 0.1)' : 'rgba(240, 180, 41, 0.1)';
        const borderColor = inputGuardrail.blocked ? 'var(--urgency-p0)' : 'var(--urgency-p2)';
        const titleColor = inputGuardrail.blocked ? 'var(--urgency-p0)' : 'var(--urgency-p1)';
        const title = inputGuardrail.blocked ? 'INPUT BLOCKED' : 'INPUT FLAGGED';
        
        notesHtml += `<div style="background: ${bgColor}; border: 1px solid ${borderColor}; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
            <strong style="color: ${titleColor};">${title}</strong>
            <p style="margin: 8px 0 0 0; font-size: 13px;">
                Risk Level: <strong>${(inputGuardrail.risk_level || 'unknown').toUpperCase()}</strong><br>
                ${inputGuardrail.issues_found?.length > 0 ? `Issues: <strong>${inputGuardrail.issues_found.join(', ')}</strong>` : ''}
            </p>
        </div>`;
    }

    // Auto-reply notice
    if (result.auto_reply?.is_auto_reply) {
        notesHtml += `<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid var(--success); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
            <strong style="color: var(--success);">AUTO-REPLY TRIGGERED</strong>
            <p style="margin: 8px 0 0 0; font-size: 13px;">
                Similar ticket found: <strong>${result.auto_reply.matched_ticket_id}</strong><br>
                Similarity: <strong>${(result.auto_reply.similarity_score * 100).toFixed(1)}%</strong><br>
                Time since match: <strong>${result.auto_reply.time_since_match_hours?.toFixed(1) || 'N/A'} hours</strong>
            </p>
        </div>`;
    }

    // Triage rationale
    notesHtml += `<strong>Triage Analysis:</strong>\n${triage.rationale}\n\n`;

    // Routing reasoning
    notesHtml += `<strong>Routing Decision:</strong>\n${routing.reasoning}\n\n`;

    // Escalation note
    if (routing.escalation) {
        notesHtml += `<strong style="color: var(--urgency-p0);">ESCALATION REQUIRED</strong>\n\n`;
    }

    // Generated notes
    notesHtml += `<strong>Agent Notes:</strong>\n${notes}`;

    // Output guardrail issues
    if (outputGuardrail.issues_found && outputGuardrail.issues_found.length > 0) {
        notesHtml += `\n\n<strong style="color: var(--urgency-p1);">Output Guardrail Issues:</strong>\n`;
        notesHtml += outputGuardrail.issues_found.map(issue => `- ${issue}`).join('\n');
    }

    elements.notesContent.innerHTML = notesHtml;
}

function copyReplyToClipboard() {
    if (!state.currentResult) return;
    
    const reply = state.currentResult.reply.customer_reply;
    navigator.clipboard.writeText(reply).then(() => {
        showToast('Reply copied to clipboard', 'success');
        elements.copyReply.querySelector('svg + span, span')?.remove();
        const span = document.createElement('span');
        span.textContent = 'Copied!';
        elements.copyReply.appendChild(span);
        setTimeout(() => {
            span.textContent = 'Copy Reply';
        }, 2000);
    });
}

function handleSendReply() {
    showToast('Reply sent to customer!', 'success');
    switchView('tickets');
}

// KB View
function initKbView() {
    let searchTimer;
    elements.kbSearchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(searchKnowledgeBase, 300);
    });
}

async function searchKnowledgeBase() {
    const query = elements.kbSearchInput.value.trim();
    
    if (query.length < 3) {
        elements.kbSearchResults.innerHTML = '<p class="search-hint">Enter at least 3 characters to search</p>';
        return;
    }
    
    elements.kbSearchResults.innerHTML = '<div class="suggestions-loading">Searching...</div>';
    
    try {
        const response = await fetch('/api/kb/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, k: 10 })
        });
        
        if (response.ok) {
            const results = await response.json();
            displayKbSearchResults(results);
        }
    } catch (error) {
        elements.kbSearchResults.innerHTML = '<p class="search-hint">Search failed. Please try again.</p>';
    }
}

function displayKbSearchResults(results) {
    if (!results || results.length === 0) {
        elements.kbSearchResults.innerHTML = '<p class="search-hint">No results found for your query.</p>';
        return;
    }
    
    elements.kbSearchResults.innerHTML = results.map(hit => `
        <div class="kb-item">
            <div class="kb-item-source">[KB:${escapeHtml(hit.doc_name)}#${escapeHtml(hit.section)}]</div>
            <div class="kb-item-text">${escapeHtml(hit.passage)}</div>
            <div class="kb-item-score">Relevance: ${(hit.relevance_score * 100).toFixed(0)}%</div>
        </div>
    `).join('');
}

// Admin View
function initAdminView() {
    elements.knownIssueForm.addEventListener('submit', handleSubmitKnownIssue);
    elements.clearIssueForm.addEventListener('click', resetKnownIssueForm);
    
    // Generate default issue ID
    generateIssueId();
}

function generateIssueId() {
    const year = new Date().getFullYear();
    const random = String(Math.floor(Math.random() * 900) + 100);
    elements.issueId.value = `API-${year}-${random}`;
}

function resetKnownIssueForm() {
    elements.knownIssueForm.reset();
    generateIssueId();
}

async function handleSubmitKnownIssue(e) {
    e.preventDefault();
    
    const submitBtn = elements.submitIssue;
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    
    // Build issue data
    const issueData = {
        issue_id: elements.issueId.value.trim(),
        title: elements.issueTitle.value.trim(),
        status: elements.issueStatus.value,
        severity: elements.issueSeverity.value,
        affected: elements.issueAffected.value.trim(),
        expected_resolution: elements.issueExpectedResolution.value || null,
        description: elements.issueDescription.value.trim(),
        workaround: elements.issueWorkaround.value.trim()
    };
    
    try {
        const response = await fetch('/api/admin/known-issue', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(issueData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add known issue');
        }
        
        const result = await response.json();
        showToast('Known issue added to knowledge base!', 'success');
        resetKnownIssueForm();
        
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = elements.toast;
    toast.querySelector('.toast-message').textContent = message;
    toast.className = `toast ${type} visible`;
    
    setTimeout(() => {
        toast.classList.remove('visible');
    }, 3000);
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncate(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function getInitials(name) {
    if (!name) return '?';
    const parts = name.split(' ').filter(Boolean);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0][0].toUpperCase();
}

function formatTime(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

function formatSla(hours) {
    if (hours <= 1) return '1 hour';
    if (hours < 24) return `${hours} hours`;
    if (hours === 24) return '24 hours';
    const days = Math.floor(hours / 24);
    return `${days} day${days > 1 ? 's' : ''}`;
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
}
