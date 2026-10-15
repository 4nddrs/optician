"""Verificacion independiente del combo de Laboratorio (creacion de orden).

Complementa tests/test_laboratorio_combo.py con contratos que ese archivo no fija:
el nombre del campo libre, que editar_orden siga siendo texto libre, que el JS
cablee los dos combos, y que vendedora y laboratorio compartan semantica.

Solo stdlib. Ninguna prueba escribe en Firestore: `create_order` y `update_order`
van con stub. Correr:
  venv/bin/python -m unittest tests.test_laboratorio_combo_verificacion -v
"""
import os
import re
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


def _nueva_orden_html():
    r = _cliente().get('/ordenes/nueva')
    assert r.status_code == 200, f'/ordenes/nueva respondio {r.status_code}'
    return r.get_data(as_text=True)


def _primera_orden_id():
    return next((d.id for d in fb.db.collection('ordenes_trabajo').limit(1).stream()), None)


class TestContratoDeCampos(unittest.TestCase):
    def test_el_campo_libre_usa_la_clave_que_lee_el_backend(self):
        # Si el name no coincide, elegir "Otro" guardaria vacio en silencio.
        campo = re.search(r'<input[^>]*id="laboratorioOtro"[^>]*>', _nueva_orden_html(), re.S)
        self.assertIsNotNone(campo, 'no se pudo aislar el campo libre del laboratorio')
        self.assertIn('name="laboratorio_otro"', campo.group(0))

    def test_el_select_de_laboratorio_no_duplica_opciones_ni_lleva_espacios(self):
        bloque = re.search(r'<select[^>]*id="laboratorio".*?</select>', _nueva_orden_html(), re.S).group(0)
        valores = re.findall(r'<option value="([^"]*)"', bloque)
        self.assertEqual(len(valores), len(set(valores)), f'opciones duplicadas: {valores}')
        for v in valores:
            self.assertEqual(v, v.strip(), f'opcion con espacios sobrantes: {v!r}')

    def test_la_plantilla_invalida_la_cache_del_js_de_creacion(self):
        html = _nueva_orden_html()
        self.assertIn('nueva_orden.js?v=8', html)
        self.assertNotIn('nueva_orden.js?v=7', html)


class TestJSDeLosDosCombos(unittest.TestCase):
    def _js(self):
        with open(os.path.join(RAIZ, 'static', 'js', 'nueva_orden.js'), encoding='utf-8') as fh:
            return fh.read()

    def test_el_js_cablea_vendedora_y_laboratorio(self):
        js = self._js()
        self.assertRegex(js, r"sincronizarComboOtro\(\s*'vendedora'\s*,\s*'vendedoraOtro'\s*\)")
        self.assertRegex(js, r"sincronizarComboOtro\(\s*'laboratorio'\s*,\s*'laboratorioOtro'\s*\)")

    def test_no_queda_el_cableado_vendedora_solo(self):
        self.assertNotIn('sincronizarVendedora', self._js())


class TestEditarSigueSiendoTextoLibre(unittest.TestCase):
    def test_editar_orden_sirve_inputs_de_texto_y_no_carga_el_js_de_creacion(self):
        oid = _primera_orden_id()
        if not oid:
            self.skipTest('no hay ordenes para abrir el editor')
        h = _cliente().get(f'/ordenes/{oid}/editar')
        self.assertEqual(h.status_code, 200)
        pagina = h.get_data(as_text=True)
        self.assertRegex(pagina, r'<input[^>]*id="vendedora"')
        self.assertRegex(pagina, r'<input[^>]*id="laboratorio"[^>]*placeholder="Nombre del laboratorio"')
        self.assertNotIn('nueva_orden.js', pagina, 'el editor no debe cargar el JS de creacion')

    def test_editar_orden_guarda_el_texto_libre_tal_cual(self):
        oid = _primera_orden_id()
        if not oid:
            self.skipTest('no hay ordenes para editar')
        guardadas = []
        real = fb.update_order
        fb.update_order = lambda o, d: (guardadas.append(d), True)[1]
        try:
            r = _cliente().post(f'/ordenes/{oid}/editar', data={
                'id_sucursal': 'S1', 'fecha_entrega': '2099-12-31',
                'vendedora': 'Quien Sea', 'laboratorio': 'Laboratorio Libre',
                'od_esf': '0', 'total': '0', 'adelanto': '0'})
        finally:
            fb.update_order = real
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        self.assertEqual(guardadas[0]['vendedora'], 'Quien Sea')
        self.assertEqual(guardadas[0]['laboratorio'], 'Laboratorio Libre')


class TestSemanticaCompartida(unittest.TestCase):
    def test_los_dos_resolutores_usan_el_mismo_centinela(self):
        self.assertEqual(app_module._vendedora_del_formulario(
            {'vendedora': app_module.VENDEDORA_OTRO, 'vendedora_otro': 'Libre'}), 'Libre')
        self.assertEqual(app_module._laboratorio_del_formulario(
            {'laboratorio': app_module.LABORATORIO_OTRO, 'laboratorio_otro': 'Libre'}), 'Libre')

    def test_un_valor_desconocido_sigue_guardandose_tal_cual(self):
        # No hay whitelist: un cliente viejo que postee texto libre sigue funcionando.
        self.assertEqual(
            app_module._laboratorio_del_formulario({'laboratorio': 'Laboratorio Externo'}),
            'Laboratorio Externo')

    def test_el_centinela_no_sobrevive_al_resolutor_de_laboratorio(self):
        self.assertEqual(app_module._laboratorio_del_formulario(
            {'laboratorio': app_module.LABORATORIO_OTRO, 'laboratorio_otro': '   '}), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
