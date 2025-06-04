// Auto-refresh for queue display
function setupAutoRefresh(interval = 30000) {
    setTimeout(function() {
        window.location.reload();
    }, interval);
}

// Highlight the current customer in queue
function highlightCurrentCustomer() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const currentTime = `${hours}:${minutes}`;
    
    document.querySelectorAll('.customer-time').forEach(el => {
        if (el.textContent.trim() === currentTime) {
            el.closest('.list-group-item').classList.add('current-customer');
        }
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the queue page
    if (document.querySelector('#queue-display')) {
        setupAutoRefresh();
        highlightCurrentCustomer();
    }
    
    // Flash message auto-dismiss
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    });
});