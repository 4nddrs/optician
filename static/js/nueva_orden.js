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

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Interpreta el texto buscado para pre-cargar el formulario de cliente
function buildClienteFromSearch(value) {
    const query = (value || '').trim();
    if (!query) return {};
    if (/^[0-9][0-9\-.\s]*$/.test(query)) {
        return { ci: query };
    }
    return { nombre_completo: query };
}

function openNuevoClienteModal(prefill, hint) {
    const modal = document.getElementById('nuevoClienteModal');
    if (!modal) return;

    const datos = prefill || {};

    document.getElementById('ncCi').value = datos.ci || '';
    document.getElementById('ncNombre').value = datos.nombre_completo || '';
    document.getElementById('ncTelefono').value = datos.telefono || '';

    const hintEl = document.getElementById('nuevoClienteHint');
    if (hintEl) {
        hintEl.textContent = hint || '';
        hintEl.style.display = hint ? 'block' : 'none';
    }

    const errorEl = document.getElementById('nuevoClienteError');
    if (errorEl) {
        errorEl.textContent = '';
        errorEl.style.display = 'none';
    }

    hideClientSuggestions();
    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');

    const nombreInput = document.getElementById('ncNombre');
    if (nombreInput) {
        nombreInput.focus();
    }
}

function closeNuevoClienteModal() {
    const modal = document.getElementById('nuevoClienteModal');
    if (!modal) return;

    modal.classList.remove('show');
    modal.setAttribute('aria-hidden', 'true');
}

function showNuevoClienteError(message) {
    const errorEl = document.getElementById('nuevoClienteError');
    if (!errorEl) return;

    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

async function crearClienteDesdeOrden(event) {
    event.preventDefault();

    const saveBtn = document.getElementById('saveNuevoClienteBtn');
    const originalHtml = saveBtn ? saveBtn.innerHTML : '';

    const datos = {
        ci: document.getElementById('ncCi').value.trim(),
        nombre_completo: document.getElementById('ncNombre').value.trim(),
        telefono: document.getElementById('ncTelefono').value.trim()
    };

    if (!datos.nombre_completo) {
        showNuevoClienteError('El nombre completo es obligatorio');
        return;
    }

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creando...';
    }

    try {
        const formData = new FormData();
        formData.append('ci', datos.ci);
        formData.append('nombre_completo', datos.nombre_completo);
        formData.append('telefono', datos.telefono);

        const response = await fetch('/clientes/nuevo', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (!result.success) {
            showNuevoClienteError(result.error || 'No se pudo crear el cliente');
            return;
        }

        // El cliente queda seleccionado en la orden y el formulario de la orden no se toca
        fillClientFields({
            id: result.cliente_id,
            ci: datos.ci,
            nombre_completo: datos.nombre_completo,
            telefono: datos.telefono
        }, true);

        closeNuevoClienteModal();

        if (typeof showNotification === 'function') {
            showNotification('Cliente registrado. Continúa con la orden.', 'success');
        }
    } catch (error) {
        console.error('Error al crear el cliente:', error);
        showNuevoClienteError('Error de conexión al crear el cliente');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalHtml;
        }
    }
}

// Sugerencia para crear el cliente cuando la búsqueda no devuelve resultados
function renderNoResultsSuggestion(query) {
    const container = document.getElementById('clientSuggestions');
    if (!container) return;

    clientSuggestions = [];

    const querySeguro = escapeHtml(query);
    container.innerHTML = `
        <button type="button" class="client-suggestion-item is-create" id="crearClienteSuggestion">
            <i class="fas fa-user-plus"></i>
            <span>No se encontró "${querySeguro}". Crear cliente</span>
        </button>
    `;
    container.style.display = 'block';

    const botonCrear = document.getElementById('crearClienteSuggestion');
    if (botonCrear) {
        botonCrear.addEventListener('click', function() {
            openNuevoClienteModal(
                buildClienteFromSearch(query),
                `No se encontró ningún cliente con "${query}". Regístralo aquí para continuar con la orden.`
            );
        });
    }
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

        if (result.success && result.clientes && result.clientes.length > 0) {
            renderClientSuggestions(result.clientes);
            return;
        }

        clearClientSelection({ keepQuery: true });

        if (response.status === 404) {
            // Sin coincidencias: ofrecer crear el cliente sin salir de la vista
            renderNoResultsSuggestion(value);
        } else {
            hideClientSuggestions();
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
    const criterio = inputCI.value.trim();
    
    if (!criterio) {
        alert('Por favor ingrese un CI o nombre');
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
        const response = await fetch(`/api/clientes/buscar?q=${encodeURIComponent(criterio)}`);
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
        } else if (result.success && result.clientes && result.clientes.length > 0) {
            // Varias coincidencias: el usuario elige
            renderClientSuggestions(result.clientes);
        } else {
            // No existe: se crea en esta misma vista y se continúa con la orden
            clearClientSelection({ keepQuery: true });
            openNuevoClienteModal(
                buildClienteFromSearch(criterio),
                `No se encontró ningún cliente con "${criterio}". Regístralo aquí para continuar con la orden.`
            );
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

// Modal para crear un cliente sin salir de la orden
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('nuevoClienteModal');
    const btnNuevoCliente = document.getElementById('btnNuevoCliente');
    const closeBtn = document.getElementById('closeNuevoClienteModal');
    const cancelBtn = document.getElementById('cancelNuevoClienteModal');
    const formNuevoCliente = document.getElementById('formNuevoClienteRapido');

    if (btnNuevoCliente) {
        btnNuevoCliente.addEventListener('click', function(e) {
            e.preventDefault();
            const buscarInput = document.getElementById('buscarCliente');
            openNuevoClienteModal(buildClienteFromSearch(buscarInput ? buscarInput.value : ''));
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeNuevoClienteModal);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeNuevoClienteModal);
    }

    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeNuevoClienteModal();
            }
        });
    }

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('show')) {
            closeNuevoClienteModal();
        }
    });

    if (formNuevoCliente) {
        formNuevoCliente.addEventListener('submit', crearClienteDesdeOrden);
    }
});

// Dynamic form for lens specifications
const materialOptions = {
    organico: [
        { value: 'blanco', label: 'Blanco' },
        { value: 'antireflex', label: 'Antireflex' },
        { value: 'blue_blocker', label: 'Blue Bloker' },
        { value: 'blue_care', label: 'Blue Care' },
        { value: 'blue_verde', label: 'Blue Verde' },
        { value: 'fotocr_ar', label: 'Fotocr. AR' },
        { value: 'fotocr_blue', label: 'Fotocr. Blue' },
        { value: 'transitions', label: 'Transitions' }
    ],
    policarbonato: [
        { value: 'blanco', label: 'Blanco' },
        { value: 'antireflex', label: 'Antireflex' },
        { value: 'blue_blocker', label: 'Blue Bloker' },
        { value: 'blue_care', label: 'Blue Care' },
        { value: 'blue_verde', label: 'Blue Verde' },
        { value: 'fotocr_ar', label: 'Fotocr. AR' },
        { value: 'fotocr_blue', label: 'Fotocr. Blue' },
        { value: 'transitions', label: 'Transitions' }
    ],
    vidrio: [
        { value: 'blanco', label: 'Blanco' },
        { value: 'fotocromatico', label: 'Fotocromático' }
    ]
};

const modeloMultifocalOptions = {
    kodak: [
        { value: 'unique_hd', label: 'Unique HD' },
        { value: 'easy', label: 'Easy' },
        { value: 'precise', label: 'Precise' }
    ],
    varilux: [
        { value: 'physio_30', label: 'Physio 30' },
        { value: 'physio', label: 'Physio' },
        { value: 'confort', label: 'Confort' },
        { value: 'dynamic', label: 'Dynamic' }
    ],
    evolution_xperience: [
        { value: 'evolution_essential', label: 'Evolution Essential' },
        { value: 'evolution_pro', label: 'Evolution Pro' },
        { value: 'evolution_pro_2_0', label: 'Evolution Pro 2.0' },
        { value: 'xperience_ia', label: 'Xperience IA' }
    ]
};

function actualizarMaterialDetalle() {
    const base = document.getElementById('material_base').value;
    const grupoDetalle = document.getElementById('grupo_material_detalle');
    const grupoOtro = document.getElementById('grupo_material_otro');
    const selectDetalle = document.getElementById('material_detalle');

    grupoDetalle.style.display = 'none';
    grupoOtro.style.display = 'none';

    if (base === 'otro') {
        grupoOtro.style.display = 'block';
    } else if (base && materialOptions[base]) {
        grupoDetalle.style.display = 'block';
        selectDetalle.innerHTML = '<option value="">Seleccione...</option>';
        materialOptions[base].forEach(function(opt) {
            selectDetalle.innerHTML += '<option value="' + opt.value + '">' + opt.label + '</option>';
        });
    }
}

function actualizarDisenoLente() {
    const tipo = document.getElementById('tipo_lente').value;
    const grupoBifocal = document.getElementById('grupo_diseno_bifocal');
    const grupoMarca = document.getElementById('grupo_marca_multifocal');
    const grupoModelo = document.getElementById('grupo_modelo_multifocal');

    grupoBifocal.style.display = 'none';
    grupoMarca.style.display = 'none';
    grupoModelo.style.display = 'none';

    if (tipo === 'bifocal') {
        grupoBifocal.style.display = 'block';
    } else if (tipo === 'multifocal') {
        grupoMarca.style.display = 'block';
    }
}

function actualizarModeloMultifocal() {
    const marca = document.getElementById('marca_multifocal').value;
    const grupoModelo = document.getElementById('grupo_modelo_multifocal');
    const selectModelo = document.getElementById('modelo_multifocal');

    if (marca && modeloMultifocalOptions[marca]) {
        grupoModelo.style.display = 'block';
        selectModelo.innerHTML = '<option value="">Seleccione...</option>';
        modeloMultifocalOptions[marca].forEach(function(opt) {
            selectModelo.innerHTML += '<option value="' + opt.value + '">' + opt.label + '</option>';
        });
    } else {
        grupoModelo.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const materialBase = document.getElementById('material_base');
    const tipoLente = document.getElementById('tipo_lente');
    const marcaMultifocal = document.getElementById('marca_multifocal');

    if (materialBase) materialBase.addEventListener('change', actualizarMaterialDetalle);
    if (tipoLente) tipoLente.addEventListener('change', actualizarDisenoLente);
    if (marcaMultifocal) marcaMultifocal.addEventListener('change', actualizarModeloMultifocal);
});

// Combos con opcion "Otro" (vendedora y laboratorio): el combo ofrece la lista de
// la tienda y un campo libre para escribir un valor propio. El campo libre solo se
// muestra (y se exige) cuando se elige "Otro"; el backend ignora su contenido en
// cualquier otro caso.
document.addEventListener('DOMContentLoaded', function() {
    function sincronizarComboOtro(idCombo, idCampoLibre) {
        const combo = document.getElementById(idCombo);
        const campoLibre = document.getElementById(idCampoLibre);
        if (!combo || !campoLibre) return;

        const valorOtro = combo.dataset.otro;

        function sincronizar() {
            const esOtro = combo.value === valorOtro;
            campoLibre.style.display = esOtro ? '' : 'none';
            campoLibre.required = esOtro;
            if (esOtro) campoLibre.focus();
        }

        combo.addEventListener('change', sincronizar);
        sincronizar();
    }

    sincronizarComboOtro('vendedora', 'vendedoraOtro');
    sincronizarComboOtro('laboratorio', 'laboratorioOtro');
});
