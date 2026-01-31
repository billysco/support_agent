/**
 * Support Triage System - Frontend Application
 */

// State
let sampleTickets = [];
let currentResult = null;

// DOM Elements
const ticketInput = document.getElementById('ticketInput');
const processBtn = document.getElementById('processBtn');
const clearBtn = document.getElementById('clearBtn');
const resultsSection = document.getElementById('resultsSection');
const modeBadge = document.getElementById('modeBadge');
const footerMode = document.getElementById('footerMode');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadSamples();
    setupEventListeners();
    checkMode();
});

// Load sample tickets
async function loadSamples() {
    try {
        const response = await fetch('/api/samples');
        if (response.ok) {
            sampleTickets = await response.json();
        }
    } catch (error) {
        console.error('Failed to load samples:', error);
    }
}

// Check processing mode
async function checkMode() {
    try {
        const response = await fetch('/api/mode');
        if (response.ok) {
            const data = await response.json();
            updateModeDisplay(data.mode);
        }
    } catch (error) {
        updateModeDisplay('unknown');
    }
}

// Update mode display
function updateModeDisplay(mode) {
    const modeText = modeBadge.querySelector('.mode-text');
    modeBadge.className = 'mode-badge ' + mode;
    
    if (mode === 'mock') {
        modeText.textContent = 'Mock Mode';
    } else if (mode === 'real') {
        modeText.textContent = 'Real Mode';
    } else {
        modeText.textContent = 'Unknown';
    }
    
    footerMode.textContent = mode.toUpperCase();
}

// Setup event listeners
function setupEventListeners() {
    // Sample buttons
    document.querySelectorAll('.btn-sample').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.sample);
            if (sampleTickets[index]) {
                ticketInput.value = JSON.stringify(sampleTickets[index], null, 2);
            }
        });
    });
    
    // Clear button
    clearBtn.addEventListener('click', () => {
        ticketInput.value = '';
        resultsSection.classList.remove('visible');
        currentResult = null;
    });
    
    // Process button
    processBtn.addEventListener('click', processTicket);
    
    // Collapsible sections
    document.querySelectorAll('.card-header.collapsible').forEach(header => {
        header.addEventListener('click', () => {
            const targetId = header.dataset.target;
            const content = document.getElementById(targetId);
            const icon = header.querySelector('.collapse-icon');
            
            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                header.classList.remove('collapsed');
                icon.textContent = '-';
            } else {
                content.classList.add('collapsed');
                header.classList.add('collapsed');
                icon.textContent = '+';
            }
        });
    });
    
    // Copy reply button
    document.getElementById('copyReplyBtn').addEventListener('click', () => {
        if (currentResult && currentResult.reply) {
            navigator.clipboard.writeText(currentResult.reply.customer_reply);
            const btn = document.getElementById('copyReplyBtn');
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 2000);
        }
    });
}

// Process ticket
async function processTicket() {
    const input = ticketInput.value.trim();
    
    if (!input) {
        alert('Please enter a ticket or select a sample.');
        return;
    }
    
    let ticket;
    try {
        ticket = JSON.parse(input);
    } catch (error) {
        alert('Invalid JSON. Please check your input.');
        return;
    }
    
    // Show loading state
    processBtn.classList.add('loading');
    processBtn.disabled = true;
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ticket)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Processing failed');
        }
        
        const result = await response.json();
        currentResult = result;
        displayResults(result);
        
        // Update mode based on result
        updateModeDisplay(result.processing_mode);
        
    } catch (error) {
        alert('Error processing ticket: ' + error.message);
    } finally {
        processBtn.classList.remove('loading');
        processBtn.disabled = false;
    }
}

// Display results
function displayResults(result) {
    resultsSection.classList.add('visible');
    
    // Triage
    const urgency = result.triage.urgency;
    const urgencyBadge = document.getElementById('urgencyBadge');
    urgencyBadge.textContent = urgency;
    urgencyBadge.className = 'urgency-badge ' + urgency.toLowerCase();
    
    document.getElementById('category').textContent = result.triage.category;
    document.getElementById('sentiment').textContent = result.triage.sentiment;
    
    const confidence = Math.round(result.triage.confidence * 100);
    document.getElementById('confidenceValue').textContent = confidence + '%';
    document.getElementById('confidenceFill').style.setProperty('--confidence', confidence + '%');
    
    document.getElementById('rationale').textContent = '"' + result.triage.rationale + '"';
    
    // Routing
    document.getElementById('team').textContent = result.routing.team;
    document.getElementById('sla').textContent = formatSLA(result.routing.sla_hours);
    
    const escalationBadge = document.getElementById('escalationBadge');
    escalationBadge.textContent = result.routing.escalation ? 'Escalate' : 'Normal';
    escalationBadge.className = 'escalation-badge ' + (result.routing.escalation ? 'yes' : 'no');
    
    document.getElementById('reasoning').textContent = result.routing.reasoning;
    
    // Guardrail
    const guardrailBadge = document.getElementById('guardrailBadge');
    guardrailBadge.textContent = result.guardrail_status.passed ? 'Passed' : 'Failed';
    guardrailBadge.className = 'guardrail-badge ' + (result.guardrail_status.passed ? 'passed' : 'failed');
    
    const issuesList = document.getElementById('issuesList');
    if (result.guardrail_status.issues_found && result.guardrail_status.issues_found.length > 0) {
        issuesList.innerHTML = result.guardrail_status.issues_found
            .map(issue => `<div class="issue-item">${escapeHtml(issue)}</div>`)
            .join('');
    } else {
        issuesList.innerHTML = '<p class="no-issues">No issues detected</p>';
    }
    
    // Extracted Fields
    const fieldsGrid = document.getElementById('fieldsGrid');
    const fields = result.extracted_fields;
    const fieldItems = [
        { label: 'Environment', value: fields.environment },
        { label: 'Region', value: fields.region },
        { label: 'Error Message', value: fields.error_message },
        { label: 'Impact', value: fields.impact },
        { label: 'Order/Invoice', value: fields.order_id },
        { label: 'Requested Action', value: fields.requested_action },
        { label: 'Reproduction Steps', value: fields.reproduction_steps }
    ];
    
    fieldsGrid.innerHTML = fieldItems.map(field => `
        <div class="field-item">
            <div class="field-label">${field.label}</div>
            <div class="field-value ${!field.value ? 'empty' : ''}">${field.value ? escapeHtml(truncate(field.value, 100)) : 'Not provided'}</div>
        </div>
    `).join('');
    
    const missingFields = document.querySelector('.missing-list');
    if (fields.missing_fields && fields.missing_fields.length > 0) {
        missingFields.textContent = fields.missing_fields.join(', ');
        document.getElementById('missingFields').style.display = 'block';
    } else {
        document.getElementById('missingFields').style.display = 'none';
    }
    
    // KB Citations
    const citationsList = document.getElementById('citationsList');
    if (result.kb_hits && result.kb_hits.length > 0) {
        citationsList.innerHTML = result.kb_hits.slice(0, 5).map(hit => `
            <div class="citation-item">
                <div class="citation-ref">[KB:${hit.doc_name}#${hit.section}]</div>
                <div class="citation-passage">"${escapeHtml(truncate(hit.passage, 200))}"</div>
            </div>
        `).join('');
    } else {
        citationsList.innerHTML = '<p class="no-issues">No relevant KB passages found</p>';
    }
    
    // Customer Reply
    document.getElementById('replyText').textContent = result.reply.customer_reply;
    
    // Internal Notes
    document.getElementById('notesText').textContent = result.reply.internal_notes;
    
    // Raw JSON
    document.getElementById('jsonOutput').textContent = JSON.stringify(result, null, 2);
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Helper functions
function formatSLA(hours) {
    if (hours <= 1) return '1 hour';
    if (hours < 24) return hours + ' hours';
    if (hours === 24) return '24 hours (1 day)';
    const days = Math.floor(hours / 24);
    return hours + ' hours (' + days + ' day' + (days > 1 ? 's' : '') + ')';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncate(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

