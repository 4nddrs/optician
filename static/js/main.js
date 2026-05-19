// Eliminación del Service Worker para evitar intercepción defectuosa de fetch
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function(registrations) {
        for(let registration of registrations) {
            registration.unregister();
        }
    });
}

// General utilities
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById('modalBackdrop');
    
    if (modal && backdrop) {
        modal.classList.add('show');
        backdrop.classList.add('show');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById('modalBackdrop');
    
    if (modal && backdrop) {
        modal.classList.remove('show');
        backdrop.classList.remove('show');
        document.body.style.overflow = 'auto';
    }
}

// Cerrar modales al hacer clic en el backdrop
document.addEventListener('DOMContentLoaded', function() {
    const backdrop = document.getElementById('modalBackdrop');
    if (backdrop) {
        backdrop.addEventListener('click', function() {
            const modales = document.querySelectorAll('.modal.show');
            modales.forEach(modal => {
                modal.classList.remove('show');
            });
            backdrop.classList.remove('show');
            document.body.style.overflow = 'auto';
        });
    }
});

// Ensure backdrop visibility matches actual modals (fix residual blur)
function ensureBackdropState() {
    const backdrop = document.getElementById('modalBackdrop');
    if (!backdrop) return;
    // Consider modals shown either by .show class or by inline display style
    const anyModalShownByClass = document.querySelectorAll('.modal.show, .modal-backdrop.show').length > 0;
    const backdrops = Array.from(document.querySelectorAll('.modal-backdrop'));
    const anyBackdropVisibleByStyle = backdrops.some(b => {
        const cs = window.getComputedStyle(b);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
    });

    const anyModalShown = anyModalShownByClass || anyBackdropVisibleByStyle;
    if (anyModalShown) {
        backdrop.classList.add('show');
    } else {
        backdrop.classList.remove('show');
        document.body.style.overflow = 'auto';
    }
}

// Run on load and periodically to recover from inconsistent states
document.addEventListener('DOMContentLoaded', function() {
    ensureBackdropState();
    // Safety: re-check a couple of times shortly after load
    setTimeout(ensureBackdropState, 200);
    setTimeout(ensureBackdropState, 1000);
});

// Cerrar modales con tecla ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modales = document.querySelectorAll('.modal.show');
        const backdrop = document.getElementById('modalBackdrop');
        
        if (modales.length > 0 && backdrop) {
            modales.forEach(modal => {
                modal.classList.remove('show');
            });
            backdrop.classList.remove('show');
            document.body.style.overflow = 'auto';
        }
    }
});

// Aplicar animación slideIn a elementos con stagger
document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.stat-card, .form-card, .detail-card, .cliente-card, .sucursal-card');
    
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });
});

// Show notifications
function showNotification(message, type = 'success', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `notificacion notificacion-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#10b981' : '#ef4444'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 3000;
        animation: slideIn 0.3s ease;
        max-width: 400px;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, duration);
}

// Formatear fecha
function formatDate(date) {
    const dateObj = new Date(date);
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return dateObj.toLocaleDateString('es-ES', options);
}

// Format currency
function formatCurrency(amount) {
    return `Bs. ${parseFloat(amount).toFixed(2)}`;
}

// Validate form field
function validateField(input) {
    if (input.hasAttribute('required') && !input.value.trim()) {
        input.style.borderColor = 'var(--color-error)';
        return false;
    }
    input.style.borderColor = 'var(--border-color)';
    return true;
}

// Apply real-time validation
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('.form-input[required], .form-select[required]');
    
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.style.borderColor = 'var(--color-success)';
            }
        });
    });
});

// Prevent form submission with Enter (except in textarea)
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
            }
        });
    });
});

// Confirm before leaving page with modified form
let formModified = false;
let allowUnload = false; // Flag to bypass the beforeunload confirmation

document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                formModified = true;
            });
        });
        
        form.addEventListener('submit', function() {
            formModified = false;
        });
    });
});

window.addEventListener('beforeunload', function(e) {
    if (formModified && !allowUnload) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// Call this function before programmatically navigating away
function bypassUnloadConfirmation() {
    allowUnload = true;
}

// Scroll suave a elementos
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Auto-resize para textareas
document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('.form-textarea');
    
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });
});
