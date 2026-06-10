/**
 * Módulo de Autenticación (Firebase v10+ modular)
 * Maneja login, logout, y autorización con sintaxis funcional moderna
 */

import { 
    getAuth, 
    signInWithEmailAndPassword, 
    signOut, 
    onAuthStateChanged,
    updatePassword
} from 'https://www.gstatic.com/firebasejs/10.7.2/firebase-auth.js';

import { 
    getFirestore, 
    collection, 
    doc, 
    updateDoc 
} from 'https://www.gstatic.com/firebasejs/10.7.2/firebase-firestore.js';

import { getFirebaseServices, waitForFirebaseReady } from './firebase-config.js';

// Estados globales
let currentUser = null;
let userProfile = null;
let auth = null;
let db = null;
let logoutInProgress = false;

const originalFetch = window.fetch.bind(window);

/**
 * Override global fetch para inyectar Bearer token automáticamente
 */
async function secureFetch(input, init = {}) {
    try {
        const requestUrl = input instanceof Request ? input.url : String(input);
        const url = new URL(requestUrl, window.location.origin);

        if (url.origin !== window.location.origin) {
            return originalFetch(input, init);
        }

        const headers = new Headers(input instanceof Request ? input.headers : (init.headers || {}));

        // Inicializar Firebase si no está listo
        if (!auth || !currentUser) {
            await waitForFirebaseReady();
        }

        // Inyectar Bearer token si no existe
        if (!headers.has('Authorization') && currentUser) {
            try {
                const token = await currentUser.getIdToken();
                if (token) {
                    headers.set('Authorization', `Bearer ${token}`);
                }
            } catch (tokenErr) {
                console.warn('⚠️ No se pudo obtener ID token:', tokenErr);
            }
        }

        const requestInit = { ...init, headers };
        if (requestInit.credentials === undefined) {
            requestInit.credentials = 'include';
        }

        if (input instanceof Request) {
            return originalFetch(new Request(input, requestInit));
        }

        return originalFetch(input, requestInit);
    } catch (error) {
        console.warn('⚠️ secureFetch fallback:', error);
        return originalFetch(input, init);
    }
}

// Reemplazar fetch global
window.authFetch = secureFetch;
window.fetch = secureFetch;

/**
 * Inicializar instancias de Firebase
 */
async function initializeFirebaseInstances() {
    try {
        const services = await waitForFirebaseReady();
        const { auth: authInstance, db: dbInstance } = getFirebaseServices();
        
        auth = authInstance || getAuth();
        db = dbInstance || getFirestore();
        
        console.log('✅ Instancias de Firebase inicializadas');
        return { auth, db };
    } catch (error) {
        console.error('❌ Error inicializando instancias:', error);
        return { auth: null, db: null };
    }
}

async function syncSessionWithBackend(idToken) {
    const response = await fetch('/api/login_session', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${idToken}`
        },
        body: JSON.stringify({ idToken })
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'No se pudo sincronizar la sesión');
    }

    return payload;
}

/**
 * Inicializar sistema de autenticación
 */
function initAuth() {
    waitForFirebaseReady().then(async () => {
        // Obtener instancias de Firebase
        if (!auth || !db) {
            const services = getFirebaseServices();
            auth = services.auth;
            db = services.db;
        }

        if (!auth) {
            console.error('❌ Firebase Auth no está disponible');
            return;
        }

        // Configurar listener de cambios de estado
        onAuthStateChanged(auth, async (user) => {
            if (user) {
                currentUser = user;

                try {
                    const idToken = await user.getIdToken(true);
                    const sessionResult = await syncSessionWithBackend(idToken);
                    userProfile = sessionResult.usuario || null;

                    if (!userProfile) {
                        userProfile = await getUserProfile(user.uid);
                    }

                    if (!userProfile) {
                        throw new Error('No se pudo cargar el perfil del usuario');
                    }

                    if (userProfile) {
                        if (isLoginPage()) {
                            redirectAfterLogin(userProfile);
                        }

                        // Cambio de contraseña deshabilitado temporalmente.
                        // Se conserva lógica comentada para reactivarla cuando sea necesario.
                        // if (userProfile.debeCambiarPassword && !isLoginPage() && !isChangePasswordPage()) {
                        //     showChangePasswordModal(user.uid);
                        // }
                    } else {
                        console.warn('⚠️ Usuario autenticado pero sin perfil en Firestore');
                        if (isLoginPage()) {
                            window.location.href = '/perfil';
                        }
                    }
                } catch (error) {
                    console.error('❌ Error obteniendo perfil:', error);
                    if (isLoginPage()) {
                        const errorDiv = document.getElementById('errorMessage');
                        if (errorDiv) {
                            errorDiv.classList.add('show');
                            const errorText = document.getElementById('errorText');
                            if (errorText) {
                                errorText.textContent = 'Error leyendo perfil. Intenta recargar.';
                            }
                        }
                    } else {
                        await logoutUser();
                    }
                }
            } else {
                currentUser = null;
                userProfile = null;

                if (logoutInProgress) {
                    return;
                }
            }
        });
    });
}

/**
 * Obtener perfil del usuario desde el servidor
 */
async function getUserProfile(uid) {
    try {
        await waitForFirebaseReady();

        if (!currentUser) {
            console.error('No hay usuario autenticado');
            return null;
        }

        try {
            const idToken = await currentUser.getIdToken(true);
            const resp = await fetch('/api/me', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + idToken
                },
                body: JSON.stringify({})
            });

            if (!resp.ok) {
                const txt = await resp.text();
                throw new Error('Server response: ' + resp.status + ' ' + txt);
            }

            const json = await resp.json();
            if (json.success && json.usuario) {
                return { ...json.usuario, uid: uid };
            }
            return null;
        } catch (serverErr) {
            console.error('❌ Error obteniendo perfil desde servidor:', serverErr);
            return null;
        }
    } catch (error) {
        console.error('❌ Error obteniendo perfil:', error);
        return null;
    }
}

/**
 * Login con email y password
 */
async function loginWithEmail(email, password) {
    try {
        await waitForFirebaseReady();

        if (!auth) {
            return { success: false, error: 'Firebase Auth no está disponible' };
        }

        const result = await signInWithEmailAndPassword(auth, email, password);
        console.log('✅ Login exitoso:', result.user.uid);
        return { success: true, user: result.user };
    } catch (error) {
        let errorMessage = 'Error al iniciar sesión';

        switch (error.code) {
            case 'auth/user-not-found':
                errorMessage = 'Usuario no encontrado';
                break;
            case 'auth/wrong-password':
                errorMessage = 'Contraseña incorrecta';
                break;
            case 'auth/invalid-email':
                errorMessage = 'Email inválido';
                break;
            case 'auth/user-disabled':
                errorMessage = 'Cuenta deshabilitada';
                break;
            case 'auth/too-many-login-attempts':
                errorMessage = 'Demasiados intentos de login. Intenta más tarde.';
                break;
        }

        return { success: false, error: errorMessage, code: error.code };
    }
}

/**
 * Cambiar contraseña del usuario
 */
async function changePassword(uid, newPassword) {
    /*
    try {
        await waitForFirebaseReady();

        if (!currentUser) {
            return { success: false, error: 'Usuario no autenticado' };
        }

        // Actualizar contraseña en Firebase Auth
        await updatePassword(currentUser, newPassword);

        // Actualizar flag en Firestore
        if (db) {
            const usuariosRef = collection(db, 'usuarios');
            const usuarioDoc = doc(usuariosRef, uid);
            await updateDoc(usuarioDoc, {
                debeCambiarPassword: false
            });
        }

        console.log('✅ Contraseña actualizada exitosamente');
        return { success: true, message: 'Contraseña actualizada' };
    } catch (error) {
        let errorMessage = 'Error al cambiar contraseña';

        if (error.code === 'auth/weak-password') {
            errorMessage = 'La contraseña debe tener al menos 6 caracteres';
        } else if (error.code === 'auth/requires-recent-login') {
            errorMessage = 'Debes iniciar sesión recientemente para cambiar la contraseña';
        }

        return { success: false, error: errorMessage };
    }
    */

    return { success: false, error: 'Cambio de contraseña deshabilitado temporalmente' };
}

/**
 * Logout del usuario
 */
async function logoutUser() {
    try {
        await waitForFirebaseReady();

        logoutInProgress = true;

        if (typeof bypassUnloadConfirmation === 'function') {
            bypassUnloadConfirmation();
        }

        try {
            await fetch('/logout', { method: 'POST', credentials: 'include' });
        } catch (logoutErr) {
            console.warn('⚠️ No se pudo limpiar la sesión del servidor:', logoutErr);
        }

        localStorage.removeItem('optica_user_data');

        if (auth) {
            await signOut(auth);
        }
        currentUser = null;
        userProfile = null;

        console.log('✅ Logout exitoso');
        window.location.href = '/login';
    } catch (error) {
        console.error('❌ Error al cerrar sesión:', error);
        currentUser = null;
        userProfile = null;
        window.location.href = '/login';
    } finally {
        logoutInProgress = false;
    }
}

/**
 * Redirigir después de login según el rol
 */
function redirectAfterLogin(profile) {
    if (profile.rol === 'admin') {
        window.location.href = '/';
    } else if (profile.rol === 'empleado') {
        window.location.href = '/ordenes';
    } else {
        window.location.href = '/';
    }
}

/**
 * Obtener usuario actual
 */
function getCurrentUser() {
    return currentUser;
}

/**
 * Obtener perfil del usuario actual
 */
function getCurrentUserProfile() {
    return userProfile;
}

/**
 * Verificar si el usuario es administrador
 */
function isAdmin() {
    return userProfile && userProfile.rol === 'admin';
}

/**
 * Verificar si está en página de login
 */
function isLoginPage() {
    return window.location.pathname === '/login';
}

/**
 * Verificar si está en página de cambio de contraseña
 */
function isChangePasswordPage() {
    // return window.location.pathname === '/cambiar-contrasena';
    return false;
}

/**
 * Mostrar modal de cambio de contraseña obligatorio
 */
function showChangePasswordModal(uid) {
    /*
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.style.display = 'flex';

        const confirmBtn = document.getElementById('btnConfirmChangePassword');
        if (confirmBtn) {
            confirmBtn.onclick = async () => {
                const newPassword = document.getElementById('newPassword').value;
                const confirmPassword = document.getElementById('confirmPassword').value;

                if (newPassword !== confirmPassword) {
                    showModalError('Las contraseñas no coinciden');
                    return;
                }

                if (newPassword.length < 6) {
                    showModalError('La contraseña debe tener al menos 6 caracteres');
                    return;
                }

                const result = await changePassword(uid, newPassword);
                if (result.success) {
                    modal.style.display = 'none';
                    location.reload();
                } else {
                    showModalError(result.error);
                }
            };
        }
    }
    */
    void uid;
}

/**
 * Mostrar error en modal
 */
function showModalError(message) {
    /*
    const errorDiv = document.getElementById('modalError');
    if (errorDiv) {
        errorDiv.style.display = 'flex';
        const errorText = document.getElementById('modalErrorText');
        if (errorText) {
            errorText.textContent = message;
        }
    }
    */
    void message;
}

/**
 * Validar acceso por rol
 */
function requireRole(allowedRoles) {
    if (!userProfile) {
        window.location.href = '/login';
        return false;
    }

    if (!allowedRoles.includes(userProfile.rol)) {
        window.location.href = '/';
        return false;
    }

    return true;
}

/**
 * Validar acceso a sucursal
 */
function checkSucursalAccess(sucursalId) {
    if (!userProfile) {
        return false;
    }

    if (userProfile.rol === 'admin') {
        return true;
    }

    return userProfile.sucursal_id === sucursalId;
}

/**
 * Obtener sucursal activa del admin
 */
function getActiveSucursal() {
    if (isAdmin()) {
        return localStorage.getItem('selectedSucursal') || '1';
    }
    return userProfile?.sucursal_id;
}

// Exponer API para plantillas que usan scripts clásicos en lugar de modules.
window.loginWithEmail = loginWithEmail;
window.changePassword = changePassword;
window.logoutUser = logoutUser;
window.getCurrentUser = getCurrentUser;
window.getCurrentUserProfile = getCurrentUserProfile;
window.isAdmin = isAdmin;
window.requireRole = requireRole;
window.checkSucursalAccess = checkSucursalAccess;
window.getActiveSucursal = getActiveSucursal;

// Inicializar autenticación cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
} else {
    initAuth();
}
