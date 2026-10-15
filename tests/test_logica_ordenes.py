"""Tests de la logica de estados, resumen del dashboard y lecturas por lote.

RED primero: estos tests describen el contrato de S1, S2, S3 y S5 y fallan
hasta que se implementen. Solo stdlib (unittest): el repo no trae runner.

Ningun test escribe en Firestore: los efectos se comprueban con stubs.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_config as fb
import firebase_auth as fa
import app as app_module

ESTADOS = {'Pendiente', 'Progreso', 'Listo', 'Entregado'}


# --------------------------------------------------------------------------
# S1 — un unico lugar declara los estados
# --------------------------------------------------------------------------
class TestEstadosCanonicos(unittest.TestCase):
    def test_s1_el_backend_declara_los_cuatro_estados(self):
        self.assertTrue(hasattr(fb, 'ESTADOS_ORDEN'), 'falta fb.ESTADOS_ORDEN')
        self.assertEqual(set(fb.ESTADOS_ORDEN), ESTADOS)

    def test_s1_la_ui_ofrece_exactamente_los_mismos(self):
        ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'templates', 'ordenes.html')
        with open(ruta, encoding='utf-8') as fh:
            html = fh.read()
        import re
        # Solo los selects de ESTADO. Un regex sobre todo el archivo tambien captura
        # el <option> del filtro de sucursal (value="{{ sucursal.id }}"), que no es un estado.
        bloques = re.findall(
            r'<select id="(?:filterEstado|nuevoEstado)"[^>]*>(.*?)</select>', html, re.S)
        self.assertEqual(len(bloques), 2,
                         'no se encontraron los dos selects de estado (filterEstado / nuevoEstado)')
        for i, bloque in enumerate(bloques):
            valores = {v for v in re.findall(r'<option value="([^"]*)"', bloque) if v}
            self.assertEqual(valores, ESTADOS,
                             f'el select de estado #{i + 1} ofrece {valores}, se esperaban {ESTADOS}')


# --------------------------------------------------------------------------
# S2 — el resumen del dashboard siempre suma
# --------------------------------------------------------------------------
class TestResumenDashboard(unittest.TestCase):
    """S2: el resumen se construye desde los totales agregados (S4), no desde la
    lista topada en MAX_ORDERS_LIMIT."""

    def _resumen(self, totales):
        self.assertTrue(hasattr(app_module, '_resumen_ordenes'),
                        'falta app._resumen_ordenes(totales)')
        return app_module._resumen_ordenes(totales)

    def test_s2_invariante_total_igual_a_pendientes_mas_entregadas(self):
        casos = [
            {'total': 8, 'entregadas': 1},
            {'total': 0, 'entregadas': 0},
            {'total': 5, 'entregadas': 0},
            {'total': 3, 'entregadas': 3},
            {'total': 100, 'entregadas': 37},
            {},
        ]
        for totales in casos:
            with self.subTest(totales=totales):
                r = self._resumen(totales)
                self.assertEqual(r['total'], r['pendientes'] + r['entregadas'],
                                 f'no suma con {totales}')
                self.assertEqual(r['total'], int((totales or {}).get('total') or 0))

    def test_s2_una_orden_en_proceso_o_lista_no_se_pierde(self):
        # 3 ordenes, 1 entregada -> las 2 restantes cuentan como pendientes,
        # sin importar si su estado es Pendiente, Progreso o Listo.
        r = self._resumen({'total': 3, 'entregadas': 1})
        self.assertEqual(r['pendientes'], 2)
        self.assertEqual(r['entregadas'], 1)

    def test_s2_no_depende_del_tope_de_100(self):
        r = self._resumen({'total': 250, 'entregadas': 10})
        self.assertEqual(r['total'], 250, 'el total no debe toparse en 100')
        self.assertEqual(r['pendientes'], 240)

    def test_s2_entregadas_mayor_que_total_no_da_pendientes_negativos(self):
        r = self._resumen({'total': 2, 'entregadas': 5})
        self.assertGreaterEqual(r['pendientes'], 0)


# --------------------------------------------------------------------------
# S3 — el estado se valida antes de escribir
# --------------------------------------------------------------------------
class TestValidacionEstado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.uid = next((d.id for d in fb.db.collection('usuarios').limit(1).stream()), None)
        cls.perfil = fa.obtener_usuario_por_uid(cls.uid) if cls.uid else None
        cls.orden_id = next((d.id for d in fb.db.collection('ordenes_trabajo').limit(1).stream()), None)

    def _cliente_autenticado(self):
        cl = app_module.app.test_client()
        with cl.session_transaction() as s:
            s['user_uid'] = self.uid
            s['user_role'] = (self.perfil or {}).get('rol', '')
        return cl

    def setUp(self):
        if not self.orden_id:
            self.skipTest('no hay ordenes para probar')
        self.escrituras = []
        self._real = fb.update_order_status
        fb.update_order_status = lambda oid, est: self.escrituras.append((oid, est))

    def tearDown(self):
        fb.update_order_status = self._real

    def test_s3_rechaza_estado_invalido_y_no_escribe(self):
        cl = self._cliente_autenticado()
        r = cl.put(f'/api/ordenes/{self.orden_id}/estado', json={'estado': 'Inventado'})
        self.assertEqual(r.status_code, 400, f'se esperaba 400, llego {r.status_code}')
        self.assertEqual(self.escrituras, [], 'no debe escribir con un estado invalido')
        self.assertIn('error', r.get_json())

    def test_s3_rechaza_estado_vacio(self):
        cl = self._cliente_autenticado()
        r = cl.put(f'/api/ordenes/{self.orden_id}/estado', json={'estado': ''})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.escrituras, [])

    def test_s3_acepta_los_cuatro_canonicos(self):
        cl = self._cliente_autenticado()
        for estado in sorted(ESTADOS):
            with self.subTest(estado=estado):
                self.escrituras.clear()
                r = cl.put(f'/api/ordenes/{self.orden_id}/estado', json={'estado': estado})
                self.assertEqual(r.status_code, 200, f'{estado} deberia aceptarse')
                self.assertEqual(self.escrituras, [(self.orden_id, estado)])

    def test_s3_rechaza_estado_con_otra_capitalizacion(self):
        cl = self._cliente_autenticado()
        r = cl.put(f'/api/ordenes/{self.orden_id}/estado', json={'estado': 'pendiente'})
        self.assertEqual(r.status_code, 400, "'pendiente' en minuscula no es canonico")
        self.assertEqual(self.escrituras, [])


# --------------------------------------------------------------------------
# S5 — lecturas por lote en vez de una por orden
# --------------------------------------------------------------------------
class _Snap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._d = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._d)


class _DocRef:
    def __init__(self, parent, doc_id):
        self.parent, self.doc_id = parent, doc_id

    def get(self):
        self.parent.single_gets += 1
        return _Snap(self.doc_id, self.parent.datos.get(self.doc_id))


class _Query:
    def __init__(self, parent, ids):
        self.parent, self.ids = parent, ids

    def stream(self):
        self.parent.in_queries += 1
        self.parent.lotes.append(list(self.ids))
        return [_Snap(i, self.parent.datos[i]) for i in self.ids if i in self.parent.datos]


class _Collection:
    def __init__(self, parent, name):
        self.parent, self.name = parent, name

    def document(self, doc_id):
        return _DocRef(self.parent, doc_id)

    def where(self, field, op, values):
        return _Query(self.parent, values)

    def limit(self, n):
        return self

    def stream(self):
        self.parent.single_gets += 1
        return [_Snap(k, v) for k, v in self.parent.datos.items()]


class _FakeDB:
    def __init__(self, datos):
        self.datos = datos
        self.single_gets = 0
        self.in_queries = 0
        self.lotes = []

    def collection(self, name):
        return _Collection(self, name)


class TestGetOrdersByIds(unittest.TestCase):
    def _ejecutar(self, ids, datos):
        fake = _FakeDB(datos)
        real = fb.db
        fb.db = fake
        try:
            res = fb.get_orders_by_ids(ids)
        finally:
            fb.db = real
        return res, fake

    def test_s5_no_hace_una_lectura_por_orden(self):
        datos = {f'o{i}': {'estado': 'Pendiente', 'n': i} for i in range(5)}
        res, fake = self._ejecutar(list(datos), datos)
        self.assertEqual(fake.single_gets, 0,
                         f'hizo {fake.single_gets} lecturas individuales; debe usar consultas in')
        self.assertEqual(len(res), 5)

    def test_s5_preserva_el_orden_solicitado(self):
        datos = {f'o{i}': {'n': i} for i in range(5)}
        ids = ['o3', 'o0', 'o4', 'o1', 'o2']
        res, _ = self._ejecutar(ids, datos)
        self.assertEqual([r['id'] for r in res], ids)

    def test_s5_deduplica(self):
        datos = {'o1': {'n': 1}, 'o2': {'n': 2}}
        res, _ = self._ejecutar(['o1', 'o2', 'o1', 'o2'], datos)
        self.assertEqual([r['id'] for r in res], ['o1', 'o2'])

    def test_s5_ignora_ids_vacios_o_inexistentes(self):
        datos = {'o1': {'n': 1}}
        res, _ = self._ejecutar(['', None, 'o1', 'fantasma'], datos)
        self.assertEqual([r['id'] for r in res], ['o1'])

    def test_s5_lista_vacia_no_consulta(self):
        res, fake = self._ejecutar([], {})
        self.assertEqual(res, [])
        self.assertEqual(fake.in_queries, 0)
        self.assertEqual(fake.single_gets, 0)

    def test_s5_trocea_en_lotes_de_30(self):
        datos = {f'o{i}': {'n': i} for i in range(65)}
        res, fake = self._ejecutar(list(datos), datos)
        self.assertEqual(len(res), 65)
        self.assertEqual(fake.in_queries, 3, f'65 ids deben dar 3 consultas, dio {fake.in_queries}')
        for lote in fake.lotes:
            self.assertLessEqual(len(lote), 30, f'lote de {len(lote)} excede el maximo de 30')


if __name__ == '__main__':
    unittest.main(verbosity=2)
