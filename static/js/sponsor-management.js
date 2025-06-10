document.addEventListener('DOMContentLoaded', function() {
    // Cache DOM elements
    const filterForm = document.getElementById('sponsorFilterForm');
    const sponsorSearch = document.getElementById('sponsorSearch');
    const eventFilter = document.getElementById('eventFilter');
    const tierFilter = document.getElementById('tierFilter');
    const statusFilter = document.getElementById('statusFilter');
    const industryFilter = document.getElementById('industryFilter');
    const minAmount = document.getElementById('minAmount');
    const maxAmount = document.getElementById('maxAmount');
    const sponsorRows = document.querySelectorAll('table tbody tr');
    const refreshBtn = document.getElementById('refreshSponsors');

    // Initialize tooltips
    const tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltips.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Handle form submission
    filterForm.addEventListener('submit', function(e) {
        e.preventDefault();
        applyFilters();
    });

    // Handle search input with debounce
    sponsorSearch.addEventListener('input', debounce(function() {
        applyFilters();
    }, 300));

    // Handle select filters change
    [eventFilter, tierFilter, statusFilter, industryFilter].forEach(filter => {
        filter.addEventListener('change', function() {
            applyFilters();
        });
    });

    // Handle amount inputs with debounce
    [minAmount, maxAmount].forEach(input => {
        input.addEventListener('input', debounce(function() {
            applyFilters();
        }, 300));
    });

    // Handle form reset
    filterForm.addEventListener('reset', function() {
        setTimeout(() => {
            applyFilters();
        }, 0);
    });

    // Handle refresh button
    refreshBtn.addEventListener('click', function() {
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
        window.location.reload();
    });

    // Apply filters function
    function applyFilters() {
        const filters = {
            search: sponsorSearch.value.toLowerCase(),
            event: eventFilter.value,
            tier: tierFilter.value,
            status: statusFilter.value,
            industry: industryFilter.value,
            minAmount: parseFloat(minAmount.value) || 0,
            maxAmount: parseFloat(maxAmount.value) || Infinity
        };

        sponsorRows.forEach(row => {
            let shouldShow = true;

            // Search filter
            if (filters.search) {
                const searchableContent = row.textContent.toLowerCase();
                shouldShow = shouldShow && searchableContent.includes(filters.search);
            }

            // Event filter
            if (filters.event) {
                const eventId = row.getAttribute('data-event-id');
                shouldShow = shouldShow && eventId === filters.event;
            }

            // Tier filter
            if (filters.tier) {
                const tierId = row.getAttribute('data-tier-id');
                shouldShow = shouldShow && tierId === filters.tier;
            }

            // Status filter
            if (filters.status) {
                const status = row.getAttribute('data-status');
                shouldShow = shouldShow && status === filters.status;
            }

            // Industry filter
            if (filters.industry) {
                const industry = row.getAttribute('data-industry');
                shouldShow = shouldShow && industry === filters.industry;
            }

            // Amount range filter
            const amount = parseFloat(row.getAttribute('data-amount')) || 0;
            shouldShow = shouldShow && amount >= filters.minAmount && amount <= filters.maxAmount;

            // Show/hide row
            row.style.display = shouldShow ? '' : 'none';
        });

        updateEmptyState();
    }

    // Update empty state message
    function updateEmptyState() {
        const visibleRows = Array.from(sponsorRows).filter(row => row.style.display !== 'none');
        const tableBody = document.querySelector('table tbody');
        const existingEmptyMessage = document.querySelector('.no-results-message');

        if (visibleRows.length === 0) {
            if (!existingEmptyMessage) {
                const emptyMessage = document.createElement('tr');
                emptyMessage.className = 'no-results-message';
                emptyMessage.innerHTML = `
                    <td colspan="6" class="text-center py-4">
                        <div class="text-muted">
                            <i class="fas fa-search fa-2x mb-3"></i>
                            <h6>No sponsors found</h6>
                            <p class="small">Try adjusting your filters or add new sponsors.</p>
                        </div>
                    </td>
                `;
                tableBody.appendChild(emptyMessage);
            }
        } else if (existingEmptyMessage) {
            existingEmptyMessage.remove();
        }
    }

    // Export sponsors function
    window.exportSponsors = function() {
        const visibleRows = Array.from(sponsorRows).filter(row => row.style.display !== 'none');
        
        // Show loading state on export button
        const exportBtn = document.querySelector('[onclick="exportSponsors()"]');
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Exporting...';

        try {
            // Gather data from visible rows
            const data = visibleRows.map(row => ({
                company: row.querySelector('h6').textContent.trim(),
                event: row.querySelector('.badge.bg-primary').textContent.trim(),
                tier: row.querySelector('[class*="badge"]').textContent.trim(),
                amount: row.getAttribute('data-amount') ? '₹' + parseFloat(row.getAttribute('data-amount')).toLocaleString('en-IN', {maximumFractionDigits: 2}) : '₹0',
                status: row.getAttribute('data-status') ? row.getAttribute('data-status').charAt(0).toUpperCase() + row.getAttribute('data-status').slice(1) : 'Active',
                industry: row.getAttribute('data-industry') ? row.getAttribute('data-industry').charAt(0).toUpperCase() + row.getAttribute('data-industry').slice(1) : 'Other',
                contact: row.querySelector('.text-muted small') ? row.querySelector('.text-muted small').textContent.trim() : '',
                created_at: new Date().toISOString().split('T')[0] // Current date as fallback
            }));

            // Define CSV headers
            const headers = [
                'Company Name',
                'Event',
                'Sponsorship Tier',
                'Amount',
                'Status',
                'Industry',
                'Contact Information',
                'Created Date'
            ];

            // Convert to CSV
            const csvContent = "data:text/csv;charset=utf-8,"
                + headers.join(",") + "\n"
                + data.map(row => [
                    `"${row.company}"`,
                    `"${row.event}"`,
                    `"${row.tier}"`,
                    `"${row.amount}"`,
                    `"${row.status}"`,
                    `"${row.industry}"`,
                    `"${row.contact}"`,
                    `"${row.created_at}"`
                ].join(",")).join("\n");

            // Generate filename with timestamp
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            const filename = `sponsors_export_${timestamp}.csv`;

            // Download file
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", filename);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Show success message
            exportBtn.classList.remove('btn-primary');
            exportBtn.classList.add('btn-success');
            exportBtn.innerHTML = '<i class="fas fa-check me-1"></i>Exported!';
            
            setTimeout(() => {
                exportBtn.disabled = false;
                exportBtn.classList.remove('btn-success');
                exportBtn.classList.add('btn-primary');
                exportBtn.innerHTML = '<i class="fas fa-file-export me-1"></i>Export';
            }, 2000);

        } catch (error) {
            console.error('Export error:', error);
            
            // Show error message
            exportBtn.classList.remove('btn-primary');
            exportBtn.classList.add('btn-danger');
            exportBtn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Export Failed';
            
            setTimeout(() => {
                exportBtn.disabled = false;
                exportBtn.classList.remove('btn-danger');
                exportBtn.classList.add('btn-primary');
                exportBtn.innerHTML = '<i class="fas fa-file-export me-1"></i>Export';
            }, 2000);
        }
    }

    // Debounce helper function
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
}); 