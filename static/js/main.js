// Main JavaScript file

// Enable tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Add event listener for API key visibility toggle
    const toggleButtons = document.querySelectorAll('.toggle-visibility');
    if (toggleButtons) {
        toggleButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                const target = document.getElementById(targetId);
                
                if (target.type === 'password') {
                    target.type = 'text';
                    this.innerHTML = '<i class="bi bi-eye-slash"></i>';
                    this.setAttribute('title', 'Hide');
                } else {
                    target.type = 'password';
                    this.innerHTML = '<i class="bi bi-eye"></i>';
                    this.setAttribute('title', 'Show');
                }
                
                // Update the tooltip
                bootstrap.Tooltip.getInstance(this).dispose();
                new bootstrap.Tooltip(this);
            });
        });
    }
});