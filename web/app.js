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
    
    // Agent panel
    panelTabs: document.querySelectorAll('.panel-tab'),
    panelKb: document.getElementById('panelKb'),
    panelReply: document.getElementById('panelReply'),
    panelNotes: document.getElementById('panelNotes'),
    kbResults: document.getElementById('kbResults'),
    replyContent: document.getElementById('replyContent'),
    notesContent: document.getElementById('notesContent'),
    guardrailStatus: document.getElementById('guardrailStatus'),
    copyReply: document.getElementById('copyReply'),
    sendReply: document.getElementById('sendReply'),
    
    // KB view
    kbSearchInput: document.getElementById('kbSearchInput'),
    kbSearchResults: document.getElementById('kbSearchResults'),
    
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
}

function switchPanel(panelName) {
    elements.panelTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.panel === panelName);
    });
    
    document.querySelectorAll('.panel-content').forEach(panel => {
        panel.classList.remove('active');
    });
    
    switch (panelName) {
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
    
    // KB results
    displayKbResults(result.kb_hits);
    
    // Reply
    displayReply(result);
    
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

function displayReply(result) {
    const guardrail = result.guardrail_status;
    
    elements.guardrailStatus.className = `guardrail-status ${guardrail.passed ? 'passed' : 'failed'}`;
    elements.guardrailStatus.querySelector('.guardrail-text').textContent = guardrail.passed ? 'Approved' : 'Review Required';
    
    elements.replyContent.textContent = result.reply.customer_reply;
}

function displayNotes(result) {
    const notes = result.reply.internal_notes;
    const triage = result.triage;
    const routing = result.routing;

    let notesHtml = '';

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

    // Guardrail issues
    if (result.guardrail_status.issues_found && result.guardrail_status.issues_found.length > 0) {
        notesHtml += `\n\n<strong style="color: var(--urgency-p1);">Guardrail Issues:</strong>\n`;
        notesHtml += result.guardrail_status.issues_found.map(issue => `- ${issue}`).join('\n');
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
