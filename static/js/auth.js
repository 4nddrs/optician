/**
 * Módulo de Autenticación
 * Maneja login, logout, y autorización
 */

// Estados globales
let currentUser = null;
let userProfile = null;

const originalFetch = window.fetch.bind(window);

async function secureFetch(input, init = {}) {
    try {
        const requestUrl = input instanceof Request ? input.url : String(input);
        const url = new URL(requestUrl, window.location.origin);

        if (url.origin !== window.location.origin) {
            return originalFetch(input, init);
        }

        const headers = new Headers(input instanceof Request ? input.headers : (init.headers || {}));

        if (typeof firebase !== 'undefined' && firebase.apps.length && !firebase.auth().currentUser) {
            await waitForFirebaseReady();
        }

        if (!headers.has('Authorization') && typeof firebase !== 'undefined' && firebase.apps.length && firebase.auth().currentUser) {
            const token = await firebase.auth().currentUser.getIdToken();
            if (token) {
                headers.set('Authorization', `Bearer ${token}`);
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

window.authFetch = secureFetch;
window.fetch = secureFetch;

/**
 * Esperar a que Firebase esté listo
 */
function waitForFirebaseReady() {
    return new Promise((resolve) => {
        // Comprobar si ya está listo
        if (window.firebaseReady && typeof firebase !== 'undefined' && firebase.apps.length > 0) {
            resolve();
            return;
        }

        // Escuchar evento firebase-initialized
        window.addEventListener('firebase-initialized', () => {
            resolve();
        }, { once: true });

        // Timeout de seguridad
        setTimeout(() => {
            if (typeof firebase !== 'undefined' && firebase.apps.length > 0) {
                resolve();
            } else {
                console.warn('⚠️ Firebase aún no está disponible, pero continuando...');
                resolve();
            }
        }, 3000);
    });
}

/**
 * Inicializar sistema de autenticación
 */
function initAuth() {
    waitForFirebaseReady().then(() => {
        // Una vez Firebase esté listo, inicializar auth state listener
        if (typeof firebase === 'undefined' || !firebase.apps.length) {
            console.error('❌ Firebase no está disponible');
            return;
        }

        firebase.auth().onAuthStateChanged(async function(user) {
            if (user) {
                currentUser = user;

                try {
                    // Force-refresh ID token to avoid race conditions where client
                    // requests to Firestore arrive without a valid token.
                    try {
                        await user.getIdToken();
                    } catch (tokenErr) {
                        console.warn('⚠️ No se pudo refrescar ID token:', tokenErr);
                    }

                    // Intentar obtener perfil del usuario desde Firestore
                    userProfile = await getUserProfile(user.uid);

                    // Si no se obtuvo perfil, intentar una vez más tras breve espera
                    if (!userProfile) {
                        console.warn('⚠️ Usuario sin perfil en Firestore (primer intento). Reintentando...');
                        await new Promise(r => setTimeout(r, 500));
                        userProfile = await getUserProfile(user.uid);
                    }

                    // Verificar si el usuario está activo
                    const statusCheck = await fetch('/api/auth/check-status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ uid: user.uid })
                    });
                    const statusResult = await statusCheck.json();

                    if (!statusResult.success || !statusResult.activo) {
                        console.warn('⚠️ El usuario no está activo o hubo un error al verificar. Cerrando sesión.');
                        const errorDiv = document.getElementById('errorMessage');
                        if (errorDiv) {
                            errorDiv.classList.add('show');
                            document.getElementById('errorText').textContent = 'Tu cuenta está desactivada. Contacta al administrador.';
                        }
                        await firebase.auth().signOut();
                        return; // Detener la ejecución
                    }


                    if (userProfile) {
                        // Usuario está autenticado y tiene perfil
                        if (isLoginPage()) {
                            redirectAfterLogin(userProfile);
                        }

                        // Verificar si debe cambiar contraseña
                        if (userProfile.debeCambiarPassword && !isLoginPage() && !isChangePasswordPage()) {
                            showChangePasswordModal(user.uid);
                        }
                    } else {
                        // Usuario autenticado pero sin perfil - no cerrar sesión inmediatamente
                        // Mostrar advertencia en consola y redirigir a página para completar perfil
                        console.warn('⚠️ Usuario autenticado pero no existe perfil en Firestore. No se cerrará sesión automáticamente.');
                        if (isLoginPage()) {
                            // Si estamos en la página de login, redirigir a /perfil para completar datos
                            window.location.href = '/perfil';
                        }
                    }
                } catch (error) {
                    console.error('❌ Error obteniendo perfil:', error);
                    // Evitar logout inmediato; mostrar mensaje y permitir al usuario reintentar
                    // Si estamos en login, mostramos error; de otro modo, forzar logout como último recurso
                    if (isLoginPage()) {
                        const errorDiv = document.getElementById('errorMessage');
                        if (errorDiv) {
                            errorDiv.classList.add('show');
                            document.getElementById('errorText').textContent = 'Error leyendo perfil. Intenta recargar.';
                        }
                    } else {
                        logoutUser();
                    }
                }
            } else {
                currentUser = null;
                userProfile = null;

                // Si no está en login, redirigir
                if (!isLoginPage() && !isChangePasswordPage()) {
                    window.location.href = '/login';
                }
            }
        });
    });
}

/**
 * Obtener perfil del usuario desde Firestore
 */
async function getUserProfile(uid) {
    try {
        await waitForFirebaseReady();
        
        if (typeof firebase === 'undefined' || !firebase.apps.length) {
            console.error('Firebase no disponible');
            return null;
        }

        // Llamar al endpoint del servidor que verifica el ID token y devuelve el perfil
        try {
            const idToken = await firebase.auth().currentUser.getIdToken();
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

        if (typeof firebase === 'undefined' || !firebase.apps.length) {
            return { success: false, error: 'Firebase no está disponible' };
        }

        const result = await firebase.auth().signInWithEmailAndPassword(email, password);

        try {
            // Sincronizar el perfil con el servidor antes de permitir navegación a vistas protegidas.
            userProfile = await getUserProfile(result.user.uid);
        } catch (profileErr) {
            console.warn('⚠️ No se pudo sincronizar el perfil en login:', profileErr);
        }
        
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
    try {
        await waitForFirebaseReady();

        const user = firebase.auth().currentUser;
        if (!user) {
            return { success: false, error: 'Usuario no autenticado' };
        }

        await user.updatePassword(newPassword);
        
        // Actualizar flag en Firestore
        const db = firebase.firestore();
        await db.collection('usuarios').doc(uid).update({
            debeCambiarPassword: false
        });
        
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
}

/**
 * Logout del usuario
 */
async function logoutUser() {
    try {
        await waitForFirebaseReady();

        if (typeof firebase === 'undefined' || !firebase.apps.length) {
            window.location.href = '/login';
            return;
        }

        // Bypass the unload confirmation before signing out
        if (typeof bypassUnloadConfirmation === 'function') {
            bypassUnloadConfirmation();
        }

        try {
            await fetch('/logout', { method: 'GET', credentials: 'include' });
        } catch (logoutErr) {
            console.warn('⚠️ No se pudo limpiar la sesión del servidor:', logoutErr);
        }

        await firebase.auth().signOut();
        currentUser = null;
        userProfile = null;
        
        console.log('✅ Logout exitoso');
        window.location.href = '/login';
    } catch (error) {
        console.error('❌ Error al cerrar sesión:', error);
        // Still try to redirect
        window.location.href = '/login';
    }
}

/**
 * Redirigir después de login según el rol
 */
function redirectAfterLogin(profile) {
    if (profile.rol === 'admin') {
        // Admin va al dashboard
        window.location.href = '/';
    } else if (profile.rol === 'empleado') {
        // Empleado va al módulo de órdenes de su sucursal
        window.location.href = '/ordenes';
    } else {
        // Por defecto al dashboard
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
    return window.location.pathname === '/cambiar-contrasena';
}

/**
 * Mostrar modal de cambio de contraseña obligatorio
 */
function showChangePasswordModal(uid) {
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.style.display = 'flex';
        
        // Configurar botón de confirmación
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
}

/**
 * Mostrar error en modal
 */
function showModalError(message) {
    const errorDiv = document.getElementById('modalError');
    if (errorDiv) {
        errorDiv.style.display = 'flex';
        document.getElementById('modalErrorText').textContent = message;
    }
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
    
    // Admin tiene acceso a todas las sucursales
    if (userProfile.rol === 'admin') {
        return true;
    }
    
    // Empleado solo tiene acceso a su propia sucursal
    return userProfile.sucursal_id === sucursalId;
}

/**
 * Obtener sucursal activa del admin
 */
function getActiveSucursal() {
    if (isAdmin()) {
        return localStorage.getItem('selectedSucursal') || '1';
    }
    return userProfile.sucursal_id;
}

// Inicializar autenticación cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
} else {
    initAuth();
}
