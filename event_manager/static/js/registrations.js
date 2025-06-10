// Handle export registrations
document.addEventListener('DOMContentLoaded', function() {
    const exportBtn = document.getElementById('exportRegistrationsBtn');
    const refreshBtn = document.getElementById('refreshDataBtn');
    const registrationSearch = document.getElementById('registrationSearch');
    const eventFilter = document.getElementById('eventFilter');
    const roleFilter = document.getElementById('roleFilter');
    const typeFilter = document.getElementById('typeFilter');

    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            // Get current filter values
            const filters = {
                event: eventFilter ? eventFilter.value : '',
                role: roleFilter ? roleFilter.value : '',
                type: typeFilter ? typeFilter.value : '',
                search: registrationSearch ? registrationSearch.value : ''
            };

            // Create query string from filters
            const queryString = Object.entries(filters)
                .filter(([_, value]) => value)
                .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
                .join('&');

            // Redirect to export URL with filters
            window.location.href = `/events/registrations/export/?${queryString}`;
        });
    }

    // Handle real-time search
    if (registrationSearch) {
        registrationSearch.addEventListener('input', debounce(function() {
            filterTable();
        }, 300));
    }

    // Handle filter changes
    [eventFilter, roleFilter, typeFilter].forEach(filter => {
        if (filter) {
            filter.addEventListener('change', function() {
                filterTable();
            });
        }
    });

    function filterTable() {
        const searchTerm = registrationSearch.value.toLowerCase();
        const eventValue = eventFilter.value.toLowerCase();
        const roleValue = roleFilter.value.toLowerCase();
        const typeValue = typeFilter.value.toLowerCase();
        
        const rows = document.querySelectorAll('#registrationsTable tbody tr');
        
        rows.forEach(row => {
            const name = row.querySelector('td:nth-child(1)').textContent.toLowerCase();
            const event = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const role = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
            const type = row.querySelector('td:nth-child(4)').textContent.toLowerCase();
            
            const matchesSearch = !searchTerm || name.includes(searchTerm) || event.includes(searchTerm);
            const matchesEvent = !eventValue || event.includes(eventValue);
            const matchesRole = !roleValue || role.includes(roleValue);
            const matchesType = !typeValue || type.includes(typeValue);
            
            row.style.display = (matchesSearch && matchesEvent && matchesRole && matchesType) ? '' : 'none';
        });
    }

    // Refresh button functionality
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            location.reload();
        });
    }
});

// Utility function for debouncing
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