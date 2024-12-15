document.addEventListener('DOMContentLoaded', function() {
    const transportButtons = document.querySelectorAll('.btn-group .btn');
    transportButtons.forEach(button => {
        button.addEventListener('click', function() {
            transportButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });

    const checkboxes = document.querySelectorAll('.form-check-input');
    const selectedServices = document.querySelector('.selected-services');

    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const serviceName = this.nextElementSibling.textContent.trim();

            if (this.checked) {
                const badge = document.createElement('span');
                badge.classList.add('badge', 'bg-primary', 'me-1', 'mb-1');
                badge.innerHTML = `${serviceName} <i class="bi bi-x"></i>`;

                badge.querySelector('i').addEventListener('click', function() {
                    badge.remove();
                    checkbox.checked = false;
                });

                selectedServices.appendChild(badge);
            } else {
                const badges = selectedServices.querySelectorAll('.badge');
                badges.forEach(badge => {
                    if (badge.textContent.includes(serviceName)) {
                        badge.remove();
                    }
                });
            }
        });
    });
});