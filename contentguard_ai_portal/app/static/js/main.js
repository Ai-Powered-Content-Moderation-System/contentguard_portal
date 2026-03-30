// Main JavaScript file for ContentGuard AI

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
    initializeTabs();
    initializeModals();
    initializeForms();
    initializeCharts();
    setupWebSocket();
});

// Tooltips
function initializeTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip-popup';
    tooltip.textContent = e.target.dataset.tooltip;
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
    tooltip.style.left = rect.left + (rect.width - tooltip.offsetWidth) / 2 + 'px';
    
    setTimeout(() => tooltip.classList.add('show'), 10);
}

function hideTooltip() {
    const tooltip = document.querySelector('.tooltip-popup');
    if (tooltip) {
        tooltip.remove();
    }
}

// Tabs
function initializeTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function(e) {
            const tabId = this.dataset.tab;
            const container = this.closest('.tabs-container');
            
            // Update tabs
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Update content
            container.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            container.querySelector(`#tab-${tabId}`).classList.add('active');
        });
    });
}

// Modals
function initializeModals() {
    document.querySelectorAll('[data-modal]').forEach(button => {
        button.addEventListener('click', function() {
            const modalId = this.dataset.modal;
            openModal(modalId);
        });
    });
    
    document.querySelectorAll('.modal-close, .modal-overlay').forEach(element => {
        element.addEventListener('click', closeModal);
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('show');
        document.body.classList.add('modal-open');
    }
}

function closeModal() {
    document.querySelectorAll('.modal.show').forEach(modal => {
        modal.classList.remove('show');
    });
    document.body.classList.remove('modal-open');
}

// Forms
function initializeForms() {
    // File upload preview
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', function(e) {
            const preview = document.querySelector(this.dataset.preview);
            if (preview && this.files.length > 0) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                };
                reader.readAsDataURL(this.files[0]);
            }
        });
    });
    
    // Form validation
    document.querySelectorAll('form[data-validate]').forEach(form => {
        form.addEventListener('submit', validateForm);
    });
}

function validateForm(e) {
    const form = e.target;
    let isValid = true;
    
    form.querySelectorAll('[required]').forEach(field => {
        if (!field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        }
    });
    
    form.querySelectorAll('[data-pattern]').forEach(field => {
        const pattern = new RegExp(field.dataset.pattern);
        if (!pattern.test(field.value)) {
            showFieldError(field, field.dataset.message || 'Invalid format');
            isValid = false;
        }
    });
    
    if (!isValid) {
        e.preventDefault();
    }
}

function showFieldError(field, message) {
    field.classList.add('error');
    
    let errorDiv = field.nextElementSibling;
    if (!errorDiv || !errorDiv.classList.contains('field-error')) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        field.parentNode.insertBefore(errorDiv, field.nextSibling);
    }
    errorDiv.textContent = message;
    
    field.addEventListener('input', function removeError() {
        field.classList.remove('error');
        if (errorDiv) errorDiv.remove();
        field.removeEventListener('input', removeError);
    });
}

// Charts
function initializeCharts() {
    if (typeof Chart === 'undefined') return;
    
    document.querySelectorAll('[data-chart]').forEach(canvas => {
        const chartType = canvas.dataset.chart;
        const chartData = JSON.parse(canvas.dataset.data || '{}');
        
        switch(chartType) {
            case 'bar':
                createBarChart(canvas, chartData);
                break;
            case 'pie':
                createPieChart(canvas, chartData);
                break;
            case 'line':
                createLineChart(canvas, chartData);
                break;
        }
    });
}

function createBarChart(canvas, data) {
    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.labels || [],
            datasets: [{
                label: data.label || 'Values',
                data: data.values || [],
                backgroundColor: '#06e0d5',
                borderColor: '#06e0d5',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#fff' }
                },
                x: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#fff' }
                }
            },
            plugins: {
                legend: { labels: { color: '#fff' } }
            }
        }
    });
}

function createPieChart(canvas, data) {
    new Chart(canvas, {
        type: 'pie',
        data: {
            labels: data.labels || [],
            datasets: [{
                data: data.values || [],
                backgroundColor: ['#06e0d5', '#3b82f6', '#10b981', '#f59e0b', '#ef4444']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { 
                    position: 'bottom',
                    labels: { color: '#fff' }
                }
            }
        }
    });
}

function createLineChart(canvas, data) {
    new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.labels || [],
            datasets: [{
                label: data.label || 'Trend',
                data: data.values || [],
                borderColor: '#06e0d5',
                backgroundColor: 'rgba(6, 224, 213, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#fff' }
                },
                x: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#fff' }
                }
            },
            plugins: {
                legend: { labels: { color: '#fff' } }
            }
        }
    });
}

// WebSocket for real-time updates
function setupWebSocket() {
    if (window.location.protocol === 'https:') {
        var wsProtocol = 'wss:';
    } else {
        var wsProtocol = 'ws:';
    }
    
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = function() {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = function() {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(setupWebSocket, 5000);
    };
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'job_update':
            updateJobStatus(data.job);
            break;
        case 'notification':
            showNotification(data.message, data.type);
            break;
        case 'stats_update':
            updateStats(data.stats);
            break;
    }
}

// Notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.classList.add('show'), 10);
    
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    });
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// Job Updates
function updateJobStatus(job) {
    const jobElement = document.querySelector(`[data-job-id="${job.job_id}"]`);
    if (jobElement) {
        const statusElement = jobElement.querySelector('.job-status');
        if (statusElement) {
            statusElement.className = `job-status status-${job.status}`;
            statusElement.textContent = job.status;
        }
        
        const progressElement = jobElement.querySelector('.job-progress');
        if (progressElement && job.progress !== undefined) {
            progressElement.style.width = `${job.progress}%`;
            progressElement.textContent = `${job.progress}%`;
        }
    }
}

// Stats Updates
function updateStats(stats) {
    for (const [key, value] of Object.entries(stats)) {
        const element = document.querySelector(`[data-stat="${key}"]`);
        if (element) {
            element.textContent = value;
        }
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy', 'error');
    });
}

// Export functions
window.ContentGuard = {
    showNotification,
    copyToClipboard,
    openModal,
    closeModal
};