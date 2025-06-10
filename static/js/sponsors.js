document.addEventListener('DOMContentLoaded', function() {
    // Cache DOM elements
    const filterForm = document.getElementById('sponsorFilterForm');
    const sponsorSearch = document.getElementById('sponsorSearch');
    const sponsorRows = document.querySelectorAll('.sponsor-row');
    const clearFiltersBtn = filterForm.querySelector('button[type="reset"]');

    // Initialize any third-party plugins (if needed)
    initializeDatePickers();

    // Handle form submission
    filterForm.addEventListener('submit', function(e) {
        e.preventDefault();
        applyFilters();
    });

    // Handle search input
    sponsorSearch.addEventListener('input', debounce(function() {
        applyFilters();
    }, 300));

    // Handle clear filters
    clearFiltersBtn.addEventListener('click', function() {
        setTimeout(() => {
            applyFilters();
        }, 0);
    });

    // Handle individual filter changes
    const filterInputs = filterForm.querySelectorAll('select, input[type="date"], input[type="number"]');
    filterInputs.forEach(input => {
        input.addEventListener('change', function() {
            applyFilters();
        });
    });

    // Apply filters function
    function applyFilters() {
        const filters = {
            search: sponsorSearch.value.toLowerCase(),
            event: document.getElementById('eventFilter').value,
            tier: document.getElementById('tierFilter').value,
            status: document.getElementById('statusFilter').value,
            industry: document.getElementById('industryFilter').value,
            startDate: document.getElementById('startDate').value,
            endDate: document.getElementById('endDate').value,
            minAmount: document.getElementById('minAmount').value,
            maxAmount: document.getElementById('maxAmount').value
        };

        sponsorRows.forEach(row => {
            let shouldShow = true;

            // Search filter
            if (filters.search) {
                const sponsorName = row.querySelector('h6').textContent.toLowerCase();
                const sponsorId = row.querySelector('small').textContent.toLowerCase();
                shouldShow = shouldShow && (sponsorName.includes(filters.search) || sponsorId.includes(filters.search));
            }

            // Event filter
            if (filters.event) {
                const eventId = row.getAttribute('data-event-id');
                shouldShow = shouldShow && eventId === filters.event;
            }

            // Tier filter
            if (filters.tier) {
                const tier = row.getAttribute('data-tier');
                shouldShow = shouldShow && tier === filters.tier;
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

            // Date range filter
            if (filters.startDate || filters.endDate) {
                const sponsorDate = new Date(row.getAttribute('data-date'));
                if (filters.startDate && new Date(filters.startDate) > sponsorDate) {
                    shouldShow = false;
                }
                if (filters.endDate && new Date(filters.endDate) < sponsorDate) {
                    shouldShow = false;
                }
            }

            // Amount range filter
            if (filters.minAmount || filters.maxAmount) {
                const amount = parseFloat(row.getAttribute('data-amount'));
                if (filters.minAmount && parseFloat(filters.minAmount) > amount) {
                    shouldShow = false;
                }
                if (filters.maxAmount && parseFloat(filters.maxAmount) < amount) {
                    shouldShow = false;
                }
            }

            // Show/hide row based on filter results
            row.style.display = shouldShow ? '' : 'none';
        });

        // Update empty state message
        updateEmptyState();
    }

    // Update empty state visibility
    function updateEmptyState() {
        const visibleRows = Array.from(sponsorRows).filter(row => row.style.display !== 'none');
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            emptyState.style.display = visibleRows.length === 0 ? 'block' : 'none';
        }
    }

    // Initialize date pickers (if using a third-party library)
    function initializeDatePickers() {
        // Add date picker initialization code here if needed
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