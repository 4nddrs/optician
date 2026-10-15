"""Regression tests for the navigation-latency change set (S1-S4).

Read-only: every mutator path is exercised against a stub DB; the real
Firestore is only *read*, and only when OPTICA_PROD_READS=1 is set.

Run:  cd <repo> && venv/bin/python -m unittest tests.test_perf_changes -v
"""
import os
import sys
import time
import unittest
from datetime import datetime

sys.path.insert(0, os.getcwd())

import firebase_auth as fa  # noqa: E402
import firebase_config as fb  # noqa: E402
import app as app_module  # noqa: E402

READS = os.getenv('OPTICA_PROD_READS', '0') == '1'


class _FakeDoc:
    def __init__(self, sink):
        self.sink = sink

    def set(self, d):
        self.sink.append(('set', d))

    def update(self, d):
        self.sink.append(('update', d))

    def delete(self):
        self.sink.append(('delete', None))

    def get(self):
        class _R:
            exists = False
        return _R()


class _FakeDB:
    def __init__(self, sink):
        self.sink = sink

    def collection(self, name):
        return self

    def document(self, uid):
        return _FakeDoc(self.sink)


class _FakeAuth:
    def update_user(self, *a, **k):
        pass

    def delete_user(self, *a, **k):
        pass

    def create_user(self, **k):
        class _U:
            uid = 'new-uid-999'
            email = k.get('email')
        return _U()


class S1_UserCacheTest(unittest.TestCase):
    UID = 'probe-uid-123'
    PERFIL = {'nombre': 'X', 'rol': 'admin', 'activo': True, 'uid': UID, 'sucursal_id': 'S1'}

    def setUp(self):
        self._db, self._auth = fa.db, fa.auth
        fa._invalidate_user_cache()

    def tearDown(self):
        fa.db, fa.auth = self._db, self._auth
        fa._invalidate_user_cache()

    def _seed(self):
        fa._user_cache[self.UID] = {'data': dict(self.PERFIL), 'timestamp': datetime.now()}

    def test_every_usuarios_writer_invalidates(self):
        """S1: all six write paths that touch `usuarios` drop the cached profile."""
        fa.auth = _FakeAuth()
        cases = [
            ('actualizar_usuario', lambda: fa.actualizar_usuario(self.UID, {'nombre': 'Y'})),
            ('actualizar_perfil_usuario', lambda: fa.actualizar_perfil_usuario(self.UID, {'nombre': 'Y'})),
            ('cambiar_contrasena', lambda: fa.cambiar_contrasena(self.UID, 'abcdef')),
            ('eliminar_usuario', lambda: fa.eliminar_usuario(self.UID)),
            ('eliminar_usuario_permanente', lambda: fa.eliminar_usuario_permanente(self.UID)),
        ]
        for name, call in cases:
            with self.subTest(fn=name):
                fa.db = _FakeDB([])
                self._seed()
                res = call()
                self.assertTrue(res.get('success'), res)
                self.assertNotIn(self.UID, fa._user_cache, f"{name} left a stale cache entry")

    def test_crear_usuario_invalidates_new_uid(self):
        """S1: crear_usuario_empleado invalidates the freshly created uid."""
        fa.auth = _FakeAuth()
        fa.db = _FakeDB([])
        fa._user_cache['new-uid-999'] = {'data': dict(self.PERFIL), 'timestamp': datetime.now()}
        res = fa.crear_usuario_empleado('a@b.com', 'abcdef', 'N', 'empleado', 'S1')
        self.assertTrue(res.get('success'), res)
        self.assertNotIn('new-uid-999', fa._user_cache)

    def test_ttl_is_a_hard_bound_without_sliding(self):
        """S1: TTL bounds staleness; reads never refresh the timestamp."""
        class _Doc:
            n = 0

            def get(self):
                _Doc.n += 1

                class _R:
                    exists = True

                    def to_dict(self):
                        return {'nombre': 'X', 'activo': True, 'rol': 'admin'}
                return _R()

        class _DB:
            def collection(self, name):
                return self

            def document(self, uid):
                return _Doc()

        fa.db = _DB()
        fa._user_cache_duration = 1
        fa._invalidate_user_cache()
        try:
            fa.obtener_usuario_por_uid('u1')
            ts = fa._user_cache['u1']['timestamp']
            fa.obtener_usuario_por_uid('u1')
            fa.obtener_usuario_por_uid('u1')
            self.assertEqual(_Doc.n, 1, "cache did not serve within TTL")
            self.assertEqual(fa._user_cache['u1']['timestamp'], ts, "timestamp refreshed on read (sliding TTL)")
            time.sleep(1.15)
            fa.obtener_usuario_por_uid('u1')
            self.assertEqual(_Doc.n, 2, "expired entry was not re-read")
        finally:
            fa._user_cache_duration = int(os.getenv('USER_CACHE_DURATION', os.getenv('CACHE_DURATION', 60)))

    def test_inactive_cached_profile_is_rejected(self):
        """S1: `activo` is enforced even when the profile comes from the cache."""
        from flask import session as flask_session
        self._seed()
        fa._user_cache[self.UID] = {'data': dict(self.PERFIL, activo=False), 'timestamp': datetime.now()}
        with app_module.app.test_request_context('/'):
            flask_session['user_uid'] = self.UID
            flask_session['user_role'] = 'admin'
            self.assertIsNone(app_module._authenticate_from_session())
        fa._user_cache[self.UID] = {'data': dict(self.PERFIL, activo=True), 'timestamp': datetime.now()}
        with app_module.app.test_request_context('/'):
            flask_session['user_uid'] = self.UID
            flask_session['user_role'] = 'admin'
            self.assertIsNotNone(app_module._authenticate_from_session())

    def test_shallow_copy_does_not_share_top_level(self):
        """S1: the returned dict is a copy; top-level mutation cannot poison the cache."""
        fa._user_cache['nest'] = {'data': {'nombre': 'N'}, 'timestamp': datetime.now()}
        r = fa.obtener_usuario_por_uid('nest')
        r['nombre'] = 'CHANGED'
        self.assertEqual(fa.obtener_usuario_por_uid('nest')['nombre'], 'N')


class S4_ParallelTest(unittest.TestCase):
    def test_order_preserved_and_exceptions_propagate(self):
        """S4: _parallel preserves argument order and never swallows a failure."""
        self.assertEqual(app_module._parallel(lambda: [1, 2], lambda: [3, 4]), [[1, 2], [3, 4]])
        with self.assertRaises(ValueError):
            app_module._parallel(lambda: 1, lambda: (_ for _ in ()).throw(ValueError('boom')))


class S3_HeaderTest(unittest.TestCase):
    def setUp(self):
        self.c = app_module.app.test_client()

    def test_static_is_no_cache_with_etag_304(self):
        """S3: /static/* -> `no-cache` (revalidate), never `no-store`."""
        r = self.c.get('/static/js/auth.js')
        cc = r.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cc)
        self.assertNotIn('no-store', cc)
        etag = r.headers.get('ETag')
        self.assertTrue(etag)
        r2 = self.c.get('/static/js/auth.js', headers={'If-None-Match': etag})
        self.assertEqual(r2.status_code, 304)
        self.assertEqual(len(r2.data), 0)

    def test_non_static_keeps_no_store(self):
        """S3: HTML/JSON/redirects keep the strict no-store header."""
        for path in ['/login', '/api/sucursales', '/nope-page']:
            with self.subTest(path=path):
                self.assertIn('no-store', self.c.get(path).headers.get('Cache-Control', ''))

    def test_static_prefix_does_not_overmatch(self):
        """S3: only paths under /static/ take the new branch."""
        for path in ['/static', '/staticx/foo']:
            with self.subTest(path=path):
                self.assertIn('no-store', self.c.get(path).headers.get('Cache-Control', ''))


@unittest.skipUnless(READS, 'set OPTICA_PROD_READS=1 to run read-only route equivalence checks')
class S4_RouteEquivalenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = None
        for d in fb.db.collection('usuarios').stream():
            u = d.to_dict(); u['uid'] = d.id
            if (u.get('rol') or '').lower() == 'admin' and u.get('activo', True):
                cls.admin = u
                break
        cls.ordenes = fb.get_all_orders()

    def _client(self):
        cl = app_module.app.test_client()
        with cl.session_transaction() as s:
            s['user_uid'] = self.admin['uid']
            s['user_role'] = self.admin.get('rol', '')
            s['user_name'] = self.admin.get('nombre', '')
        return cl

    def test_converted_routes_respond_200(self):
        oid = self.ordenes[0]['id']
        for path in ['/', '/ordenes', '/ordenes/nueva', f'/ordenes/{oid}',
                     f'/ordenes/{oid}/editar', '/api/control/datos']:
            with self.subTest(path=path):
                self.assertEqual(self._client().get(path).status_code, 200)

    def test_ver_orden_skips_employee_lookup_when_no_id(self):
        """S4: get_user_by_id must not be called when id_empleado is falsy."""
        real = (fb.get_order_by_id, fb.get_client_by_id, fb.get_branch_by_id, fb.get_user_by_id)
        base = dict(real[0](self.ordenes[0]['id']))
        calls = {'n': 0}
        try:
            base.pop('id_empleado', None)
            base['nombre_empleado'] = 'FALLBACK-NAME'
            fb.get_order_by_id = lambda oid: dict(base)
            fb.get_client_by_id = lambda cid: {'id': cid, 'nombre_completo': 'C'}
            fb.get_branch_by_id = lambda bid: {'id': bid, 'nombre': 'S'}

            def _user(u):
                calls['n'] += 1
                return {'nombre': 'SHOULD-NOT-RENDER'}
            fb.get_user_by_id = _user
            html = self._client().get(f"/ordenes/{base['id']}").get_data(as_text=True)
            self.assertEqual(calls['n'], 0)
            self.assertIn('FALLBACK-NAME', html)
        finally:
            fb.get_order_by_id, fb.get_client_by_id, fb.get_branch_by_id, fb.get_user_by_id = real


if __name__ == '__main__':
    unittest.main(verbosity=2)
