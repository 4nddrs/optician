// Functions for edit order page
console.log('editar_orden.js loaded successfully');

document.addEventListener('DOMContentLoaded', function() {
    // Populate form with existing order data if available
    if (window.ORDEN_A_EDITAR) {
        const o = window.ORDEN_A_EDITAR;
        const form = document.getElementById('formEditarOrden') || document.getElementById('formNuevaOrden');
        
        if (form) {
            // Pre-fill main inputs
            if (document.getElementById('id_sucursal')) document.getElementById('id_sucursal').value = o.id_sucursal || '';
            if (document.getElementById('fecha_entrega')) document.getElementById('fecha_entrega').value = o.fecha_entrega || '';
            
            // Client data
            if (window.CLIENTE_A_EDITAR) {
                const c = window.CLIENTE_A_EDITAR;
                if (document.getElementById('id_cliente')) document.getElementById('id_cliente').value = c.id || o.id_cliente || '';
                if (document.getElementById('nombre_cliente')) document.getElementById('nombre_cliente').value = c.nombre_completo || '';
                if (document.getElementById('telefono_cliente')) document.getElementById('telefono_cliente').value = c.telefono || '';
                if (document.getElementById('buscarCliente')) document.getElementById('buscarCliente').value = c.ci || '';
            }

            // Specs
            if (o.especificaciones) {
                if (document.getElementById('tipo_lente')) document.getElementById('tipo_lente').value = o.especificaciones.tipo_lente || '';
                if (document.getElementById('material')) document.getElementById('material').value = o.especificaciones.material || '';
                if (document.getElementById('marca_lente')) document.getElementById('marca_lente').value = o.especificaciones.marca_lente || '';
                
                // Tratamientos checkboxes
                if (o.especificaciones.tratamientos && Array.isArray(o.especificaciones.tratamientos)) {
                    o.especificaciones.tratamientos.forEach(trat => {
                        const cb = document.querySelector(`input[name="tratamientos[]"][value="${trat}"]`);
                        if (cb) cb.checked = true;
                    });
                }
            }

            // Frame
            if (o.montura) {
                if (document.getElementById('modelo_montura')) document.getElementById('modelo_montura').value = o.montura.modelo || '';
                if (document.getElementById('observaciones_montura')) document.getElementById('observaciones_montura').value = o.montura.observaciones || '';
            }

            // Payments
            if (o.pagos) {
                if (document.getElementById('total')) document.getElementById('total').value = o.pagos.total || '';
                if (document.getElementById('adelanto')) document.getElementById('adelanto').value = o.pagos.adelanto || '';
                if (document.getElementById('saldo')) document.getElementById('saldo').value = o.pagos.saldo || '';
                if (document.getElementById('metodo_pago')) document.getElementById('metodo_pago').value = o.pagos.metodo_pago || 'efectivo';
            }

            // Graduation OD
            if (o.graduacion && o.graduacion.lejos && o.graduacion.lejos.od) {
                if (document.getElementById('od_esf')) document.getElementById('od_esf').value = o.graduacion.lejos.od.esf || '';
                if (document.getElementById('od_cil')) document.getElementById('od_cil').value = o.graduacion.lejos.od.cil || '';
                if (document.getElementById('od_eje')) document.getElementById('od_eje').value = o.graduacion.lejos.od.eje || '';
            }

            // Graduation OI
            if (o.graduacion && o.graduacion.lejos && o.graduacion.lejos.oi) {
                if (document.getElementById('oi_esf')) document.getElementById('oi_esf').value = o.graduacion.lejos.oi.esf || '';
                if (document.getElementById('oi_cil')) document.getElementById('oi_cil').value = o.graduacion.lejos.oi.cil || '';
                if (document.getElementById('oi_eje')) document.getElementById('oi_eje').value = o.graduacion.lejos.oi.eje || '';
            }
            
            // DI / Adicion
            if (o.graduacion && o.graduacion.lejos) {
                if (document.getElementById('di')) document.getElementById('di').value = o.graduacion.lejos.di || '';
            }
            if (o.graduacion && o.graduacion.cerca) {
                if (document.getElementById('adicion')) document.getElementById('adicion').value = o.graduacion.cerca.adicion || '';
            }
            
            // Update action route for the form manually in the submit handler
        }
    }
});

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
    const form = document.getElementById('formEditarOrden') || document.getElementById('formNuevaOrden');
    
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
                document.getElementById('nombre_empleado').value = userProfile.nombre_completo || '';
            }
            
            // Mostrar loading
            const loading = document.getElementById('loading');
            if (loading) {
                loading.style.display = 'flex';
            }
            
            // Preparar datos del formulario
            const formData = new FormData(this);
            const ordenId = window.ORDEN_A_EDITAR ? (window.ORDEN_A_EDITAR.id_orden || window.ORDEN_A_EDITAR.id) : '';
            
            if (!ordenId) {
                alert('No se pudo determinar el ID de la orden.');
                if (loading) loading.style.display = 'none';
                return;
            }

            try {
                const response = await fetch(`/ordenes/${ordenId}/editar`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    if (typeof showNotification === 'function') {
                        showNotification('Orden actualizada exitosamente', 'success');
                    } else {
                        alert('Orden actualizada exitosamente');
                    }
                    if (typeof formModified !== 'undefined') formModified = false;
                    setTimeout(() => {
                        window.location.href = `/ordenes/${result.orden_id || ordenId}`;
                    }, 1000);
                } else {
                    alert('Error al actualizar la orden: ' + result.error);
                }
            } catch (error) {
                alert('Error al actualizar la orden: ' + error.message);
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
