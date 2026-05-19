// Esperar a que todos los scripts de Firebase estén listos
let firebaseReady = false;
let initAttempts = 0;
const MAX_ATTEMPTS = 50; // 5 segundos máximo

function checkFirebaseReady() {
    initAttempts++;
    
    if (typeof firebase !== 'undefined' && firebase.apps !== undefined) {
        if (!firebaseReady) {
            initializeFirebaseApp();
        }
        return true;
    }
    
    if (initAttempts >= MAX_ATTEMPTS) {
        console.error('❌ Firebase no se cargó después de 50 intentos');
        console.error('❌ Verifica que los CDNs de Firebase sean accesibles');
        return false;
    }
    
    return false;
}

function initializeFirebaseApp() {
    if (firebaseReady) return; // Evitar reinicializar
    
    try {
        // Firebase configuration
        // Primero usar la configuración inyectada por el servidor desde .env
        const defaultConfig = {
            apiKey: "AIzaSyDemoKey123456789",
            authDomain: "optica-demo.firebaseapp.com",
            projectId: "optica-demo",
            storageBucket: "optica-demo.appspot.com",
            messagingSenderId: "123456789",
            appId: "1:123456789:web:abc123def456"
        };

        const firebaseConfig = (window.__FIREBASE_CONFIG && window.__FIREBASE_CONFIG.apiKey) ? window.__FIREBASE_CONFIG : defaultConfig;

        if (!firebaseConfig.apiKey || firebaseConfig.apiKey === defaultConfig.apiKey) {
            console.warn('⚠️ FIREBASE API key missing or using placeholder. Set `FIREBASE_API_KEY` in your .env');
        }

        // Initialize Firebase - Solo si no está inicializado
        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
            console.log('✅ Firebase inicializado correctamente');
        }

        // Get Firebase services - Exponer globalmente
        window.auth = firebase.auth();
        window.db = firebase.firestore();

        // Configurar persistencia
        firebase.auth().setPersistence(firebase.auth.Auth.Persistence.LOCAL)
            .then(() => {
                console.log('✅ Persistencia de sesión configurada');
            })
            .catch((error) => {
                console.error('⚠️ Error configurando persistencia:', error);
            });

        // Debug mode
        window.DEBUG = location.hostname === 'localhost' || location.hostname === '127.0.0.1';

        if (window.DEBUG) {
            console.log('🔍 Firebase Debug Mode Enabled');
            console.log('📊 Firebase Apps:', firebase.apps.length, 'app(s)');
        }

        firebaseReady = true;
        // Emitir evento personalizado
        window.dispatchEvent(new Event('firebase-initialized'));

    } catch (error) {
        console.error('❌ Error inicializando Firebase:', error);
        firebaseReady = false;
    }
}

// Verificar Firebase cada 100ms
const firebaseCheckInterval = setInterval(() => {
    if (checkFirebaseReady()) {
        clearInterval(firebaseCheckInterval);
    }
}, 100);

// Limpiar intervalo después de 5 segundos de todas formas
setTimeout(() => {
    clearInterval(firebaseCheckInterval);
    if (!firebaseReady) {
        console.error('❌ Firebase no se inicializó. Verifica los CDNs.');
    }
}, 5000);

console.log('📡 Esperando a que Firebase se cargue desde los CDNs...');
