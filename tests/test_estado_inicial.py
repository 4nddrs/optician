"""Regla: una orden registrada con fecha de entrega ya pasada nace como Entregado.

Decision del usuario: "si registro una orden con fecha pasada a la actual, el
estado de la orden es Entregado automaticamente". Limite elegido: solo si la
fecha es ANTERIOR a hoy (una entrega de hoy todavia esta pendiente), y solo al
crear. La comparacion usa la fecha local de la tienda, no UTC.

RED primero: `_estado_inicial_orden` todavia no existe.

Solo stdlib. Ninguna prueba escribe en Firestore: `create_order` va con stub.
"""
import os
import sys
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_config as fb
import firebase_auth as fa
import app as app_module

HOY = date(2026, 10, 15)


class TestEstadoInicialOrden(unittest.TestCase):
    def _estado(self, fecha, hoy=HOY):
        self.assertTrue(hasattr(app_module, '_estado_inicial_orden'),
                        'falta app._estado_inicial_orden(fecha_entrega, hoy=None)')
        return app_module._estado_inicial_orden(fecha, hoy=hoy)

    def test_fecha_anterior_a_hoy_nace_entregado(self):
        for fecha in ['2026-10-14', '2026-01-01', '2020-06-30']:
            with self.subTest(fecha=fecha):
                self.assertEqual(self._estado(fecha), 'Entregado')

    def test_fecha_de_hoy_nace_pendiente(self):
        self.assertEqual(self._estado('2026-10-15'), 'Pendiente',
                         'una entrega programada para hoy todavia esta pendiente')

    def test_fecha_futura_nace_pendiente(self):
        for fecha in ['2026-10-16', '2027-01-01']:
            with self.subTest(fecha=fecha):
                self.assertEqual(self._estado(fecha), 'Pendiente')

    def test_fecha_vacia_o_invalida_nace_pendiente(self):
        for fecha in [None, '', '   ', 'no-es-fecha', '2026-13-45']:
            with self.subTest(fecha=fecha):
                self.assertEqual(self._estado(fecha), 'Pendiente')

    def test_el_estado_devuelto_siempre_es_canonico(self):
        for fecha in ['2026-10-14', '2026-10-15', '2026-10-16', '', None]:
            with self.subTest(fecha=fecha):
                self.assertIn(self._estado(fecha), fb.ESTADOS_ORDEN)

    def test_el_limite_es_exclusivo_en_el_dia_de_hoy(self):
        # ayer -> Entregado, hoy -> Pendiente, manana -> Pendiente
        self.assertEqual(self._estado('2026-10-14', hoy=HOY), 'Entregado')
        self.assertEqual(self._estado('2026-10-15', hoy=HOY), 'Pendiente')
        self.assertEqual(self._estado('2026-10-16', hoy=HOY), 'Pendiente')


class TestZonaHorariaDeLaTienda(unittest.TestCase):
    def test_el_hoy_por_defecto_usa_la_zona_de_la_tienda(self):
        self.assertTrue(hasattr(app_module, '_hoy_tienda'),
                        'falta app._hoy_tienda()')
        tz = os.getenv('APP_TIMEZONE', 'America/La_Paz')
        esperado = datetime.now(ZoneInfo(tz)).date()
        self.assertEqual(app_module._hoy_tienda(), esperado)

    def test_la_tienda_va_en_utc_menos_4(self):
        tz = os.getenv('APP_TIMEZONE', 'America/La_Paz')
        offset = datetime.now(ZoneInfo(tz)).utcoffset()
        self.assertEqual(offset.total_seconds(), -4 * 3600,
                         'la tienda es Bolivia (UTC-4); ajusta APP_TIMEZONE si no')


class TestCreacionPersisteElEstado(unittest.TestCase):
    """La ruta de creacion debe guardar el estado derivado, no 'Pendiente' fijo."""

    @classmethod
    def setUpClass(cls):
        cls.uid = next((d.id for d in fb.db.collection('usuarios').limit(1).stream()), None)
        cls.perfil = fa.obtener_usuario_por_uid(cls.uid) if cls.uid else None

    def setUp(self):
        self.guardadas = []
        self._real = fb.create_order
        fb.create_order = lambda data: (self.guardadas.append(data), 'ORD-TEST')[1]

    def tearDown(self):
        fb.create_order = self._real

    def _post(self, fecha_entrega):
        cl = app_module.app.test_client()
        with cl.session_transaction() as s:
            s['user_uid'] = self.uid
            s['user_role'] = (self.perfil or {}).get('rol', '')
        return cl.post('/ordenes/nueva', data={
            'id_sucursal': 'S1',
            'id_cliente': 'cli-test',
            'fecha_entrega': fecha_entrega,
        })

    def test_una_fecha_pasada_guarda_entregado(self):
        ayer = date.today().replace(day=1) if date.today().day > 1 else date(2020, 1, 1)
        r = self._post(ayer.isoformat())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(len(self.guardadas), 1)
        self.assertEqual(self.guardadas[0]['estado'], 'Entregado',
                         f"se guardo {self.guardadas[0].get('estado')!r}")

    def test_una_fecha_futura_guarda_pendiente(self):
        r = self._post('2099-12-31')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['estado'], 'Pendiente')


if __name__ == '__main__':
    unittest.main(verbosity=2)
