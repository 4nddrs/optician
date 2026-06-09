/**
 * Firebase Configuration (Modern Modular SDK v10.7.2)
 * Reemplaza la sintaxis compat obsoleta por funciones funcionales
 */

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.2/firebase-app.js';
import { getAuth, setPersistence, browserSessionPersistence } from 'https://www.gstatic.com/firebasejs/10.7.2/firebase-auth.js';
import { getFirestore } from 'https://www.gstatic.com/firebasejs/10.7.2/firebase-firestore.js';

// Estados globales
let firebaseReady = false;
let firebaseApp = null;
let auth = null;
let db = null;

console.log('📡 firebase-config.js módulo cargado');

/**
 * Inicializar Firebase con configuración del servidor
 */
function initializeFirebaseApp() {
    if (firebaseReady) {
        console.log('⚠️ Firebase ya está inicializado, saltando...');
        return { firebaseApp, auth, db };
    }

    try {
        // Obtener configuración inyectada por el servidor desde .env
        const defaultConfig = {
            apiKey: "AIzaSyDemoKey123456789",
            authDomain: "optica-demo.firebaseapp.com",
            projectId: "optica-demo",
            storageBucket: "optica-demo.appspot.com",
            messagingSenderId: "123456789",
            appId: "1:123456789:web:abc123def456"
        };

        const firebaseConfig = (window.__FIREBASE_CONFIG && window.__FIREBASE_CONFIG.apiKey) 
            ? window.__FIREBASE_CONFIG 
            : defaultConfig;

        if (!firebaseConfig.apiKey || firebaseConfig.apiKey === defaultConfig.apiKey) {
            console.warn('⚠️ FIREBASE API key missing or using placeholder. Set `FIREBASE_API_KEY` in your .env');
            console.warn('   Config:', firebaseConfig);
        }

        console.log('🔧 Inicializando Firebase App con config:', {
            apiKey: firebaseConfig.apiKey ? '[REDACTED]' : 'MISSING',
            projectId: firebaseConfig.projectId,
            authDomain: firebaseConfig.authDomain
        });

        // Inicializar Firebase App
        firebaseApp = initializeApp(firebaseConfig);
        console.log('✅ Firebase App inicializado');

        // Obtener Auth y Firestore
        auth = getAuth(firebaseApp);
        console.log('✅ Auth obtenido');
        
        db = getFirestore(firebaseApp);
        console.log('✅ Firestore obtenido');

        // Configurar persistencia de sesión
        setPersistence(auth, browserSessionPersistence)
            .then(() => {
                console.log('✅ Persistencia de sesión configurada (browserSessionPersistence)');
            })
            .catch((error) => {
                console.error('⚠️ Error configurando persistencia:', error);
            });

        // Debug mode
        window.DEBUG = location.hostname === 'localhost' || location.hostname === '127.0.0.1';

        if (window.DEBUG) {
            console.log('🔍 Firebase Debug Mode Enabled');
            console.log('📊 Firebase App:', firebaseApp.name);
            console.log('🔑 Auth instance:', auth?.tenantId || 'default tenant');
        }

        firebaseReady = true;

        // Emitir evento personalizado
        window.dispatchEvent(new Event('firebase-initialized'));
        console.log('📢 Evento firebase-initialized disparado');

        return { firebaseApp, auth, db };
    } catch (error) {
        console.error('❌ Error inicializando Firebase:', error);
        console.error('   Stack:', error.stack);
        firebaseReady = false;
        return null;
    }
}

/**
 * Esperar a que Firebase esté listo (para scripts globales que aún usan window.auth/db)
 */
export function waitForFirebaseReady() {
    return new Promise((resolve) => {
        if (firebaseReady && auth && db) {
            console.log('✅ Firebase ya está listo (immediate resolve)');
            resolve({ auth, db });
            return;
        }

        console.log('⏳ Esperando a que Firebase esté listo...');

        const checkInterval = setInterval(() => {
            if (firebaseReady && auth && db) {
                console.log('✅ Firebase está listo (polling detected)');
                clearInterval(checkInterval);
                resolve({ auth, db });
            }
        }, 50);

        // Timeout de seguridad
        setTimeout(() => {
            clearInterval(checkInterval);
            if (firebaseReady && auth && db) {
                console.log('✅ Firebase está listo (timeout fallback)');
                resolve({ auth, db });
            } else {
                console.warn('⚠️ Firebase aún no está disponible después de 5s timeout');
                console.warn('   State:', { firebaseReady, auth: !!auth, db: !!db });
                resolve({ auth, db }); // Resolver aunque no esté listo
            }
        }, 5000);
    });
}

/**
 * Obtener instancias de Firebase (para uso modular)
 */
export function getFirebaseServices() {
    if (!firebaseReady) {
        console.warn('⚠️ Firebase services no están listos, intentando inicializar...');
        initializeFirebaseApp();
    }
    return { firebaseApp, auth, db };
}

/**
 * Inicializar y exponer globalmente para compatibilidad
 * Se ejecuta inmediatamente al cargar el módulo
 */
console.log('🚀 Iniciando IIFE de firebase-config...');

(async function() {
    try {
        // Pequeña pausa para permitir que window.__FIREBASE_CONFIG se inyecte desde HTML
        console.log('⏳ Esperando 100ms para que __FIREBASE_CONFIG se inyecte...');
        await new Promise(r => setTimeout(r, 100));
        
        console.log('🔍 Verificando __FIREBASE_CONFIG:', !!window.__FIREBASE_CONFIG);
        
        console.log('📡 Llamando a initializeFirebaseApp()...');
        const result = initializeFirebaseApp();
        
        console.log('📊 Resultado de inicialización:', {
            firebaseReady,
            firebaseApp: !!firebaseApp,
            auth: !!auth,
            db: !!db
        });
        
    } catch (error) {
        console.error('❌ Error en IIFE de firebase-config:', error);
        console.error('   Stack:', error.stack);
    }
})();

// Exponer globalmente para scripts que dependen de window.auth/db
console.log('🔗 Exponiendo propiedades globales...');

Object.defineProperty(window, 'firebaseReady', {
    get: () => {
        return firebaseReady;
    },
    enumerable: true
});

Object.defineProperty(window, 'auth', {
    get: () => auth,
    enumerable: true
});

Object.defineProperty(window, 'db', {
    get: () => db,
    enumerable: true
});

console.log('✅ firebase-config.js inicialización completada');
