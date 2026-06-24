from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g, abort
from datetime import datetime, timedelta
import firebase_config as fb
import firebase_auth as fa
import firebase_admin
import os
import logging
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()


def _is_local_development():
    flask_env = os.getenv('FLASK_ENV', 'development').lower()
    flask_debug = os.getenv('FLASK_DEBUG', '').lower()
    app_env = os.getenv('APP_ENV', 'development').lower()
    return (
        flask_env == 'development'
        or flask_debug in ['1', 'true', 'yes']
        or app_env in ['dev', 'development', 'local']
    )


def _safe_profile_dict(perfil):
    perfil_seguro = {}
    for clave, valor in (perfil or {}).items():
        if isinstance(valor, datetime):
            perfil_seguro[clave] = valor.isoformat()
        else:
            perfil_seguro[clave] = valor
    return perfil_seguro


def _build_current_user(uid, decoded_token=None, perfil=None):
    perfil_seguro = _safe_profile_dict(perfil)
    rol_token = (decoded_token or {}).get('role')
    rol_perfil = perfil_seguro.get('rol')
    sucursal_usuario = perfil_seguro.get('sucursal_id') or perfil_seguro.get('sucursal')

    g.current_user = {
        'uid': uid,
        'token': decoded_token or {},
        'profile': perfil_seguro,
        'role': (rol_token or rol_perfil or '').lower(),
        'sucursal': sucursal_usuario,
    }
    return g.current_user


def _authenticate_from_session():
    uid = session.get('user_uid')
    if not uid:
        return None

    perfil = fa.obtener_usuario_por_uid(uid)
    if perfil and not perfil.get('activo', True):
        return None

    if perfil:
        return _build_current_user(uid, perfil=perfil)

    # Fallback: si el perfil no se pudo obtener (Firestore caído, timeout, etc.),
    # usar datos de sesión para evitar redirigir al login por errores transitorios
    role = session.get('user_role', '')
    if not role:
        return None

    perfil_fallback = {
        'uid': uid,
        'rol': role,
        'nombre': session.get('user_name', ''),
        'email': session.get('user_email', ''),
        'activo': True,
    }
    logger.warning(f"Firestore lookup failed for uid={uid}, using session cache (role={role})")
    return _build_current_user(uid, perfil=perfil_fallback)


def _persist_session_from_profile(uid, perfil, decoded_token=None):
    """Persist Flask session state from a verified Firebase user profile."""
    session.permanent = True
    session['user_uid'] = uid
    session['user_role'] = (perfil.get('rol') or '').lower()
    session['user_name'] = perfil.get('nombre')
    session['user_email'] = perfil.get('email')
    return _build_current_user(uid, decoded_token=decoded_token, perfil=perfil)

# Configurar logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

# Ensure local development session cookies are accepted by browsers
app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = not _is_local_development()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_PATH'] = '/'
session_cookie_domain = os.getenv('SESSION_COOKIE_DOMAIN')
if session_cookie_domain:
    app.config['SESSION_COOKIE_DOMAIN'] = session_cookie_domain
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=int(os.getenv('SESSION_LIFETIME_DAYS', '7')))


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Expose Firebase client config to Jinja templates from environment (.env)
app.jinja_env.globals['FIREBASE_CONFIG'] = {
    'apiKey': os.getenv('FIREBASE_API_KEY'),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN'),
    'projectId': os.getenv('FIREBASE_PROJECT_ID'),
    'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET'),
    'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    'appId': os.getenv('FIREBASE_APP_ID')
}

# ========================================
# DECORADORES
# ========================================

def login_required(f):
    """Verificar que el usuario esté autenticado con un ID token de Firebase."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        current_user = None

        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            if token:
                try:
                    decoded_token = firebase_admin.auth.verify_id_token(token, check_revoked=True)
                    uid = decoded_token.get('uid')
                    if uid:
                        perfil = fa.obtener_usuario_por_uid(uid)
                        if perfil and perfil.get('activo', True):
                            current_user = _build_current_user(uid, decoded_token=decoded_token, perfil=perfil)
                except Exception:
                    current_user = None

        if current_user is None:
            current_user = _authenticate_from_session()

        if current_user is None:
            uid_session = session.get('user_uid')
            logger.warning(
                f"Redirigiendo a /login desde {request.path} — "
                f"Bearer={bool(auth_header.startswith('Bearer '))}, "
                f"SessionUID={uid_session}, "
                f"SessionRole={session.get('user_role')}"
            )
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Se requiere un token de acceso'}), 401
            return redirect('/login')

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Verificar que el usuario autenticado tenga rol de admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = getattr(g, 'current_user', None) or _authenticate_from_session()
        if not current_user:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Autenticación requerida'}), 401
            return redirect('/login')

        role = (current_user.get('token', {}).get('role') or current_user.get('role') or current_user.get('profile', {}).get('rol') or '').lower()
        if role != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Acceso denegado'}), 403
            return redirect('/')
        return f(*args, **kwargs)

    return decorated_function


def _user_can_access_order(orden):
    """Permite acceso a la orden para usuarios autenticados.

    La verificación por sucursal se deja comentada como referencia para casos
    donde se quiera reactivar un control más estricto a nivel de recurso.
    """
    current_user = getattr(g, 'current_user', None)
    if not current_user:
        return False

    role = (current_user.get('token', {}).get('role') or current_user.get('role') or current_user.get('profile', {}).get('rol') or '').lower()
    if role == 'admin':
        return True

    # user_branch = str(current_user.get('sucursal') or current_user.get('profile', {}).get('sucursal_id') or '').strip()
    # order_branch = str((orden or {}).get('id_sucursal') or '').strip()
    # return bool(user_branch and order_branch and user_branch == order_branch)
    return True


def _forbid_order_access(message='No tienes acceso a esta orden'):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': message}), 403
    abort(403, description=message)

# ========================================
# RUTAS DE AUTENTICACIÓN
# ========================================

# Ruta de Login
@app.route('/login')
def login():
    return render_template('login.html')

# Ruta de Logout
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return jsonify({'success': True, 'message': 'Sesión cerrada'})

    session.clear()
    return redirect('/login')

# Ruta de Perfil
@app.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')

# Ruta de Alta de Empleado (solo admin)
@app.route('/empleados/nueva', methods=['GET'])
@login_required
@admin_required
def alta_empleado():
    return render_template('alta_empleado.html')

# API: Crear Nuevo Empleado
@app.route('/api/empleados/crear', methods=['POST'])
@login_required
@admin_required
def crear_empleado():
    try:
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        celular = request.form.get('celular')
        rol = request.form.get('rol')
        sucursal_id = request.form.get('sucursal')
        password = request.form.get('password')
        
        # Validaciones
        if not all([nombre, email, celular, rol, sucursal_id, password]):
            return jsonify({'success': False, 'error': 'Todos los campos son obligatorios'}), 400
        
        # Crear usuario
        resultado = fa.crear_usuario_empleado(email, password, nombre, rol, sucursal_id, celular)
        
        if resultado['success']:
            return jsonify({
                'success': True,
                'uid': resultado['uid'],
                'mensaje': resultado['mensaje']
            })
        else:
            return jsonify({'success': False, 'error': resultado['error']}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al crear empleado: {str(e)}'}), 500

# Ruta de Usuarios (listado)
@app.route('/usuarios')
@login_required
@admin_required
def usuarios():
    return render_template('usuarios.html')

# API: Obtener todos los usuarios
@app.route('/api/usuarios', methods=['GET'])
@login_required
@admin_required
def obtener_usuarios():
    try:
        # Pagination and filters
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=10, type=int)
        role = (request.args.get('rol') or '').strip().lower()
        sucursal = (request.args.get('sucursal') or '').strip()
        search = (request.args.get('search') or '').strip().lower()

        # Defensive bounds
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100

        usuarios = fa.obtener_usuarios_activos()

        # Normalize/serialize values for JSON response
        normalized = []
        for usuario in usuarios:
            u = dict(usuario)
            fecha = u.get('fecha_creacion')
            if hasattr(fecha, 'timestamp'):
                u['fecha_creacion'] = fecha.timestamp()
            u['rol'] = (u.get('rol') or '').lower()
            u['sucursal_id'] = str(u.get('sucursal_id') or '')
            u['nombre'] = u.get('nombre') or ''
            u['email'] = u.get('email') or ''
            u['celular'] = u.get('celular') or ''
            normalized.append(u)

        # Apply filters
        if role:
            normalized = [u for u in normalized if u.get('rol') == role]
        if sucursal:
            normalized = [u for u in normalized if u.get('sucursal_id') == sucursal]
        if search:
            normalized = [
                u for u in normalized
                if search in u.get('nombre', '').lower() or search in u.get('email', '').lower() or search in u.get('celular', '').lower()
            ]

        # Sort by creation date desc (fallback 0)
        normalized.sort(key=lambda u: u.get('fecha_creacion') or 0, reverse=True)

        total = len(normalized)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        usuarios_page = normalized[start:end]

        return jsonify({
            'success': True,
            'usuarios': usuarios_page,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Actualizar Usuario
@app.route('/api/usuarios/<uid>/actualizar', methods=['POST'])
@login_required
@admin_required
def actualizar_usuario_endpoint(uid):
    try:
        datos = request.json
        if not datos:
            return jsonify({'success': False, 'error': 'No se enviaron datos'}), 400
            
        resultado = fa.actualizar_usuario(uid, datos)
        if resultado['success']:
            return jsonify(resultado), 200
        else:
            return jsonify(resultado), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Eliminar Usuario
@app.route('/api/usuarios/<uid>/eliminar', methods=['POST', 'DELETE'])
@login_required
@admin_required
def eliminar_usuario_endpoint(uid):
    try:
        resultado = fa.eliminar_usuario(uid)
        if resultado['success']:
            return jsonify(resultado), 200
        else:
            return jsonify(resultado), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Obtener usuarios por sucursal
@app.route('/api/usuarios/sucursal/<sucursal_id>', methods=['GET'])
@login_required
@admin_required
def obtener_usuarios_sucursal(sucursal_id):
    try:
        usuarios = fa.obtener_usuarios_por_sucursal(sucursal_id)
        
        for usuario in usuarios:
            if hasattr(usuario.get('fecha_creacion'), 'timestamp'):
                usuario['fecha_creacion'] = usuario['fecha_creacion'].timestamp()
        
        return jsonify({
            'success': True,
            'usuarios': usuarios
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Cambiar contraseña
@app.route('/api/usuario/cambiar-contrasena', methods=['POST'])
@login_required
def cambiar_contrasena():
    try:
        data = request.get_json()
        nueva_contrasena = data.get('nuevaContrasena')
        
        if not nueva_contrasena:
            return jsonify({'success': False, 'error': 'Nueva contraseña requerida'}), 400
        
        # Aquí se llamaría al método de Firebase Auth para cambiar contraseña
        # Por ahora retornamos un placeholder
        return jsonify({
            'success': True,
            'mensaje': 'Contraseña actualizada. Por favor inicia sesión nuevamente.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Verificar estado del usuario
@app.route('/api/auth/check-status', methods=['POST'])
@login_required
def check_user_status():
    try:
        current_user = getattr(g, 'current_user', None)
        uid = current_user.get('uid') if current_user else None
        if not uid:
            return jsonify({'success': False, 'error': 'Autenticación requerida'}), 401

        resultado = fa.verificar_estado_usuario(uid)
        
        if 'error' in resultado:
            return jsonify({'success': False, 'error': resultado['error']}), 404

        return jsonify({'success': True, 'activo': resultado['activo']})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/login_session', methods=['POST'])
def login_session():
    """Verify a Firebase ID token and atomically populate Flask session state."""
    try:
        data = request.get_json(silent=True) or {}
        id_token = None

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            id_token = auth_header.split(' ', 1)[1].strip()

        if not id_token:
            id_token = data.get('idToken')

        if not id_token:
            return jsonify({'success': False, 'error': 'No ID token provided'}), 401

        decoded = firebase_admin.auth.verify_id_token(id_token, check_revoked=True)
        uid = decoded.get('uid')
        if not uid:
            return jsonify({'success': False, 'error': 'Invalid token'}), 401

        perfil = fa.obtener_usuario_por_uid(uid)
        if not perfil:
            return jsonify({'success': False, 'error': 'Perfil no encontrado'}), 404

        if not perfil.get('activo', True):
            session.clear()
            return jsonify({'success': False, 'error': 'Tu cuenta está desactivada'}), 403

        perfil_safe = _safe_profile_dict(perfil)
        perfil_safe['uid'] = uid
        _persist_session_from_profile(uid, perfil_safe, decoded_token=decoded)

        return jsonify({'success': True, 'uid': uid, 'usuario': perfil_safe}), 200
    except Exception as e:
        logger.exception('Error sincronizando sesión Flask/Firebase')
        return jsonify({'success': False, 'error': str(e)}), 401

# API: Obtener todas las sucursales
@app.route('/api/sucursales', methods=['GET'])
@login_required
def obtener_sucursales():
    try:
        sucursales = fb.get_all_branches()
        return jsonify({'success': True, 'sucursales': sucursales})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Main route - Dashboard
@app.route('/')
@login_required
def index():
    try:
        ordenes = fb.get_all_orders()
        sucursales = fb.get_all_branches()
        clientes = fb.get_all_clients()
        
        # Create a dictionary for quick client lookup
        clientes_dict = {cliente['id']: cliente for cliente in clientes}
        
        # Statistics
        total_ordenes = len(ordenes)
        ordenes_pendientes = len([o for o in ordenes if o.get('estado') == 'Pendiente'])
        ordenes_entregadas = len([o for o in ordenes if o.get('estado') == 'Entregado'])
        
        return render_template('index.html', 
                             ordenes=ordenes[:10],  # Últimas 10 órdenes
                             sucursales=sucursales,
                             clientes_dict=clientes_dict,
                             total_ordenes=total_ordenes,
                             ordenes_pendientes=ordenes_pendientes,
                             ordenes_entregadas=ordenes_entregadas)
    except Exception as e:
        return render_template('error.html', error=str(e))

# Control / Panel de Administración
@app.route('/control')
@login_required
@admin_required
def control():
    """Vista del dashboard gerencial / control"""
    return render_template('control.html')

@app.route('/api/control/datos', methods=['GET'])
@login_required
@admin_required
def api_control_datos():
    try:
        ordenes = fb.get_all_orders()
        sucursales = fb.get_all_branches()
        usuarios = fa.obtener_usuarios_activos()
        
        # Convertir timestamps si los hay
        usuarios_safe = []
        for u in usuarios:
            us = dict(u)
            if hasattr(us.get('fecha_creacion'), 'timestamp'):
                us['fecha_creacion'] = us['fecha_creacion'].isoformat()
            usuarios_safe.append(us)

        return jsonify({
            'success': True,
            'ordenes': ordenes,
            'sucursales': sucursales,
            'usuarios': usuarios_safe
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Client routes
@app.route('/clientes')
@login_required
def clientes():
    try:
        clientes = fb.get_all_clients()
        return render_template('clientes.html', clientes=clientes)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        try:
            data = {
                'ci': request.form.get('ci'),
                'nombre_completo': request.form.get('nombre_completo'),
                'telefono': request.form.get('telefono')
            }
            cliente_id = fb.create_client(data)
            return jsonify({'success': True, 'cliente_id': cliente_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    return render_template('nuevo_cliente.html')

@app.route('/clientes/<cliente_id>')
@login_required
def ver_cliente(cliente_id):
    try:
        cliente = fb.get_client_by_id(cliente_id)
        if not cliente:
            return render_template('error.html', error='Cliente no encontrado')
        
        # Get client orders from historial_ordenes (order IDs)
        historial_ordenes = cliente.get('historial_ordenes', [])
        ordenes_cliente = fb.get_orders_by_ids(historial_ordenes)
        
        return render_template('ver_cliente.html', cliente=cliente, ordenes=ordenes_cliente)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/clientes/<cliente_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    try:
        cliente = fb.get_client_by_id(cliente_id)
        if not cliente:
            return render_template('error.html', error='Cliente no encontrado')

        if request.method == 'POST':
            data = {
                'ci': request.form.get('ci'),
                'nombre_completo': request.form.get('nombre_completo'),
                'telefono': request.form.get('telefono')
            }

            if not all([data['ci'], data['nombre_completo'], data['telefono']]):
                return jsonify({'success': False, 'error': 'Todos los campos son obligatorios'}), 400

            fb.update_client(cliente_id, data)
            return jsonify({'success': True, 'cliente_id': cliente_id})

        return render_template('editar_cliente.html', cliente=cliente)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/api/clientes/buscar')
@login_required
def buscar_cliente():
    try:
        ci = (request.args.get('ci') or '').strip()
        query = (request.args.get('q') or '').strip().lower()

        if not ci and not query:
            return jsonify({'success': False, 'error': 'CI o texto de búsqueda requerido'}), 400

        if ci:
            cliente = fb.get_client_by_ci(ci)
            if cliente:
                return jsonify({'success': True, 'cliente': cliente})

        if query:
            clientes = fb.get_all_clients()
            coincidencias = []

            for cliente in clientes:
                nombre = str(cliente.get('nombre_completo') or '').lower()
                ci_cliente = str(cliente.get('ci') or '').lower()
                telefono = str(cliente.get('telefono') or '').lower()

                if query in nombre or query in ci_cliente or query in telefono:
                    coincidencias.append(cliente)

            if coincidencias:
                coincidencias.sort(key=lambda c: (
                    0 if str(c.get('ci') or '').lower() == query else 1,
                    str(c.get('nombre_completo') or '').lower()
                ))

                respuesta = {'success': True, 'clientes': coincidencias[:10]}

                if len(coincidencias) == 1:
                    respuesta['cliente'] = coincidencias[0]

                return jsonify(respuesta)

        return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Order routes
@app.route('/ordenes')
@login_required
def ordenes():
    try:
        ordenes = fb.get_all_orders()
        sucursales = fb.get_all_branches()
        clientes = fb.get_all_clients()
        
        # Create a dictionary for quick client lookup
        clientes_dict = {cliente['id']: cliente for cliente in clientes}
        
        return render_template('ordenes.html', ordenes=ordenes, sucursales=sucursales, clientes_dict=clientes_dict)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/ordenes/nueva', methods=['GET', 'POST'])
@login_required
def nueva_orden():
    if request.method == 'POST':
        try:
            # Basic data
            data = {
                'id_sucursal': request.form.get('id_sucursal'),
                'id_cliente': request.form.get('id_cliente'),
                'id_empleado': request.form.get('id_empleado', ''),
                'nombre_usuario': request.form.get('nombre_empleado', 'Desconocido'),
                'fecha_creacion': datetime.utcnow().isoformat() + 'Z',
                'fecha_entrega': request.form.get('fecha_entrega'),
                'estado': 'Pendiente',
                
                # Specifications
                'especificaciones': {
                    'material_base': request.form.get('material_base'),
                    'material_detalle': request.form.get('material_detalle') if request.form.get('material_base') != 'otro' else '',
                    'material_otro': request.form.get('material_otro') if request.form.get('material_base') == 'otro' else '',
                    'tipo_lente': request.form.get('tipo_lente'),
                    'diseno_bifocal': request.form.get('diseno_bifocal') if request.form.get('tipo_lente') == 'bifocal' else '',
                    'marca_multifocal': request.form.get('marca_multifocal') if request.form.get('tipo_lente') == 'multifocal' else '',
                    'modelo_multifocal': request.form.get('modelo_multifocal') if request.form.get('tipo_lente') == 'multifocal' else '',
                    'tratamientos': request.form.getlist('tratamientos[]')
                },
                
                # Graduation
                'graduacion': {
                    'lejos': {
                        'od': {
                            'esf': float(request.form.get('od_esf', 0)),
                            'cil': float(request.form.get('od_cil')) if request.form.get('od_cil') else None,
                            'eje': int(request.form.get('od_eje')) if request.form.get('od_eje') else None
                        },
                        'oi': {
                            'esf': float(request.form.get('oi_esf', 0)),
                            'cil': float(request.form.get('oi_cil')) if request.form.get('oi_cil') else None,
                            'eje': int(request.form.get('oi_eje')) if request.form.get('oi_eje') else None
                        },
                        'di': int(request.form.get('di', 0))
                    },
                    'cerca': {
                        'adicion': float(request.form.get('adicion')) if request.form.get('adicion') else None
                    }
                },
                
                # Frame
                'montura': {
                    'modelo': request.form.get('modelo_montura'),
                    'observaciones': request.form.get('observaciones_montura', '')
                },
                
                # Payments
                'pagos': {
                    'total': float(request.form.get('total', 0)),
                    'adelanto': float(request.form.get('adelanto', 0)),
                    'saldo': float(request.form.get('total', 0)) - float(request.form.get('adelanto', 0)),
                    'metodo_pago': request.form.get('metodo_pago')
                },
                
                # Historial inicial
                'historial': [{
                    'fecha': datetime.utcnow().isoformat() + 'Z',
                    'id_usuario': request.form.get('id_empleado', ''),
                    'nombre_usuario': request.form.get('nombre_empleado', 'Desconocido'),
                    'cambios': ['Creación de la orden']
                }]
            }
            
            orden_id = fb.create_order(data)
            return jsonify({'success': True, 'orden_id': orden_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    # GET - Show form
    try:
        clientes = fb.get_all_clients()
        sucursales = fb.get_all_branches()
        return render_template('nueva_orden.html', clientes=clientes, sucursales=sucursales)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/ordenes/<orden_id>')
@login_required
def ver_orden(orden_id):
    try:
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return render_template('error.html', error='Orden no encontrada')

        if not _user_can_access_order(orden):
            return _forbid_order_access()
        
        cliente = fb.get_client_by_id(orden.get('id_cliente'))
        sucursal = fb.get_branch_by_id(orden.get('id_sucursal'))
        
        # Búsqueda optimizada del empleado
        empleado_id = orden.get('id_empleado')
        if empleado_id:
            empleado = fb.get_user_by_id(empleado_id)
            if empleado:
                orden['nombre_empleado'] = empleado.get('nombre', 'Nombre no encontrado')
            else:
                orden['nombre_empleado'] = 'Empleado no encontrado'
        else:
            # Fallback por si el empleado fue eliminado o es una orden antigua
            orden['nombre_empleado'] = orden.get('nombre_empleado', 'N/A')

        return render_template('ver_orden.html', orden=orden, cliente=cliente, sucursal=sucursal)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/ordenes/<orden_id>/descargar-pdf', methods=['GET'])
@login_required
def descargar_pdf_orden(orden_id):
    """
    Descarga la orden como PDF.
    Endpoint: GET /ordenes/{orden_id}/descargar-pdf
    """
    try:
        from pdf_generator import generar_pdf_orden, enviar_pdf_respuesta
        
        # Obtener los datos de la orden
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return render_template('error.html', error='Orden no encontrada'), 404

        if not _user_can_access_order(orden):
            return _forbid_order_access()
        
        # Obtener cliente y sucursal
        cliente = fb.get_client_by_id(orden.get('id_cliente'))
        sucursal = fb.get_branch_by_id(orden.get('id_sucursal'))
        
        # Generar PDF
        pdf_buffer, filename = generar_pdf_orden(orden, cliente, sucursal)
        
        # Retornar respuesta con el PDF
        return enviar_pdf_respuesta(app, pdf_buffer, filename)
        
    except Exception as e:
        logger.error(f"Error descargando PDF: {str(e)}")
        return render_template('error.html', error=f'Error al generar PDF: {str(e)}'), 500

@app.route('/ordenes/<orden_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_orden(orden_id):
    import json
    from datetime import datetime
    try:
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return jsonify({'success': False, 'error': 'Orden no encontrada'}) if request.method == 'POST' else render_template('error.html', error='Orden no encontrada')

        # current_user = getattr(g, 'current_user', None) or {}
        # role = (current_user.get('token', {}).get('role') or current_user.get('role') or current_user.get('profile', {}).get('rol') or '').lower()
        # if role != 'admin':
        #     user_branch = str(current_user.get('sucursal') or current_user.get('profile', {}).get('sucursal_id') or '').strip()
        #     order_branch = str((orden or {}).get('id_sucursal') or '').strip()
        #     if not user_branch or not order_branch or user_branch != order_branch:
        #         return _forbid_order_access('Solo puedes editar órdenes de tu sucursal')
        
        if request.method == 'GET':
            sucursales = fb.get_all_branches()
            cliente = fb.get_client_by_id(orden.get('id_cliente'))
            
            # Pasar diccionarios seguros a JSON para pre-popular
            return render_template('editar_orden.html', 
                                   orden=orden, 
                                   sucursales=sucursales,
                                   orden_json=json.dumps(orden),
                                   cliente_json=json.dumps(cliente) if cliente else "null")
            
        elif request.method == 'POST':
            data = request.form.to_dict()
            editor_uid = data.get('id_empleado')
            
            # Extracción y estructuración igual que nueva_orden
            new_order_data = {
                'id_sucursal': data.get('id_sucursal'),
                'fecha_entrega': data.get('fecha_entrega'),
                'id_empleado': orden.get('id_empleado') or data.get('id_empleado'),
                
                'graduacion': {
                    'lejos': {
                        'od': {
                            'esf': float(data.get('od_esf') or 0),
                            'cil': float(data.get('od_cil') or 0),
                            'eje': int(data.get('od_eje') or 0)
                        },
                        'oi': {
                            'esf': float(data.get('oi_esf') or 0),
                            'cil': float(data.get('oi_cil') or 0),
                            'eje': int(data.get('oi_eje') or 0)
                        },
                        'di': float(data.get('di') or 0)
                    },
                    'cerca': {
                        'adicion': float(data.get('adicion') or 0)
                    }
                },
                
                'especificaciones': {
                    'material_base': data.get('material_base'),
                    'material_detalle': data.get('material_detalle') if data.get('material_base') != 'otro' else '',
                    'material_otro': data.get('material_otro') if data.get('material_base') == 'otro' else '',
                    'tipo_lente': data.get('tipo_lente'),
                    'diseno_bifocal': data.get('diseno_bifocal') if data.get('tipo_lente') == 'bifocal' else '',
                    'marca_multifocal': data.get('marca_multifocal') if data.get('tipo_lente') == 'multifocal' else '',
                    'modelo_multifocal': data.get('modelo_multifocal') if data.get('tipo_lente') == 'multifocal' else '',
                    'tratamientos': request.form.getlist('tratamientos[]')
                },
                
                'montura': {
                    'modelo': data.get('modelo_montura'),
                    'observaciones': data.get('observaciones_montura')
                },
                
                'pagos': {
                    'total': float(data.get('total') or 0),
                    'adelanto': float(data.get('adelanto') or 0),
                    'saldo': float(data.get('total') or 0) - float(data.get('adelanto') or 0),
                    'metodo_pago': data.get('metodo_pago')
                },
                'ultima_actualizacion': datetime.now().isoformat()
            }
            
            # Construir historial (buscamos cambios principales)
            historial = orden.get('historial', [])
            cambios = []
            
            # Comparaciones simples para el log
            if orden.get('pagos', {}).get('total') != new_order_data['pagos']['total']:
                cambios.append(f"Total modificado a {new_order_data['pagos']['total']}")
            if orden.get('id_sucursal') != new_order_data['id_sucursal']:
                cambios.append(f"Sucursal modificada a {new_order_data['id_sucursal']}")
            if orden.get('fecha_entrega') != new_order_data['fecha_entrega']:
                cambios.append(f"Fecha de entrega modificada a {new_order_data['fecha_entrega']}")
                
            # Si hubo cambios en datos de lentes o montura de manera general
            if json.dumps(orden.get('graduacion'), sort_keys=True) != json.dumps(new_order_data['graduacion'], sort_keys=True):
                cambios.append("Graduación modificada")
            if json.dumps(orden.get('montura'), sort_keys=True) != json.dumps(new_order_data['montura'], sort_keys=True):
                cambios.append("Datos de montura modificados")
            if json.dumps(orden.get('especificaciones'), sort_keys=True) != json.dumps(new_order_data['especificaciones'], sort_keys=True):
                cambios.append("Especificaciones de lentes modificadas")
            if orden.get('pagos', {}).get('adelanto') != new_order_data['pagos']['adelanto']:
                cambios.append(f"A cuenta modificado a {new_order_data['pagos']['adelanto']}")
                
            if not cambios:
                cambios.append("Edición general sin cambios rastreados específicamente")
                
            nuevo_log = {
                'fecha': datetime.now().isoformat(),
                'id_usuario': editor_uid or 'Desconocido',
                'nombre_usuario': data.get('nombre_empleado', 'Desconocido'),
                'cambios': cambios
            }
            historial.append(nuevo_log)
            new_order_data['historial'] = historial
            
            fb.update_order(orden_id, new_order_data)
            
            return jsonify({
                'success': True,
                'orden_id': orden_id
            })
            
    except Exception as e:
        if request.method == 'POST':
            return jsonify({'success': False, 'error': str(e)}), 500
        return render_template('error.html', error=str(e))

@app.route('/api/ordenes/<orden_id>/estado', methods=['PUT'])
@login_required
def actualizar_estado(orden_id):
    try:
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return jsonify({'success': False, 'error': 'Orden no encontrada'}), 404

        if not _user_can_access_order(orden):
            return _forbid_order_access()

        new_status = request.json.get('estado')
        if not new_status:
            return jsonify({'success': False, 'error': 'Estado requerido'}), 400
        
        fb.update_order_status(orden_id, new_status)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ordenes/<orden_id>', methods=['DELETE'])
@login_required
def eliminar_orden(orden_id):
    try:
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return jsonify({'success': False, 'error': 'Orden no encontrada'}), 404

        if not _user_can_access_order(orden):
            return _forbid_order_access()

        fb.delete_order(orden_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Branch routes
@app.route('/sucursales')
@login_required
def sucursales():
    try:
        sucursales = fb.get_all_branches()
        return render_template('sucursales.html', sucursales=sucursales)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/sucursales/crear', methods=['POST'])
@login_required
@admin_required
def crear_sucursal():
    try:
        sucursal_id = (request.form.get('id') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        direccion = (request.form.get('direccion') or '').strip()
        ubicacion = (request.form.get('ubicacion') or '').strip()

        if not all([sucursal_id, nombre, direccion]):
            return jsonify({'success': False, 'error': 'ID, nombre y dirección son obligatorios'}), 400

        if fb.get_branch_by_id(sucursal_id):
            return jsonify({'success': False, 'error': 'Ya existe una sucursal con ese ID'}), 400

        data = {
            'nombre': nombre,
            'direccion': direccion,
            'ubicacion': ubicacion,
        }

        fb.create_branch(sucursal_id, data)
        return jsonify({'success': True, 'sucursal_id': sucursal_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/sucursales/<sucursal_id>/editar', methods=['POST'])
@login_required
@admin_required
def editar_sucursal(sucursal_id):
    try:
        nombre = (request.form.get('nombre') or '').strip()
        direccion = (request.form.get('direccion') or '').strip()
        ubicacion = (request.form.get('ubicacion') or '').strip()

        if not all([nombre, direccion]):
            return jsonify({'success': False, 'error': 'Nombre y dirección son obligatorios'}), 400

        if not fb.get_branch_by_id(sucursal_id):
            return jsonify({'success': False, 'error': 'Sucursal no encontrada'}), 404

        data = {
            'nombre': nombre,
            'direccion': direccion,
            'ubicacion': ubicacion,
        }

        fb.update_branch(sucursal_id, data)
        return jsonify({'success': True, 'sucursal_id': sucursal_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Página no encontrada'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Error interno del servidor'), 500


@app.route('/api/me', methods=['POST'])
def api_me():
    """Verifica el ID token enviado por el cliente y devuelve el perfil desde Firestore.

    Se acepta el token en la cabecera `Authorization: Bearer <token>` o en el body JSON `{ "idToken": "..." }`.
    """
    try:
        logger.info('API /api/me called')
        # Obtener token
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        logger.info(f'Authorization header present: {bool(auth_header)}')
        if not token:
            data = request.get_json(silent=True) or {}
            token = data.get('idToken')
        logger.info(f'Token present in body: {bool(token and not auth_header)}')

        if not token:
            return jsonify({'success': False, 'error': 'No ID token provided'}), 401

        # Verificar token con Admin SDK
        try:
            decoded = firebase_admin.auth.verify_id_token(token)
            uid = decoded.get('uid')
            logger.info(f'Decoded token uid={uid}')
        except Exception as verify_err:
            logger.exception('Token verification failed')
            return jsonify({'success': False, 'error': 'Invalid token'}), 401

        # Obtener perfil desde firebase_auth helper (usa Admin SDK)
        perfil = fa.obtener_usuario_por_uid(uid)
        logger.info(f'Perfil lookup for uid={uid} returned: {bool(perfil)}')
        if perfil:
            # Convertir valores no serializables (datetime) a ISO strings
            perfil_safe = {}
            for k, v in perfil.items():
                try:
                    # datetime -> isoformat
                    from datetime import datetime
                    if isinstance(v, datetime):
                        perfil_safe[k] = v.isoformat()
                    else:
                        perfil_safe[k] = v
                except Exception:
                    perfil_safe[k] = v

            # Populate server session
            _persist_session_from_profile(uid, perfil_safe, decoded_token=decoded)
            logger.info(f"Session populated for uid={uid} role={session.get('user_role')}")
            logger.info(f"Session keys now: {list(session.keys())}")

            # Build response and populate server-side session for non-auth UI state
            from flask import make_response
            resp = make_response(jsonify({'success': True, 'usuario': perfil_safe, 'uid': uid}))
            return resp
        else:
            return jsonify({'success': False, 'error': 'Perfil no encontrado', 'uid': uid}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

if __name__ == '__main__':
    is_local_dev = _is_local_development()
    app.run(
        debug=is_local_dev,
        host='0.0.0.0' if is_local_dev else '127.0.0.1',
        port=int(os.getenv('PORT', 5000))
    )

