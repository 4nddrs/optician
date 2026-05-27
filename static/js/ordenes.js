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

// Filter orders
document.addEventListener('DOMContentLoaded', function() {
    const filterEstado = document.getElementById('filterEstado');
    const filterSucursal = document.getElementById('filterSucursal');
    const searchOrden = document.getElementById('searchOrden');
    
    if (filterEstado && filterSucursal && searchOrden) {
        function filtrarOrdenes() {
            const estadoSeleccionado = filterEstado.value.toLowerCase();
            const sucursalSeleccionada = filterSucursal.value.toLowerCase();
            const busqueda = searchOrden.value.toLowerCase();
            
            const rows = document.querySelectorAll('#ordenesTableBody tr');
            
            rows.forEach(row => {
                const estado = row.dataset.estado ? row.dataset.estado.toLowerCase() : '';
                const sucursal = row.dataset.sucursal ? row.dataset.sucursal.toLowerCase() : '';
                const ordenId = row.dataset.ordenId ? row.dataset.ordenId.toLowerCase() : '';
                
                const matchEstado = !estadoSeleccionado || estado === estadoSeleccionado;
                const matchSucursal = !sucursalSeleccionada || sucursal === sucursalSeleccionada;
                const matchBusqueda = !busqueda || ordenId.includes(busqueda);
                
                if (matchEstado && matchSucursal && matchBusqueda) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        filterEstado.addEventListener('change', filtrarOrdenes);
        filterSucursal.addEventListener('change', filtrarOrdenes);
        searchOrden.addEventListener('input', filtrarOrdenes);
    }
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
