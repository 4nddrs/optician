// Functions for orders page

// Change order status
function cambiarEstado(ordenId) {
    document.getElementById('ordenIdEstado').value = ordenId;
    showModal('modalEstado');
}

// Save new status
async function guardarEstado() {
    const ordenId = document.getElementById('ordenIdEstado').value;
    const nuevoEstado = document.getElementById('nuevoEstado').value;
    
    if (!nuevoEstado) {
        alert('Por favor seleccione un estado');
        return;
    }
    
    try {
        const response = await fetch(`/api/ordenes/${ordenId}/estado`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Estado actualizado correctamente', 'success');
            closeModal('modalEstado');
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error al actualizar el estado: ' + error.message);
    }
}

// Confirm deletion
function confirmarEliminar(ordenId) {
    document.getElementById('ordenIdEliminar').value = ordenId;
    showModal('modalEliminar');
}

// Delete order
async function eliminarOrden() {
    const ordenId = document.getElementById('ordenIdEliminar').value;
    
    try {
        const response = await fetch(`/api/ordenes/${ordenId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Orden eliminada correctamente', 'success');
            closeModal('modalEliminar');
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error al eliminar la orden: ' + error.message);
    }
}

// Filters are applied server-side (S7). The filter controls are a GET form, so
// the server filters and paginates and the browser just reloads the page. The
// old client-side filter hid rows of the already-rendered page, which would
// silently hide matches outside the visible page once pagination exists.
document.addEventListener('DOMContentLoaded', function() {
    const formFiltros = document.getElementById('formFiltros');
    if (!formFiltros) {
        return;
    }

    // Changing a select submits the form right away; the search box submits
    // with the "Filtrar" button or by pressing Enter.
    ['filterEstado', 'filterSucursal'].forEach(function(id) {
        const select = document.getElementById(id);
        if (select) {
            select.addEventListener('change', function() {
                formFiltros.submit();
            });
        }
    });
});

// Send WhatsApp message
function enviarWhatsApp(telefono, nombreCliente, estado, fechaEntrega, ordenId, nombreSucursal = '', direccionSucursal = '', ubicacionSucursal = '') {
    // Format phone number (add +591 prefix if not present)
    let numeroFormateado = telefono.replace(/\D/g, ''); // Remove non-digits
    if (!numeroFormateado.startsWith('591')) {
        numeroFormateado = '591' + numeroFormateado;
    }
    
    // Translate status to Spanish friendly text
    const estadosTexto = {
    'Pendiente': '*registrado y pendiente de procesamiento*',
    'Progreso': '*en proceso de elaboración*',
    'Listo': '*listo para su entrega*',
    'Entregado': '*entregado correctamente*'
};
    
    const estadoTexto = estadosTexto[estado] || estado.toUpperCase();

    const detalleSucursal = nombreSucursal || direccionSucursal || ubicacionSucursal
        ? `
Sucursal: ${nombreSucursal || 'No especificada'}
Dirección: ${direccionSucursal || 'No especificada'}
Ubicación: ${ubicacionSucursal || 'No especificada'}
`
        : '';
    
    // Create message without emojis to avoid encoding issues
    const mensaje = `Hola ${nombreCliente},

Gracias por elegir Óptica V-CLARO.

Queremos informarle que su pedido se encuentra ${estadoTexto}.

N.º de orden: ${ordenId}
Fecha de entrega: ${fechaEntrega}

${detalleSucursal}

Le esperamos en nuestra sucursal para la entrega de su pedido en la fecha indicada.

Muchas gracias por su preferencia.

Óptica V-CLARO`;
    
    // Encode message for URL
    const mensajeCodificado = encodeURIComponent(mensaje);
    
    // Create WhatsApp URL
    const urlWhatsApp = `https://wa.me/${numeroFormateado}?text=${mensajeCodificado}`;
    
    // Open WhatsApp
    window.open(urlWhatsApp, '_blank');
}
