"""
Módulo de autenticación con Firebase Auth y Firestore
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Usar el cliente de Firestore ya inicializado
from firebase_config import db

# Caché de perfiles de usuario.
#
# Motivo: obtener_usuario_por_uid() se llama en cada request autenticado (guard de
# sesión, /api/login_session, /api/me) y cada llamada cuesta un read a Firestore
# (~300 ms medidos). El perfil cambia muy poco, así que se cachea con TTL corto.
#
# El TTL es deliberadamente bajo: también cubre la comprobación de `activo`, por lo
# que un usuario desactivado pierde el acceso como máximo en USER_CACHE_DURATION
# segundos. Toda escritura de perfil invalida su entrada de inmediato.
_user_cache = {}
_user_cache_duration = int(os.getenv('USER_CACHE_DURATION', os.getenv('CACHE_DURATION', 60)))


def _invalidate_user_cache(uid=None):
    """Descarta el perfil cacheado de un uid, o toda la caché si uid es None."""
    if uid is None:
        _user_cache.clear()
    else:
        _user_cache.pop(uid, None)


def crear_usuario_empleado(email, password, nombre, rol, sucursal_id, celular=None):
    """
    Crea un nuevo usuario en Firebase Auth y su perfil en Firestore
    
    Args:
        email (str): Email del nuevo empleado
        password (str): Contraseña temporal
        nombre (str): Nombre completo del empleado
        rol (str): 'admin' o 'empleado'
        sucursal_id (str): ID de la sucursal (S1-S4)
    
    Returns:
        dict: Información del usuario creado o error
    """
    try:
        # Validar rol
        if rol not in ['admin', 'empleado']:
            return {'success': False, 'error': 'Rol inválido. Debe ser "admin" o "empleado"'}
        
        # Validar sucursal_id
        if sucursal_id not in ['S1', 'S2', 'S3', 'S4']:
            return {'success': False, 'error': 'Sucursal inválida. Debe ser S1, S2, S3 o S4'}
        
        # Crear usuario en Firebase Auth
        user = auth.create_user(
            email=email,
            password=password,
            display_name=nombre
        )
        
        # Crear perfil en Firestore
        db.collection('usuarios').document(user.uid).set({
            'nombre': nombre,
            'email': email,
            'celular': celular or '',
            'rol': rol,
            'sucursal_id': sucursal_id,
            # S8: hora UTC timezone-aware; antes se usaba una llamada deprecada
            # que devolvía un datetime naive.
            'fecha_creacion': datetime.now(timezone.utc),
            'debeCambiarPassword': True,
            'activo': True
        })
        
        _invalidate_user_cache(user.uid)

        return {
            'success': True,
            'uid': user.uid,
            'email': user.email,
            'mensaje': 'Usuario creado exitosamente. El empleado debe cambiar la contraseña en su primer login.'
        }
    
    except auth.EmailAlreadyExistsError:
        return {'success': False, 'error': 'El email ya está registrado'}
    except auth.InvalidPasswordError:
        return {'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres'}
    except Exception as e:
        return {'success': False, 'error': f'Error al crear usuario: {str(e)}'}


def obtener_usuario_por_uid(uid):
    """
    Obtiene la información del perfil de un usuario desde Firestore
    
    Args:
        uid (str): UID del usuario en Firebase Auth
    
    Returns:
        dict: Datos del usuario o None
    """
    cached = _user_cache.get(uid)
    if cached and (datetime.now() - cached['timestamp']).total_seconds() < _user_cache_duration:
        return dict(cached['data'])

    try:
        doc = db.collection('usuarios').document(uid).get()
        if doc.exists:
            usuario = doc.to_dict()
            usuario['uid'] = uid
            _user_cache[uid] = {'data': usuario, 'timestamp': datetime.now()}
            return dict(usuario)
        return None
    except Exception as e:
        print(f'Error al obtener usuario: {str(e)}')
        return None


def obtener_usuario_por_email(email):
    """
    Obtiene la información del perfil de un usuario por email
    
    Args:
        email (str): Email del usuario
    
    Returns:
        dict: Datos del usuario incluyendo uid o None
    """
    try:
        docs = db.collection('usuarios').where('email', '==', email).limit(1).stream()
        for doc in docs:
            usuario = doc.to_dict()
            usuario['uid'] = doc.id
            return usuario
        return None
    except Exception as e:
        print(f'Error al obtener usuario por email: {str(e)}')
        return None


def obtener_todos_usuarios():
    """
    Obtiene todos los usuarios registrados
    
    Returns:
        list: Lista de usuarios
    """
    try:
        usuarios = []
        docs = db.collection('usuarios').stream()
        for doc in docs:
            usuario = doc.to_dict()
            usuario['uid'] = doc.id
            usuarios.append(usuario)
        return usuarios
    except Exception as e:
        print(f'Error al obtener usuarios: {str(e)}')
        return []


def obtener_usuarios_por_sucursal(sucursal_id):
    """
    Obtiene todos los usuarios de una sucursal específica
    
    Args:
        sucursal_id (str): ID de la sucursal
    
    Returns:
        list: Lista de usuarios de la sucursal
    """
    try:
        usuarios = []
        docs = db.collection('usuarios').where('sucursal_id', '==', sucursal_id).stream()
        for doc in docs:
            usuario = doc.to_dict()
            usuario['uid'] = doc.id
            usuarios.append(usuario)
        return usuarios
    except Exception as e:
        print(f'Error al obtener usuarios por sucursal: {str(e)}')
        return []


def actualizar_usuario(uid, datos):
    """
    Actualiza el perfil de un usuario en Firestore y Firebase Auth (email)
    """
    try:
        # Campos permitidos para actualización en Firestore
        campos_firestore = ['nombre', 'email', 'celular', 'rol', 'sucursal_id', 'activo']
        datos_firestore = {k: v for k, v in datos.items() if k in campos_firestore}
        
        # Asegurarse de que 'activo' sea un booleano
        if 'activo' in datos_firestore:
            datos_firestore['activo'] = bool(datos_firestore['activo'])

        email_nuevo = datos.get('email')

        # 1. Actualizar Auth (si hay email nuevo)
        if email_nuevo:
            auth.update_user(uid, email=email_nuevo)
            datos_firestore['email'] = email_nuevo
            
        # 2. Actualizar Firestore
        if datos_firestore:
            db.collection('usuarios').document(uid).update(datos_firestore)
        
        _invalidate_user_cache(uid)

        return {'success': True, 'mensaje': 'Usuario actualizado exitosamente'}
    
    except Exception as e:
        return {'success': False, 'error': f'Error al actualizar usuario: {str(e)}'}

def actualizar_perfil_usuario(uid, datos):
    """
    Actualiza el perfil de un usuario en Firestore
    
    Args:
        uid (str): UID del usuario
        datos (dict): Datos a actualizar
    
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Campos permitidos para actualización
        campos_permitidos = ['nombre', 'celular', 'debeCambiarPassword', 'sucursal_id']
        datos_filtrados = {k: v for k, v in datos.items() if k in campos_permitidos}
        
        if not datos_filtrados:
            return {'success': False, 'error': 'No hay campos válidos para actualizar'}
        
        db.collection('usuarios').document(uid).update(datos_filtrados)
        _invalidate_user_cache(uid)
        return {'success': True, 'mensaje': 'Perfil actualizado exitosamente'}
    
    except Exception as e:
        return {'success': False, 'error': f'Error al actualizar perfil: {str(e)}'}


def cambiar_contrasena(uid, nueva_contrasena):
    """
    Cambia la contraseña de un usuario
    
    Args:
        uid (str): UID del usuario
        nueva_contrasena (str): Nueva contraseña
    
    Returns:
        dict: Resultado de la operación
    """
    try:
        auth.update_user(uid, password=nueva_contrasena)
        
        # Actualizar flag debeCambiarPassword
        db.collection('usuarios').document(uid).update({
            'debeCambiarPassword': False
        })
        _invalidate_user_cache(uid)

        return {'success': True, 'mensaje': 'Contraseña actualizada exitosamente'}
    
    except auth.InvalidPasswordError:
        return {'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres'}
    except Exception as e:
        return {'success': False, 'error': f'Error al cambiar contraseña: {str(e)}'}


def eliminar_usuario(uid):
    """
    Elimina un usuario de Firebase Auth y Firestore (soft delete - marca como inactivo)
    
    Args:
        uid (str): UID del usuario
    
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Soft delete - marcar como inactivo
        db.collection('usuarios').document(uid).update({
            'activo': False,
            # S8: hora UTC timezone-aware; antes se usaba una llamada deprecada
            # que devolvía un datetime naive.
            'fecha_eliminacion': datetime.now(timezone.utc)
        })
        _invalidate_user_cache(uid)

        return {'success': True, 'mensaje': 'Usuario desactivado exitosamente'}
    
    except Exception as e:
        return {'success': False, 'error': f'Error al eliminar usuario: {str(e)}'}


def eliminar_usuario_permanente(uid):
    """
    Elimina permanentemente un usuario de Firebase Auth y Firestore.

    Args:
        uid (str): UID del usuario

    Returns:
        dict: Resultado de la operación
    """
    try:
        try:
            auth.delete_user(uid)
        except auth.UserNotFoundError:
            pass

        db.collection('usuarios').document(uid).delete()
        _invalidate_user_cache(uid)

        return {'success': True, 'mensaje': 'Usuario eliminado permanentemente'}

    except Exception as e:
        return {'success': False, 'error': f'Error al eliminar usuario permanentemente: {str(e)}'}


def obtener_usuarios_por_estado(activo=True):
    """
    Obtiene usuarios filtrados por estado de activo
    
    Returns:
        list: Lista de usuarios activos
    """
    try:
        usuarios = []
        docs = db.collection('usuarios').where('activo', '==', bool(activo)).stream()
        for doc in docs:
            usuario = doc.to_dict()
            usuario['uid'] = doc.id
            usuarios.append(usuario)
        return usuarios
    except Exception as e:
        print(f'Error al obtener usuarios por estado: {str(e)}')
        return []


def obtener_usuarios_activos():
    """
    Obtiene todos los usuarios activos.
    """
    return obtener_usuarios_por_estado(True)


def verificar_estado_usuario(uid):
    """
    Verifica si un usuario está activo en Firestore.
    
    Args:
        uid (str): UID del usuario.
        
    Returns:
        dict: {'activo': True/False, 'error': ...}
    """
    try:
        usuario = obtener_usuario_por_uid(uid)
        if usuario:
            return {'activo': usuario.get('activo', False)}
        return {'activo': False, 'error': 'Usuario no encontrado'}
    except Exception as e:
        return {'activo': False, 'error': str(e)}
