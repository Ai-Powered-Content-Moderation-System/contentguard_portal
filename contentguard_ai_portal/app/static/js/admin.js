// Admin Panel JavaScript

document.addEventListener('DOMContentLoaded', function() {
    loadAdminStats();
    initializeDataTables();
    initializeBulkActions();
    setupChartRefresh();
    initializeUserManagement();
});

// Load admin statistics
async function loadAdminStats() {
    try {
        const response = await fetch('/admin/stats');
        const data = await response.json();
        
        if (data.success) {
            updateAdminStats(data.stats);
        }
    } catch (error) {
        console.error('Failed to load admin stats:', error);
    }
}

function updateAdminStats(stats) {
    const statsMap = {
        'total-users': stats.total_users,
        'total-comments': stats.total_comments,
        'bad-comments': stats.bad_comments,
        'unreviewed': stats.unreviewed,
        'total-jobs': stats.total_jobs
    };
    
    for (const [id, value] of Object.entries(statsMap)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
            animateNumber(element, value);
        }
    }
}

function animateNumber(element, target) {
    const start = parseInt(element.textContent) || 0;
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.floor(start + (target - start) * progress);
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// DataTables
function initializeDataTables() {
    document.querySelectorAll('.datatable').forEach(table => {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search...';
        searchInput.className = 'datatable-search';
        searchInput.addEventListener('input', function(e) {
            filterTable(table, e.target.value);
        });
        
        table.parentNode.insertBefore(searchInput, table);
        
        // Add sorting
        table.querySelectorAll('th').forEach((th, index) => {
            if (th.dataset.sortable !== 'false') {
                th.addEventListener('click', () => sortTable(table, index));
                th.style.cursor = 'pointer';
            }
        });
    });
}

function filterTable(table, searchTerm) {
    const rows = table.querySelectorAll('tbody tr');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
    
    // Update visible count
    const visibleCount = Array.from(rows).filter(row => row.style.display !== 'none').length;
    const countElement = table.parentNode.querySelector('.datatable-count');
    if (countElement) {
        countElement.textContent = `Showing ${visibleCount} of ${rows.length} entries`;
    }
}

function sortTable(table, column) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const isNumeric = table.querySelector(`td:nth-child(${column + 1})`).dataset.numeric === 'true';
    
    const direction = table.dataset.sortDirection === 'asc' ? 'desc' : 'asc';
    table.dataset.sortDirection = direction;
    table.dataset.sortColumn = column;
    
    rows.sort((a, b) => {
        const aVal = a.querySelector(`td:nth-child(${column + 1})`).textContent;
        const bVal = b.querySelector(`td:nth-child(${column + 1})`).textContent;
        
        if (isNumeric) {
            return direction === 'asc' 
                ? parseFloat(aVal) - parseFloat(bVal)
                : parseFloat(bVal) - parseFloat(aVal);
        } else {
            return direction === 'asc'
                ? aVal.localeCompare(bVal)
                : bVal.localeCompare(aVal);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
    
    // Update sort indicators
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });
    const header = table.querySelector(`th:nth-child(${column + 1})`);
    header.classList.add(`sort-${direction}`);
}

// Bulk Actions
function initializeBulkActions() {
    const selectAll = document.getElementById('select-all');
    if (selectAll) {
        selectAll.addEventListener('change', function() {
            document.querySelectorAll('.select-item').forEach(cb => {
                cb.checked = this.checked;
            });
        });
    }
    
    const bulkActionBtn = document.getElementById('bulk-action');
    if (bulkActionBtn) {
        bulkActionBtn.addEventListener('click', performBulkAction);
    }
}

async function performBulkAction() {
    const selected = Array.from(document.querySelectorAll('.select-item:checked'))
        .map(cb => cb.value);
    
    if (selected.length === 0) {
        ContentGuard.showNotification('No items selected', 'warning');
        return;
    }
    
    const action = document.getElementById('bulk-action-select').value;
    if (!action) {
        ContentGuard.showNotification('Please select an action', 'warning');
        return;
    }
    
    if (!confirm(`Are you sure you want to ${action} ${selected.length} items?`)) {
        return;
    }
    
    try {
        const response = await fetch('/comments/batch/review', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: action,
                items: selected
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            ContentGuard.showNotification(data.message, 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            ContentGuard.showNotification(data.error, 'error');
        }
    } catch (error) {
        ContentGuard.showNotification('Failed to perform action', 'error');
    }
}

// Chart Refresh
function setupChartRefresh() {
    const refreshBtn = document.getElementById('refresh-charts');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async function() {
            this.disabled = true;
            this.innerHTML = '<span class="spinner-small"></span> Refreshing...';
            
            try {
                await refreshCharts();
                ContentGuard.showNotification('Charts updated', 'success');
            } catch (error) {
                ContentGuard.showNotification('Failed to refresh charts', 'error');
            } finally {
                this.disabled = false;
                this.innerHTML = 'Refresh Charts';
            }
        });
    }
}

async function refreshCharts() {
    const response = await fetch('/admin/chart-data');
    const data = await response.json();
    
    if (data.success) {
        updateCharts(data.data);
    }
}

function updateCharts(data) {
    // Update category chart
    const categoryChart = Chart.getChart('category-chart');
    if (categoryChart && data.categories) {
        categoryChart.data.labels = data.categories.labels;
        categoryChart.data.datasets[0].data = data.categories.values;
        categoryChart.update();
    }
    
    // Update timeline chart
    const timelineChart = Chart.getChart('timeline-chart');
    if (timelineChart && data.timeline) {
        timelineChart.data.labels = data.timeline.labels;
        timelineChart.data.datasets[0].data = data.timeline.values;
        timelineChart.update();
    }
}

// User Management
function initializeUserManagement() {
    // User search
    const userSearch = document.getElementById('user-search');
    if (userSearch) {
        userSearch.addEventListener('input', debounce(function(e) {
            filterUsers(e.target.value);
        }, 300));
    }
    
    // Role filters
    document.querySelectorAll('.role-filter').forEach(filter => {
        filter.addEventListener('change', filterUsersByRole);
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function filterUsers(searchTerm) {
    const rows = document.querySelectorAll('.user-row');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const username = row.querySelector('.user-username').textContent.toLowerCase();
        const email = row.querySelector('.user-email').textContent.toLowerCase();
        const name = row.querySelector('.user-name').textContent.toLowerCase();
        
        const matches = username.includes(term) || email.includes(term) || name.includes(term);
        row.style.display = matches ? '' : 'none';
    });
}

function filterUsersByRole() {
    const selectedRoles = Array.from(document.querySelectorAll('.role-filter:checked'))
        .map(cb => cb.value);
    
    if (selectedRoles.length === 0) {
        document.querySelectorAll('.user-row').forEach(row => {
            row.style.display = '';
        });
        return;
    }
    
    document.querySelectorAll('.user-row').forEach(row => {
        const role = row.dataset.role;
        row.style.display = selectedRoles.includes(role) ? '' : 'none';
    });
}

// Export functions
window.Admin = {
    loadAdminStats,
    performBulkAction,
    refreshCharts
};