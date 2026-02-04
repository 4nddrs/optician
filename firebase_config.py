import firebase_admin
from firebase_admin import credentials, firestore
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
    'branches': {'data': None, 'timestamp': None}
}
_cache_duration = int(os.getenv('CACHE_DURATION', 60))  # Cache duration from env

def _is_cache_valid(cache_key):
    """Check if cache is still valid"""
    if _cache[cache_key]['timestamp'] is None:
        return False
    elapsed = (datetime.now() - _cache[cache_key]['timestamp']).total_seconds()
    return elapsed < _cache_duration

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

def add_order_to_client(client_id, order_number):
    """Add order number to client history"""
    cliente_ref = db.collection('clientes').document(client_id)
    cliente_ref.update({
        'historial_ordenes': firestore.ArrayUnion([order_number])
    })

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

# Work order functions
def get_all_orders(limit=None):
    """Get all work orders with optional limit"""
    if limit is None:
        limit = int(os.getenv('MAX_ORDERS_LIMIT', 100))
    
    ordenes_ref = db.collection('ordenes_trabajo').order_by('fecha_creacion', direction=firestore.Query.DESCENDING).limit(limit)
    ordenes = []
    for doc in ordenes_ref.stream():
        orden = doc.to_dict()
        orden['id'] = doc.id
        ordenes.append(orden)
    return ordenes

def get_order_by_id(order_id):
    """Get an order by ID"""
    doc = db.collection('ordenes_trabajo').document(order_id).get()
    if doc.exists:
        orden = doc.to_dict()
        orden['id'] = doc.id
        return orden
    return None

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
    # Generate correlative
    nro_correlativo = get_next_correlative(data['id_sucursal'])
    id_orden = f"{data['id_sucursal']}_{nro_correlativo}"
    
    data['id_orden'] = id_orden
    data['nro_correlativo'] = nro_correlativo
    
    # Create the order
    db.collection('ordenes_trabajo').document(id_orden).set(data)
    
    # Update client history
    add_order_to_client(data['id_cliente'], nro_correlativo)
    
    return id_orden

def update_order(order_id, data):
    """Update an existing order"""
    db.collection('ordenes_trabajo').document(order_id).update(data)

def update_order_status(order_id, new_status):
    """Update only the status of an order"""
    db.collection('ordenes_trabajo').document(order_id).update({
        'estado': new_status
    })

def delete_order(order_id):
    """Delete a work order"""
    db.collection('ordenes_trabajo').document(order_id).delete()
