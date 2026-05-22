// Functions for new order page
console.log('nueva_orden.js loaded successfully');

let clientSearchDebounce = null;
let clientSuggestions = [];

function clearClientSelection(options = {}) {
    const keepQuery = options.keepQuery || false;
    document.getElementById('id_cliente').value = '';
    document.getElementById('ci_cliente').value = '';
    document.getElementById('nombre_cliente').value = '';
    document.getElementById('telefono_cliente').value = '';

    if (!keepQuery) {
        const inputCI = document.getElementById('buscarCliente');
        if (inputCI) {
            inputCI.value = '';
        }
    }
}

function renderClientSuggestions(clientes) {
    const container = document.getElementById('clientSuggestions');
    if (!container) return;

    clientSuggestions = Array.isArray(clientes) ? clientes : [];

    if (!clientSuggestions.length) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }

    container.innerHTML = clientSuggestions.map((cliente, index) => {
        const nombre = cliente.nombre_completo || 'Sin nombre';
        const ci = cliente.ci || '';
        const telefono = cliente.telefono || 'Sin teléfono';

        return `
            <button type="button" class="client-suggestion-item" data-index="${index}">
                <span>
                    <span class="client-suggestion-name">${nombre}</span><br>
                    <span class="client-suggestion-meta">CI: ${ci}</span>
                </span>
                <span class="client-suggestion-meta">${telefono}</span>
            </button>
        `;
    }).join('');

    container.style.display = 'block';

    container.querySelectorAll('.client-suggestion-item').forEach(item => {
        item.addEventListener('click', function() {
            const selected = clientSuggestions[Number(this.dataset.index)];
            if (selected) {
                fillClientFields(selected, true);
            }
        });
    });
}

function hideClientSuggestions() {
    const container = document.getElementById('clientSuggestions');
    if (!container) return;
    container.innerHTML = '';
    container.style.display = 'none';
}

function fillClientFields(cliente, keepQuery = false) {
    if (!cliente) return;

    document.getElementById('id_cliente').value = cliente.id || '';
    document.getElementById('ci_cliente').value = cliente.ci || '';
    document.getElementById('nombre_cliente').value = cliente.nombre_completo || '';
    document.getElementById('telefono_cliente').value = cliente.telefono || '';

    const inputCI = document.getElementById('buscarCliente');
    if (inputCI && !keepQuery) {
        inputCI.value = cliente.ci || '';
    }

    hideClientSuggestions();
}

async function buscarClientesEnVivo(query) {
    const value = (query || '').trim();
    if (!value) {
        hideClientSuggestions();
        clearClientSelection({ keepQuery: true });
        return;
    }

    try {
        const response = await fetch(`/api/clientes/buscar?q=${encodeURIComponent(value)}`);
        const result = await response.json();

        if (result.success) {
            if (result.cliente) {
                fillClientFields(result.cliente, false);
            }

            if (result.clientes && result.clientes.length > 1) {
                renderClientSuggestions(result.clientes);
            } else if (result.clientes && result.clientes.length === 1 && !result.cliente) {
                renderClientSuggestions(result.clientes);
            } else if (!result.cliente) {
                hideClientSuggestions();
            }
        } else {
            hideClientSuggestions();
            clearClientSelection({ keepQuery: true });
        }
    } catch (error) {
        console.error('Error al buscar clientes:', error);
    }
}

// Search client by CI
async function buscarCliente() {
    console.log('buscarCliente function called');
    const inputCI = document.getElementById('buscarCliente');
    const btnBuscar = document.getElementById('btnBuscarCliente');
    const ci = inputCI.value.trim();
    
    if (!ci) {
        alert('Por favor ingrese un CI');
        inputCI.focus();
        return;
    }
    
    // Show loading indicator on button if exists
    let originalText = '';
    if (btnBuscar) {
        originalText = btnBuscar.innerHTML;
        btnBuscar.disabled = true;
        btnBuscar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Buscando...';
    }
    
    // Disable input
    inputCI.disabled = true;
    
    try {
        const response = await fetch(`/api/clientes/buscar?ci=${encodeURIComponent(ci)}`);
        const result = await response.json();
        
        if (result.success && result.cliente) {
            // Fill fields with client data
            fillClientFields(result.cliente, false);
            
            // Show success notification
            if (typeof showNotification === 'function') {
                showNotification('Cliente encontrado: ' + result.cliente.nombre_completo, 'success');
            } else {
                alert('Cliente encontrado: ' + result.cliente.nombre_completo);
            }
        } else {
            alert('Cliente no encontrado. Por favor registre el cliente primero.');
            clearClientSelection({ keepQuery: true });
            inputCI.focus();
        }
    } catch (error) {
        console.error('Error al buscar cliente:', error);
        alert('Error al buscar el cliente. Por favor intente nuevamente.');
        clearClientSelection({ keepQuery: true });
    } finally {
        // Restore button and input
        if (btnBuscar) {
            btnBuscar.disabled = false;
            btnBuscar.innerHTML = originalText;
        }
        inputCI.disabled = false;
    }
}

// Make function globally accessible
window.buscarCliente = buscarCliente;

// Calculate balance automatically
function calcularSaldo() {
    const total = parseFloat(document.getElementById('total').value) || 0;
    const adelanto = parseFloat(document.getElementById('adelanto').value) || 0;
    const saldo = total - adelanto;
    
    document.getElementById('saldo').value = saldo.toFixed(2);
}

// Make function globally accessible
window.calcularSaldo = calcularSaldo;

// Set minimum delivery date (today)
document.addEventListener('DOMContentLoaded', function() {
    const fechaEntrega = document.getElementById('fecha_entrega');
    if (fechaEntrega) {
        const hoy = new Date().toISOString().split('T')[0];
        fechaEntrega.min = hoy;
    }
});

// Validate and submit form
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('formNuevaOrden');
    
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Validate required fields
            const camposRequeridos = form.querySelectorAll('[required]');
            let valido = true;
            
            camposRequeridos.forEach(campo => {
                if (!validateField(campo)) {
                    valido = false;
                }
            });
            
            if (!valido) {
                alert('Por favor complete todos los campos requeridos');
                return;
            }
            
            // Validate that a client has been selected
            const idCliente = document.getElementById('id_cliente').value;
            if (!idCliente) {
                alert('Por favor busque y seleccione un cliente');
                return;
            }

            // Poblamos ocultos de empleado
            const userProfile = typeof getCurrentUserProfile === 'function' ? getCurrentUserProfile() : null;
            if (userProfile) {
                document.getElementById('id_empleado').value = userProfile.uid || '';
                document.getElementById('nombre_empleado').value = userProfile.nombre || '';
            }
            
            // Mostrar loading
            const loading = document.getElementById('loading');
            if (loading) {
                loading.style.display = 'flex';
            }
            
            // Preparar datos del formulario
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/ordenes/nueva', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showNotification('Orden creada exitosamente', 'success');
                    formModified = false;
                    setTimeout(() => {
                        window.location.href = `/ordenes/${result.orden_id}`;
                    }, 1000);
                } else {
                    alert('Error al crear la orden: ' + result.error);
                }
            } catch (error) {
                alert('Error al crear la orden: ' + error.message);
            } finally {
                if (loading) {
                    loading.style.display = 'none';
                }
            }
        });
    }
});

// Validation of numeric graduation fields
document.addEventListener('DOMContentLoaded', function() {
    const esferaInputs = document.querySelectorAll('#od_esf, #oi_esf');
    const cilindroInputs = document.querySelectorAll('#od_cil, #oi_cil');
    const ejeInputs = document.querySelectorAll('#od_eje, #oi_eje');
    
    // Validar rango de esfera (-20 a +20)
    esferaInputs.forEach(input => {
        input.addEventListener('change', function() {
            const valor = parseFloat(this.value);
            if (valor < -20 || valor > 20) {
                alert('La esfera debe estar entre -20 y +20');
                this.value = 0;
            }
        });
    });
    
    // Validar rango de cilindro (-10 a 0)
    cilindroInputs.forEach(input => {
        input.addEventListener('change', function() {
            const valor = parseFloat(this.value);
            if (valor && (valor < -10 || valor > 0)) {
                alert('El cilindro debe estar entre -10 y 0');
                this.value = '';
            }
        });
    });
    
    // Validar rango de eje (0 a 180)
    ejeInputs.forEach(input => {
        input.addEventListener('change', function() {
            const valor = parseInt(this.value);
            if (valor && (valor < 0 || valor > 180)) {
                alert('El eje debe estar entre 0 y 180');
                this.value = '';
            }
        });
    });
    
    // Si hay cilindro, el eje es requerido
    cilindroInputs.forEach((cilInput, index) => {
        cilInput.addEventListener('change', function() {
            const ejeInput = ejeInputs[index];
            if (this.value && parseFloat(this.value) !== 0) {
                ejeInput.setAttribute('required', 'required');
            } else {
                ejeInput.removeAttribute('required');
            }
        });
    });
});

// Payment fields validation
document.addEventListener('DOMContentLoaded', function() {
    const totalInput = document.getElementById('total');
    const adelantoInput = document.getElementById('adelanto');
    
    if (adelantoInput && totalInput) {
        adelantoInput.addEventListener('change', function() {
            const total = parseFloat(totalInput.value) || 0;
            const adelanto = parseFloat(this.value) || 0;
            
            if (adelanto > total) {
                alert('El adelanto no puede ser mayor que el total');
                this.value = total;
                calcularSaldo();
            }
            
            if (adelanto < 0) {
                alert('El adelanto no puede ser negativo');
                this.value = 0;
                calcularSaldo();
            }
        });
    }
});

// Auto-complete client name when searching
document.addEventListener('DOMContentLoaded', function() {
    const buscarInput = document.getElementById('buscarCliente');
    const btnBuscar = document.getElementById('btnBuscarCliente');
    const suggestions = document.getElementById('clientSuggestions');
    
    // Add click event to button
    if (btnBuscar) {
        btnBuscar.addEventListener('click', function(e) {
            e.preventDefault();
            buscarCliente();
        });
    }
    
    if (buscarInput) {
        buscarInput.addEventListener('input', function() {
            clearTimeout(clientSearchDebounce);
            const query = this.value;

            if (!query.trim()) {
                hideClientSuggestions();
                clearClientSelection({ keepQuery: true });
                return;
            }

            clientSearchDebounce = setTimeout(() => {
                buscarClientesEnVivo(query);
            }, 250);
        });

        buscarInput.addEventListener('focus', function() {
            if (clientSuggestions.length > 0) {
                const container = document.getElementById('clientSuggestions');
                if (container) {
                    container.style.display = 'block';
                }
            }
        });
    }

    if (suggestions) {
        document.addEventListener('click', function(e) {
            if (!suggestions.contains(e.target) && e.target !== buscarInput) {
                hideClientSuggestions();
            }
        });
    }

    // Add Enter key support
    if (buscarInput) {
        buscarInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                buscarCliente();
            }
        });
    }
});
