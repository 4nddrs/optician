// Functions for new order page
console.log('nueva_orden.js loaded successfully');

// Search client by CI
async function buscarCliente() {
    console.log('buscarCliente function called');
    const inputCI = document.getElementById('buscarCliente');
    const btnBuscar = document.querySelector('button[onclick*="buscarCliente"]');
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
            document.getElementById('id_cliente').value = result.cliente.id;
            document.getElementById('nombre_cliente').value = result.cliente.nombre_completo;
            document.getElementById('telefono_cliente').value = result.cliente.telefono;
            
            // Show success notification
            if (typeof showNotification === 'function') {
                showNotification('Cliente encontrado: ' + result.cliente.nombre_completo, 'success');
            } else {
                alert('Cliente encontrado: ' + result.cliente.nombre_completo);
            }
        } else {
            alert('Cliente no encontrado. Por favor registre el cliente primero.');
            document.getElementById('id_cliente').value = '';
            document.getElementById('nombre_cliente').value = '';
            document.getElementById('telefono_cliente').value = '';
            inputCI.focus();
        }
    } catch (error) {
        console.error('Error al buscar cliente:', error);
        alert('Error al buscar el cliente. Por favor intente nuevamente.');
        document.getElementById('id_cliente').value = '';
        document.getElementById('nombre_cliente').value = '';
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
    
    // Add click event to button
    if (btnBuscar) {
        btnBuscar.addEventListener('click', function(e) {
            e.preventDefault();
            buscarCliente();
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
