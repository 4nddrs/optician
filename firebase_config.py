import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.field_path import FieldPath
import os
import json
from functools import lru_cache
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase
def initialize_firebase():
    if not firebase_admin._apps:
        use_default_credentials = os.getenv('FIREBASE_USE_DEFAULT_CREDENTIALS', 'false').lower() == 'true'
        
        if use_default_credentials:
            # Running in Cloud Functions - use default credentials
            firebase_admin.initialize_app()
        else:
            # Use credentials from environment variables
            cred_dict = {
                "type": os.getenv('FIREBASE_TYPE', 'service_account'),
                "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
                "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
                "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
                "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_CERT_URL'),
                "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL')
            }
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
    
    return firestore.client()

# Get Firestore client
db = initialize_firebase()

# Simple cache timestamp
_cache = {
    'clients': {'data': None, 'timestamp': None},
    'branches': {'data': None, 'timestamp': None},
    'orders': {'data': None, 'timestamp': None},
    'order_totals': {'data': None, 'timestamp': None}
}
_cache_duration = int(os.getenv('CACHE_DURATION', 60))  # Cache duration from env

def _is_cache_valid(cache_key):
    """Check if cache is still valid"""
    if _cache[cache_key]['timestamp'] is None:
        return False
    elapsed = (datetime.now() - _cache[cache_key]['timestamp']).total_seconds()
    return elapsed < _cache_duration


def _invalidate_orders_cache():
    """Descarta la lista de órdenes y sus totales agregados.

    Toda escritura de orden debe llamar a esto para que una orden recién creada
    aparezca de inmediato y los contadores del dashboard no queden desfasados.
    """
    for clave in ('orders', 'order_totals'):
        _cache[clave]['timestamp'] = None


# Estados canónicos de una orden de trabajo. Fuente única para validar (S3) y
# contar (S2); no duplicar esta lista en otras capas.
ESTADOS_ORDEN = ['Pendiente', 'Progreso', 'Listo', 'Entregado']

# Client functions
def get_all_clients():
    """Get all clients with cache"""
    if _is_cache_valid('clients'):
        return _cache['clients']['data']
    
    clientes_ref = db.collection('clientes')
    clientes = []
    for doc in clientes_ref.stream():
        cliente = doc.to_dict()
        cliente['id'] = doc.id
        clientes.append(cliente)
    
    _cache['clients']['data'] = clientes
    _cache['clients']['timestamp'] = datetime.now()
    return clientes

def get_client_by_id(client_id):
    """Get a client by ID"""
    doc = db.collection('clientes').document(client_id).get()
    if doc.exists:
        cliente = doc.to_dict()
        cliente['id'] = doc.id
        return cliente
    return None

def get_client_by_ci(ci):
    """Search client by CI"""
    clientes_ref = db.collection('clientes').where('ci', '==', ci).limit(1)
    for doc in clientes_ref.stream():
        cliente = doc.to_dict()
        cliente['id'] = doc.id
        return cliente
    return None

def get_user_by_id(user_id):
    """Get a user by their UID from the 'usuarios' collection."""
    if not user_id:
        return None
    try:
        doc = db.collection('usuarios').document(user_id).get()
        if doc.exists:
            user = doc.to_dict()
            user['id'] = doc.id
            return user
        return None
    except Exception as e:
        print(f"Error getting user by ID {user_id}: {e}")
        return None

def create_client(data):
    """Create a new client"""
    doc_ref = db.collection('clientes').document()
    data['historial_ordenes'] = []
    doc_ref.set(data)
    # Invalidate cache
    _cache['clients']['timestamp'] = None
    return doc_ref.id

def update_client(client_id, data):
    """Update an existing client"""
    db.collection('clientes').document(client_id).update(data)
    # Invalidate cache
    _cache['clients']['timestamp'] = None

def add_order_to_client(client_id, order_id):
    """Add order ID to client history"""
    cliente_ref = db.collection('clientes').document(client_id)
    cliente_ref.update({
        'historial_ordenes': firestore.ArrayUnion([order_id])
    })
    # Invalidate cache
    _invalidate_orders_cache()

# Branch functions
def get_all_branches():
    """Get all branches with cache"""
    if _is_cache_valid('branches'):
        return _cache['branches']['data']
    
    sucursales_ref = db.collection('sucursales')
    sucursales = []
    for doc in sucursales_ref.stream():
        sucursal = doc.to_dict()
        sucursal['id'] = doc.id
        sucursales.append(sucursal)
    
    _cache['branches']['data'] = sucursales
    _cache['branches']['timestamp'] = datetime.now()
    return sucursales

def get_branch_by_id(branch_id):
    """Get a branch by ID"""
    doc = db.collection('sucursales').document(branch_id).get()
    if doc.exists:
        sucursal = doc.to_dict()
        sucursal['id'] = doc.id
        return sucursal
    return None

def create_branch(branch_id, data):
    """Create a new branch using the provided branch ID."""
    db.collection('sucursales').document(branch_id).set(data)
    _cache['branches']['timestamp'] = None
    return branch_id

def update_branch(branch_id, data):
    """Update an existing branch."""
    db.collection('sucursales').document(branch_id).update(data)
    _cache['branches']['timestamp'] = None
    return branch_id

# Work order functions
def get_all_orders(limit=None):
    """Get all work orders with optional limit.

    Sin `limit` explícito se cachea con TTL igual que clientes y sucursales;
    con `limit` se consulta directo porque es una vista parcial.
    """
    cacheable = limit is None
    if cacheable:
        if _is_cache_valid('orders'):
            return _cache['orders']['data']
        limit = int(os.getenv('MAX_ORDERS_LIMIT', 100))

    ordenes_ref = db.collection('ordenes_trabajo').order_by('fecha_creacion', direction=firestore.Query.DESCENDING).limit(limit)
    ordenes = []
    for doc in ordenes_ref.stream():
        orden = doc.to_dict()
        orden['id'] = doc.id
        ordenes.append(orden)

    if cacheable:
        _cache['orders']['data'] = ordenes
        _cache['orders']['timestamp'] = datetime.now()
    return ordenes


# Tamaño de página de /ordenes (S7). Configurable por entorno.
ORDENES_PAGE_SIZE = int(os.getenv('ORDENES_PAGE_SIZE', 25))


def _clave_fecha_creacion(orden):
    """Clave de ordenamiento por fecha, tolerante a str ISO y a datetime."""
    valor = orden.get('fecha_creacion')
    if hasattr(valor, 'isoformat'):
        return valor.isoformat()
    return valor or ''


def get_orders_page(estado=None, sucursal=None, q=None, page=1, page_size=None):
    """Página de órdenes con los filtros aplicados en el servidor (S7).

    Devuelve un dict con las órdenes de la página pedida, el total de
    coincidencias y los metadatos de paginación que consume la plantilla.

    Invariante: filtrar por un estado devuelve TODAS las órdenes de ese estado
    repartidas en páginas; el conjunto filtrado nunca se recorta. Sin filtros la
    lectura se acota a MAX_ORDERS_LIMIT y se cachea con TTL, como antes.

    Nota de índices (medido): Firestore exige un índice compuesto para combinar
    `where('estado', '==', ...)` con `order_by('fecha_creacion')`. Ese índice no
    existe en el proyecto y la consulta nativa falla con FailedPrecondition
    ("The query requires an index"), así que aquí se optó por:
      - aplicar los filtros de igualdad en Firestore, que sí resuelve con los
        índices de campo único automáticos (los combina por index merging);
      - resolver el orden por fecha y el corte de página en el servidor de la
        aplicación.
    Es un compromiso deliberado y documentado: se lee el conjunto que casa con
    el filtro (no solo la página visible), lo que es correcto y acotado por el
    propio filtro. Cuando el índice compuesto exista, el corte puede moverse a
    Firestore con `.order_by('fecha_creacion').start_after(...)`.
    """
    page_size = int(page_size or ORDENES_PAGE_SIZE)
    page = max(1, int(page or 1))

    estado = (estado or '').strip()
    sucursal = (sucursal or '').strip()
    q = (q or '').strip()

    # Un estado fuera de ESTADOS_ORDEN no es un filtro válido: se ignora en vez
    # de aplicarlo a ciegas. ESTADOS_ORDEN es la única fuente de estados válidos.
    if estado and estado not in ESTADOS_ORDEN:
        estado = ''

    con_filtros = bool(estado or sucursal or q)

    # Sin `where()` nada acota la lectura en Firestore y `consulta.stream()`
    # recorría `ordenes_trabajo` ENTERA en cada carga de página: se reutiliza la
    # lectura acotada y cacheada de get_all_orders() (MAX_ORDERS_LIMIT + TTL).
    if not (estado or sucursal):
        ordenes = list(get_all_orders())
    else:
        consulta = db.collection('ordenes_trabajo')
        if estado:
            consulta = consulta.where('estado', '==', estado)
        if sucursal:
            consulta = consulta.where('id_sucursal', '==', sucursal)

        ordenes = []
        for doc in consulta.stream():
            orden = doc.to_dict()
            orden['id'] = doc.id
            ordenes.append(orden)

    if q:
        busqueda = q.lower()
        ordenes = [o for o in ordenes if busqueda in (o.get('id_orden') or '').lower()]

    if con_filtros:
        # Orden por fecha en el servidor de la aplicación: ver nota de índices.
        ordenes.sort(key=_clave_fecha_creacion, reverse=True)

    total = len(ordenes)
    total_paginas = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_paginas)
    inicio = (page - 1) * page_size

    return {
        'ordenes': ordenes[inicio:inicio + page_size],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_paginas,
        'has_prev': page > 1,
        'has_next': page < total_paginas,
    }


def get_order_totals():
    """Totales de órdenes para el dashboard, con la agregación count() de Firestore.

    Dos consultas (total sin filtro y entregadas) en vez de traer documentos, así
    el resultado no depende del tope MAX_ORDERS_LIMIT. `pendientes` se deriva en
    el llamador como total - entregadas, para que la invariante se cumpla por
    construcción.

    Se cachea con el mismo TTL que las órdenes porque medimos que las
    agregaciones count() se degradan al repetirse (~250 ms la primera, ~850 ms la
    segunda), así que no deben ejecutarse en cada carga del dashboard.
    """
    if _is_cache_valid('order_totals'):
        return _cache['order_totals']['data']

    ordenes_ref = db.collection('ordenes_trabajo')

    def _total():
        return int(ordenes_ref.count().get()[0][0].value or 0)

    def _entregadas():
        return int(ordenes_ref.where('estado', '==', 'Entregado').count().get()[0][0].value or 0)

    total, entregadas = _total(), _entregadas()
    totales = {'total': total, 'entregadas': entregadas}
    _cache['order_totals']['data'] = totales
    _cache['order_totals']['timestamp'] = datetime.now()
    return totales

def get_order_by_id(order_id):
    """Get an order by ID"""
    doc = db.collection('ordenes_trabajo').document(order_id).get()
    if doc.exists:
        orden = doc.to_dict()
        orden['id'] = doc.id
        return orden
    return None

def get_orders_by_ids(order_ids):
    """Get multiple orders by their IDs, preserving the provided order.

    Usa consultas `in` por lotes de hasta 30 (límite de Firestore) en vez de un
    read por orden, deduplicando los ids y saltando los vacíos o inexistentes.
    """
    ids_unicos = []
    vistos = set()
    for order_id in order_ids or []:
        if not order_id or order_id in vistos:
            continue
        vistos.add(order_id)
        ids_unicos.append(order_id)

    if not ids_unicos:
        return []

    encontrados = {}
    for inicio in range(0, len(ids_unicos), 30):
        lote = ids_unicos[inicio:inicio + 30]
        ordenes_ref = db.collection('ordenes_trabajo').where(
            FieldPath.document_id(), 'in', lote
        )
        for doc in ordenes_ref.stream():
            orden = doc.to_dict()
            orden['id'] = doc.id
            encontrados[doc.id] = orden

    return [encontrados[oid] for oid in ids_unicos if oid in encontrados]

def get_orders_by_branch(branch_id):
    """Get orders filtered by branch"""
    ordenes_ref = db.collection('ordenes_trabajo').where('id_sucursal', '==', branch_id)
    ordenes = []
    for doc in ordenes_ref.stream():
        orden = doc.to_dict()
        orden['id'] = doc.id
        ordenes.append(orden)
    return ordenes

def get_orders_by_status(status):
    """Get orders filtered by status"""
    ordenes_ref = db.collection('ordenes_trabajo').where('estado', '==', status)
    ordenes = []
    for doc in ordenes_ref.stream():
        orden = doc.to_dict()
        orden['id'] = doc.id
        ordenes.append(orden)
    return ordenes

def get_next_correlative(branch_id):
    """Get next correlative number for a branch"""
    ordenes_ref = db.collection('ordenes_trabajo').where('id_sucursal', '==', branch_id).stream()
    
    max_correlative = 0
    for doc in ordenes_ref:
        correlativo = doc.to_dict().get('nro_correlativo', 0)
        if correlativo > max_correlative:
            max_correlative = correlativo
    
    return max_correlative + 1

def create_order(data):
    """Create a new work order"""
    # Generate or use the provided correlative
    requested_correlative = data.get('nro_correlativo')
    if requested_correlative in (None, ''):
        nro_correlativo = get_next_correlative(data['id_sucursal'])
    else:
        nro_correlativo = int(requested_correlative)
        if nro_correlativo < 1:
            raise ValueError('El correlativo debe ser mayor que cero')

    id_orden = f"{data['id_sucursal']}_{nro_correlativo}"

    existing_order = db.collection('ordenes_trabajo').document(id_orden).get()
    if existing_order.exists:
        raise ValueError('Ya existe una orden con ese correlativo en la sucursal seleccionada')
    
    data['id_orden'] = id_orden
    data['nro_correlativo'] = nro_correlativo
    
    # Create the order
    db.collection('ordenes_trabajo').document(id_orden).set(data)
    
    # Update client history
    add_order_to_client(data['id_cliente'], id_orden)

    # Invalidate cache
    _invalidate_orders_cache()

    return id_orden

def update_order(order_id, data):
    """Update an existing order"""
    db.collection('ordenes_trabajo').document(order_id).update(data)
    # Invalidate cache
    _invalidate_orders_cache()

def update_order_status(order_id, new_status):
    """Update only the status of an order"""
    db.collection('ordenes_trabajo').document(order_id).update({
        'estado': new_status
    })
    # Invalidate cache
    _invalidate_orders_cache()

def delete_order(order_id):
    """Delete a work order"""
    db.collection('ordenes_trabajo').document(order_id).delete()
    # Invalidate cache
    _invalidate_orders_cache()
