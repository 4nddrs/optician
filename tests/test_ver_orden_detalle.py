"""La vista de detalle de la venta no muestra el campo "Atendido por".

Pedido del usuario (verbatim): "creo que al ver los detalles de la venta la parte de
Atendido por / Sucursal 1 sobra, ya que ya tenemos vendedora, quitalo y tambien del
pdf que generamos".

Aclarado con una captura de pantalla: "solo el campo 'Atendido por', Sucursal se
queda". El valor que aparecia bajo "Atendido por" era literalmente "Sucursal 1",
porque `nombre_empleado` guardaba ese texto; la sucursal real ("Casa Matriz") se
muestra en su propio campo `Sucursal`, que se conserva.

RED primero: la linea "Atendido por" todavia esta en ver_orden.html.

Solo stdlib. Firestore se lee unicamente para elegir una orden que abrir; no se
escribe nada.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_config as fb
import firebase_auth as fa
import app as app_module

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cliente():
    uid = next((d.id for d in fb.db.collection('usuarios').limit(1).stream()), None)
    perfil = fa.obtener_usuario_por_uid(uid) if uid else None
    cl = app_module.app.test_client()
    with cl.session_transaction() as s:
        s['user_uid'] = uid
        s['user_role'] = (perfil or {}).get('rol', '')
    return cl


def _una_orden_id():
    return next((d.id for d in fb.db.collection('ordenes_trabajo').limit(1).stream()), None)


def _fuente_plantilla(nombre):
    with open(os.path.join(RAIZ, 'templates', nombre), encoding='utf-8') as fh:
        return fh.read()


class TestVerOrdenSinAtendidoPor(unittest.TestCase):
    def _html(self):
        oid = _una_orden_id()
        if not oid:
            self.skipTest('no hay ordenes para abrir el detalle')
        r = _cliente().get(f'/ordenes/{oid}')
        self.assertEqual(r.status_code, 200, f'/ordenes/{oid} respondio {r.status_code}')
        return r.get_data(as_text=True)

    def test_no_muestra_el_campo_atendido_por(self):
        self.assertNotIn('Atendido por', self._html(),
                         'la vista de detalle todavia muestra "Atendido por"')

    def test_la_plantilla_ya_no_referencia_nombre_empleado(self):
        # La linea se quita completa, no solo su etiqueta.
        self.assertNotIn('nombre_empleado', _fuente_plantilla('ver_orden.html'))

    def test_sigue_mostrando_el_campo_sucursal(self):
        # El usuario fue explicito: "Sucursal se queda".
        self.assertIn('Sucursal</dt>', self._html(),
                      'se perdio el campo Sucursal, que debia conservarse')

    def test_la_plantilla_conserva_los_campos_vendedora_y_sucursal(self):
        # Motivo del cambio ("ya tenemos vendedora") y limite explicito del
        # usuario ("Sucursal se queda"): los dos campos siguen en la plantilla.
        # Se mira el fuente para no depender de que la orden elegida los tenga.
        fuente = _fuente_plantilla('ver_orden.html')
        self.assertIn('Vendedora</dt>', fuente)
        self.assertIn('Sucursal</dt>', fuente)


class TestLaNotaDeVentaNoTieneEseCampo(unittest.TestCase):
    """La nota de venta impresa nunca mostro "Atendido por": su plantilla solo
    pinta sucursal, correlativo, orden, fechas, vendedora y laboratorio. Se fija
    aqui para que el pedido quede cubierto y nadie lo reintroduzca."""

    def test_orden_pdf_no_renderiza_el_campo_atendido_por(self):
        self.assertNotIn('Atendido por', _fuente_plantilla('orden_pdf.html'))

    def test_orden_pdf_no_renderiza_nombre_empleado(self):
        self.assertNotIn('nombre_empleado', _fuente_plantilla('orden_pdf.html'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
