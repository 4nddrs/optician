// Función para inicializar el dashboard
function initDashboard() {
    // 1. Verificación de Rol usando userData global desde base.html
    // Esperar a que userData esté disponible
    let attempts = 0;
    const checkUserInterval = setInterval(() => {
        attempts++;
        
        // userData se declara y carga en base.html
        if (typeof userData !== 'undefined' && userData && userData.rol) {
            clearInterval(checkUserInterval);
            
            if (userData.rol !== 'admin') {
                document.getElementById('access-denied').classList.remove('hidden');
                return;
            } else {
                document.getElementById('dashboard-container').style.display = 'block';
                
                // Initialize UI Elements
                initTabs();
                
                // Load initial data
                loadDashboardData();

                // Setup event listeners for filters
                document.getElementById('filter-date').addEventListener('change', loadDashboardData);
                document.getElementById('filter-branch').addEventListener('change', loadDashboardData);
                const employeeSearch = document.getElementById('employee-search');
                if (employeeSearch && !employeeSearch.hasAttribute('data-listener')) {
                    employeeSearch.addEventListener('input', renderEmployeeRankingFromCache);
                    employeeSearch.setAttribute('data-listener', 'true');
                }
            }
        } else if (attempts > 50) {
            // Timeout después de 5 segundos (50 × 100ms)
            clearInterval(checkUserInterval);
            document.getElementById('access-denied').classList.remove('hidden');
        }
    }, 100);
}

// Ejecutar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    // El DOM ya está listo (script se cargó al final)
    initDashboard();
}


// Chart instances
let charts = {};

// Default Chart.js settings for dark mode
Chart.defaults.color = '#9ca3af';
Chart.defaults.borderColor = '#374151';

function initTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    if (!tabs.length) return;

    tabs.forEach(tab => {
        if (tab.hasAttribute('data-tab-listener')) return;
        tab.addEventListener('click', () => switchDashboardTab(tab.dataset.tab));
        tab.setAttribute('data-tab-listener', 'true');
    });

    // Ensure a tab is visible even if the browser misses initial state
    switchDashboardTab(document.querySelector('.tab-btn.active')?.dataset.tab || 'finanzas');
}

function switchDashboardTab(tabName) {
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    contents.forEach(content => {
        const isTarget = content.id === `tab-${tabName}`;
        content.classList.toggle('active', isTarget);
        content.classList.toggle('hidden', !isTarget);
    });
}

async function loadDashboardData() {
    try {
        const response = await fetch('/api/control/datos');
        if (!response.ok) throw new Error('Network error: ' + response.status);
        const data = await response.json();
        
        console.log('📊 Dashboard Data:', data);
        
        if (data.success) {
            if (data.sucursales) populateBranchFilter(data.sucursales);
            if (data.ordenes) {
                console.log(`📋 Total órdenes recibidas: ${data.ordenes.length}`);
                processAndRenderDashboard(data);
            } else {
                console.warn('⚠️ No hay órdenes en la respuesta');
            }
        } else {
            console.error('❌ API Error:', data.error);
        }
    } catch (e) {
        console.error('❌ Error fetching dashboard data:', e);
    }
}

let branchesPopulated = false;
let employeeDashboardCache = {
    employees: [],
    salesByEmployee: {},
    selectedEmployeeId: null
};

function populateBranchFilter(sucursales) {
    if (branchesPopulated) return;
    const select = document.getElementById('filter-branch');
    if (!select || !Array.isArray(sucursales)) return;
    sucursales.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.nombre;
        select.appendChild(opt);
    });
    branchesPopulated = true;
}

function processAndRenderDashboard(data) {
    const timeFilter = document.getElementById('filter-date').value;
    const branchFilter = document.getElementById('filter-branch').value;
    
    const now = new Date();
    
    // Filter Orders
    let filteredOrders = data.ordenes.filter(o => {
        // Evaluate Branch filter
        if (branchFilter !== 'all' && String(o.id_sucursal || '') !== String(branchFilter)) return false;
        
        // Evaluate Time filter
        if (timeFilter !== 'todo') {
            const creacionStr = o.fecha_creacion || '';
            const orderDate = new Date(creacionStr);
            if (isNaN(orderDate)) return true; // fallback
            
            if (timeFilter === 'hoy') {
                if (orderDate.toDateString() !== now.toDateString()) return false;
            } else if (timeFilter === 'semana') {
                const firstDayOfWeek = new Date(now);
                firstDayOfWeek.setDate(now.getDate() - now.getDay());
                firstDayOfWeek.setHours(0, 0, 0, 0);
                if (orderDate < firstDayOfWeek) return false;
            } else if (timeFilter === 'mes') {
                if (orderDate.getMonth() !== now.getMonth() || orderDate.getFullYear() !== now.getFullYear()) return false;
            }
        }
        return true;
    });

    calculateKPIs(filteredOrders);
    renderFinanzas(filteredOrders);
    renderSucursalesEquipo(filteredOrders, data.sucursales, data.usuarios);
    renderTendencias(filteredOrders);
}

function calculateKPIs(orders) {
    let ingresos = 0;
    let saldos = 0;
    let enTaller = 0;

    if (!orders || orders.length === 0) {
        console.warn('⚠️ No hay órdenes para calcular KPIs');
    }

    orders.forEach(o => {
        try {
            const p = o.pagos || {};
            const total = parseFloat(p.total || 0);
            const saldo = parseFloat(p.saldo || 0);
            
            ingresos += total;
            saldos += saldo;
            
            const estado = (o.estado || '').toLowerCase();
            if (['proceso', 'pendiente', 'en_taller', 'progreso'].includes(estado)) {
                enTaller++;
            }
        } catch (err) {
            console.warn('⚠️ Error procesando orden:', o, err);
        }
    });

    console.log(`💰 KPIs - Ingresos: ${ingresos}, Saldos: ${saldos}, En Taller: ${enTaller}`);

    document.getElementById('kpi-ingresos').textContent = `Bs. ${ingresos.toFixed(2)}`;
    document.getElementById('kpi-saldos').textContent = `Bs. ${saldos.toFixed(2)}`;
    document.getElementById('kpi-taller').textContent = enTaller;
}

// ============== RENDERIZADO DE GRÁFICOS ==============

function renderFinanzas(orders) {
    // 1. Tendencia de Ingresos
    // Agrupar por fecha
    const dates = {};
    orders.forEach(o => {
        if (!o.fecha_creacion) return;
        const d = o.fecha_creacion.split('T')[0];
        if (!dates[d]) dates[d] = 0;
        dates[d] += parseFloat(o.pagos?.total || 0);
    });

    const sortedDates = Object.keys(dates).sort();
    const trendLabels = sortedDates;
    const trendData = sortedDates.map(d => dates[d]);

    if (charts.tendencia) charts.tendencia.destroy();
    const ctxTrend = document.getElementById('chart-tendencia-ingresos').getContext('2d');
    
    // Crear gradiente para el glow
    let gradient = ctxTrend.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.5)'); // Verde neón
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    charts.tendencia = new Chart(ctxTrend, {
        type: 'line',
        data: {
            labels: trendLabels.length ? trendLabels : ['Sin datos'],
            datasets: [{
                label: 'Volumen de Ventas (Bs.)',
                data: trendData.length ? trendData : [0],
                borderColor: '#10b981', // Neon green
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: '#10b981',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#10b981',
                fill: true,
                tension: 0.4 // Curva suave
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, grid: { color: '#374151' } }
            }
        }
    });

    // 2. Metodos de pago
    const metodos = {};
    orders.forEach(o => {
        const m = (o.pagos?.metodo_pago || 'efectivo').toLowerCase();
        if (!metodos[m]) metodos[m] = 0;
        metodos[m]++;
    });

    if (charts.metodos) charts.metodos.destroy();
    charts.metodos = new Chart(document.getElementById('chart-metodos-pago'), {
        type: 'doughnut',
        data: {
            labels: Object.keys(metodos).length ? Object.keys(metodos) : ['Ninguno'],
            datasets: [{
                data: Object.keys(metodos).length ? Object.values(metodos) : [1],
                backgroundColor: ['#0ea5e9', '#8b5cf6', '#f59e0b', '#10b981'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { position: 'right', labels: { color: '#e5e7eb', padding: 20 } }
            }
        }
    });

    // 3. Comparación Dinero Ingresado vs Saldo Pendiente
    let totalIngresos = 0;
    let totalSaldo = 0;

    orders.forEach(o => {
        totalIngresos += parseFloat(o.pagos?.total || 0);
        totalSaldo += parseFloat(o.pagos?.saldo || 0);
    });

    if (charts.cashVsPending) charts.cashVsPending.destroy();
    charts.cashVsPending = new Chart(document.getElementById('chart-cash-vs-pending'), {
        type: 'bar',
        data: {
            labels: ['Dinero Ingresado', 'Saldo Pendiente'],
            datasets: [{
                label: 'Bs.',
                data: [totalIngresos, totalSaldo],
                backgroundColor: ['#10b981', '#f59e0b'],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true }
            }
        }
    });

    // 4. Proporción Ingresos/Saldos
    const totalGeneral = totalIngresos + totalSaldo;
    
    if (charts.ratioChart) charts.ratioChart.destroy();
    charts.ratioChart = new Chart(document.getElementById('chart-ingresos-saldos-ratio'), {
        type: 'doughnut',
        data: {
            labels: ['Pagado', 'Por Cobrar'],
            datasets: [{
                data: [totalIngresos, totalSaldo],
                backgroundColor: ['#10b981', '#f59e0b'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: { position: 'right', labels: { color: '#e5e7eb', padding: 20 } },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const value = context.parsed;
                            const percent = ((value / totalGeneral) * 100).toFixed(1);
                            return `${context.label}: Bs. ${value.toFixed(2)} (${percent}%)`;
                        }
                    }
                }
            }
        },
        plugins: [{
            id: 'textCenter',
            beforeDatasetsDraw(chart) {
                const { width, height, ctx } = chart;
                ctx.restore();
                
                const fontSize = (height / 200).toFixed(2);
                ctx.font = `bold ${fontSize}em sans-serif`;
                ctx.textBaseline = 'middle';
                ctx.textAlign = 'center';
                ctx.fillStyle = '#e5e7eb';
                
                const text = `Total: Bs. ${totalGeneral.toFixed(2)}`;
                const textX = width / 3.5;
                const textY = height / 16;
                
                ctx.fillText(text, textX, textY);
                ctx.save();
            }
        }]
    });
}

function renderSucursalesEquipo(orders, sucursalesAll, usuarios) {
    // 1. Ingresos por Sucursal
    const sucursalTotales = {};
    const sucursalNombres = {};
    const sucursalConteos = {};
    
    (sucursalesAll || []).forEach(s => {
        sucursalTotales[s.id] = 0;
        sucursalNombres[s.id] = s.nombre;
        sucursalConteos[s.id] = 0;
    });

    orders.forEach(o => {
        const sid = String(o.id_sucursal || '');
        if (sid && sucursalTotales[sid] !== undefined) {
            sucursalTotales[sid] += parseFloat(o.pagos?.total || o.total || 0);
            sucursalConteos[sid] += 1;
        }
    });

    const sucLabels = Object.keys(sucursalTotales).map(k => sucursalNombres[k]);
    const sucData = Object.keys(sucursalTotales).map(k => sucursalTotales[k]);
    const branchSummary = document.getElementById('branch-summary');

    if (branchSummary) {
        const orderedBranches = Object.keys(sucursalTotales)
            .map(id => ({ id, nombre: sucursalNombres[id], total: sucursalTotales[id], count: sucursalConteos[id] }))
            .sort((a, b) => b.total - a.total);

        branchSummary.innerHTML = orderedBranches.length
            ? orderedBranches.map((branch, index) => `
                <div class="summary-card">
                    <div>
                        <strong>${index + 1}. ${branch.nombre}</strong><br>
                        <span>${branch.count} órdenes</span>
                    </div>
                    <strong>Bs. ${branch.total.toFixed(2)}</strong>
                </div>
            `).join('')
            : '<p class="ranking-empty">No hay sucursales con movimientos en este periodo.</p>';
    }

    if (charts.sucursales) charts.sucursales.destroy();
    charts.sucursales = new Chart(document.getElementById('chart-sucursales'), {
        type: 'bar',
        data: {
            labels: sucLabels.length ? sucLabels : ['Sin datos'],
            datasets: [{
                label: 'Ingresos (Bs)',
                data: sucData.length ? sucData : [0],
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true }
            }
        }
    });

    // 2. Ranking de Empleados
    const empleadoTotales = {};
    const ventasPorEmpleado = {};
    const empleadosPorId = {};

    (usuarios || []).forEach(u => {
        const empleadoKey = String(u?.uid || u?.id || u?.id_empleado || '');
        if (empleadoKey) {
            empleadosPorId[empleadoKey] = u;
        }
    });

    orders.forEach(o => {
        const eId = String(o.id_empleado || o.empleado_id || o.id_usuario || '');
        if (!eId) return;
        if (!ventasPorEmpleado[eId]) ventasPorEmpleado[eId] = [];

        ventasPorEmpleado[eId].push({
            id_orden: o.id_orden || o.id || 'Sin ID',
            correlativo: o.nro_correlativo || o.correlativo || '-',
            fecha_creacion: o.fecha_creacion || '',
            sucursal: sucursalNombres[String(o.id_sucursal || '')] || o.id_sucursal || 'Sin sucursal',
            total: parseFloat(o.pagos?.total || o.total || 0),
            saldo: parseFloat(o.pagos?.saldo || o.saldo || 0),
            estado: o.estado || 'sin_estado'
        });

        if (!empleadoTotales[eId]) {
            const empleadoBase = empleadosPorId[eId] || {};
            empleadoTotales[eId] = {
                total: 0,
                count: 0,
                nombre: o.nombre_empleado || o.nombre_usuario || o.nombre || empleadoBase.nombre || empleadoBase.nombre_completo || 'Desconocido'
            };
        }
        empleadoTotales[eId].count += 1;
        empleadoTotales[eId].total += parseFloat(o.pagos?.total || o.total || 0);
    });

    const ranking = Object.entries(empleadoTotales)
        .map(([id, data]) => ({ id, ...data }))
        .sort((a, b) => b.count - a.count || b.total - a.total);
    employeeDashboardCache = {
        employees: ranking,
        salesByEmployee: ventasPorEmpleado,
        selectedEmployeeId: employeeDashboardCache.selectedEmployeeId || (ranking[0] ? ranking[0].id : null)
    };

    renderEmployeeRankingFromCache();
}

function renderEmployeeRankingFromCache() {
    const searchInput = document.getElementById('employee-search');
    const query = (searchInput?.value || '').trim().toLowerCase();
    const employees = employeeDashboardCache.employees || [];
    const filtered = query
        ? employees.filter(emp => String(emp.nombre || '').toLowerCase().includes(query))
        : employees;

    const container = document.getElementById('ranking-empleados-container');
    if (!container) return;

    container.innerHTML = '';

    if (filtered.length === 0) {
        container.innerHTML = '<p class="ranking-empty">No se encontraron empleados con ese nombre.</p>';
        renderEmployeeDetail(null);
        return;
    }

    if (!employeeDashboardCache.selectedEmployeeId || !filtered.some(emp => emp.id === employeeDashboardCache.selectedEmployeeId)) {
        employeeDashboardCache.selectedEmployeeId = filtered[0].id;
    }

    const maxCount = filtered[0].count;

    filtered.forEach((emp, index) => {
        const isLeader = index === 0;
        const pCT = maxCount > 0 ? (emp.count / maxCount) * 100 : 0;
        const saleWord = emp.count === 1 ? 'venta' : 'ventas';

        container.innerHTML += `
            <div class="employee-card ${employeeDashboardCache.selectedEmployeeId === emp.id ? 'active' : ''}" data-employee-id="${emp.id}">
                <div class="employee-card-top">
                    <div>
                        <div class="employee-name">${isLeader ? '<i class="fas fa-crown" style="color: #f59e0b; margin-right: 0.4rem;"></i>' : ''}${emp.nombre}</div>
                        <div class="employee-meta">${index + 1}. ${emp.count} ${saleWord} · Bs. ${emp.total.toFixed(2)}</div>
                    </div>
                    <div class="employee-pill">${pCT.toFixed(0)}%</div>
                </div>
                <div class="employee-stats">
                    <div class="employee-pill">${emp.count} ${saleWord}</div>
                    <div class="employee-pill">Bs. ${emp.total.toFixed(2)}</div>
                </div>
                <div class="ranking-track" style="margin-top: 0.85rem; width: 100%;">
                    <div class="ranking-bar" style="width:${pCT}%;"></div>
                </div>
            </div>
        `;
    });

    container.querySelectorAll('.employee-card').forEach(card => {
        if (card.hasAttribute('data-listener')) return;
        card.addEventListener('click', () => {
            employeeDashboardCache.selectedEmployeeId = card.dataset.employeeId;
            renderEmployeeRankingFromCache();
        });
        card.setAttribute('data-listener', 'true');
    });

    const selected = filtered.find(emp => emp.id === employeeDashboardCache.selectedEmployeeId) || filtered[0];
    renderEmployeeDetail(selected);
}

function renderEmployeeDetail(employee) {
    const nameEl = document.getElementById('employee-detail-name');
    const metaEl = document.getElementById('employee-detail-meta');
    const summaryEl = document.getElementById('employee-detail-summary');
    const listEl = document.getElementById('employee-sales-list');

    if (!nameEl || !metaEl || !summaryEl || !listEl) return;

    if (!employee) {
        nameEl.textContent = 'Selecciona un empleado';
        metaEl.textContent = 'Verás aquí el detalle de sus ventas';
        summaryEl.textContent = '0 ventas';
        listEl.innerHTML = '<p class="ranking-empty">Busca o selecciona un empleado para ver sus ventas.</p>';
        return;
    }

    const sales = employeeDashboardCache.salesByEmployee?.[employee.id] || [];
    nameEl.textContent = employee.nombre;
    metaEl.textContent = `Ranking por cantidad de ventas`;
    summaryEl.textContent = `${employee.count} ${employee.count === 1 ? 'venta' : 'ventas'} · Bs. ${employee.total.toFixed(2)}`;

    if (!sales.length) {
        listEl.innerHTML = '<p class="ranking-empty">Este empleado no tiene ventas registradas en el período filtrado.</p>';
        return;
    }

    listEl.innerHTML = sales.map(sale => {
        const fecha = sale.fecha_creacion ? new Date(sale.fecha_creacion).toLocaleDateString('es-BO') : 'Sin fecha';
        return `
            <div class="employee-sale-row">
                <div>
                    <strong>Orden ${sale.id_orden}</strong><br>
                    <span>Correlativo: ${sale.correlativo} · ${fecha}</span><br>
                    <span>Sucursal: ${sale.sucursal} · Estado: ${String(sale.estado).replace(/_/g, ' ')}</span>
                </div>
                <div style="text-align: right;">
                    <strong>Bs. ${sale.total.toFixed(2)}</strong><br>
                    <span>Saldo: Bs. ${sale.saldo.toFixed(2)}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderTendencias(orders) {
    // 1. Tratamientos
    const trats = {};
    const lentes = {};
    const estados = {};
    
    orders.forEach(o => {
        const e = o.especificaciones || {};
        const estado = (o.estado || 'sin_estado').toLowerCase();
        estados[estado] = (estados[estado] || 0) + 1;
        
        // Lentes Totales
        const tl = (e.tipo_lente || 'no_especificado').toLowerCase();
        if (!lentes[tl]) lentes[tl] = 0;
        lentes[tl]++;

        // Tratamientos
        const lista = e.tratamientos || [];
        lista.forEach(t => {
            const n = t.toLowerCase();
            if (!trats[n]) trats[n] = 0;
            trats[n]++;
        });
    });

    // Render Tratamientos
    if (charts.tratamientos) charts.tratamientos.destroy();
    charts.tratamientos = new Chart(document.getElementById('chart-tratamientos'), {
        type: 'bar',
        data: {
            labels: Object.keys(trats).length ? Object.keys(trats) : ['Sin datos'],
            datasets: [{
                label: 'Cantidad de Órdenes',
                data: Object.keys(trats).length ? Object.values(trats) : [0],
                backgroundColor: '#10b981',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { grid: { display: false } }, y: { beginAtZero: true } }
        }
    });

    // Render Tipos de Lentes
    if (charts.lentes) charts.lentes.destroy();
    charts.lentes = new Chart(document.getElementById('chart-lentes'), {
        type: 'pie',
        data: {
            labels: Object.keys(lentes).length ? Object.keys(lentes) : ['Sin datos'],
            datasets: [{
                data: Object.keys(lentes).length ? Object.values(lentes) : [1],
                backgroundColor: ['#f43f5e', '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { color: '#e5e7eb' } } }
        }
    });

    const trendSummary = document.getElementById('trend-summary');
    if (trendSummary) {
        const estadosOrdenados = Object.entries(estados).sort((a, b) => b[1] - a[1]);
        trendSummary.innerHTML = estadosOrdenados.length
            ? estadosOrdenados.map(([estado, cantidad]) => `
                <div class="summary-card">
                    <div>
                        <strong>${estado.replace(/_/g, ' ')}</strong><br>
                        <span>Órdenes por estado</span>
                    </div>
                    <strong>${cantidad}</strong>
                </div>
            `).join('')
            : '<p class="ranking-empty">Sin órdenes para analizar.</p>';
    }
}
