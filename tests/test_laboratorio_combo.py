"""El laboratorio de una orden se elige de un combo, con opcion de escribir uno propio.

Pedido del usuario (verbatim): "quiero lo mismo para laboratorios, cuando creo una
nueva orden un combo con estas opciones:Innovar / Digilab / Visión tech / Easy lab /
Premier / Rosales / Global / Cat / Lioc / Dislab / Seúl / Cerisier, tambien dale la
opcion de escribir".

RED primero: LABORATORIOS y _laboratorio_del_formulario todavia no existen.

Solo stdlib. Ninguna prueba escribe en Firestore: `create_order` va con stub.
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

# La lista exacta que paso el usuario, en su orden. Sin espacios sobrantes:
# un espacio final en un nombre crearia un laboratorio distinto en los datos.
ESPERADOS = [
    'Innovar',
    'Digilab',
    'Visión tech',
    'Easy lab',
    'Premier',
    'Rosales',
    'Global',
    'Cat',
    'Lioc',
    'Dislab',
    'Seúl',
    'Cerisier',
]


class TestListaDeLaboratorios(unittest.TestCase):
    def test_existe_la_lista_en_el_backend(self):
        self.assertTrue(hasattr(app_module, 'LABORATORIOS'), 'falta app.LABORATORIOS')

    def test_contiene_exactamente_los_nombres_pedidos_en_su_orden(self):
        self.assertEqual(list(app_module.LABORATORIOS), ESPERADOS)

    def test_los_nombres_no_llevan_espacios_sobrantes(self):
        for nombre in app_module.LABORATORIOS:
            self.assertEqual(nombre, nombre.strip(), f'{nombre!r} tiene espacios sobrantes')

    def test_no_hay_duplicados_ni_vacios(self):
        self.assertEqual(len(set(app_module.LABORATORIOS)), len(app_module.LABORATORIOS))
        self.assertNotIn('', app_module.LABORATORIOS)

    def test_el_centinela_de_otro_no_choca_con_un_nombre_real(self):
        self.assertTrue(hasattr(app_module, 'LABORATORIO_OTRO'), 'falta app.LABORATORIO_OTRO')
        self.assertNotIn(app_module.LABORATORIO_OTRO, app_module.LABORATORIOS)

    def test_el_centinela_es_el_mismo_que_usa_vendedora(self):
        # Un solo centinela en la app: dos valores distintos para el mismo
        # significado invitarian a que uno de los dos se guardara por error.
        self.assertEqual(app_module.LABORATORIO_OTRO, app_module.VENDEDORA_OTRO)


class TestResolucionDelLaboratorio(unittest.TestCase):
    def _resolver(self, **form):
        self.assertTrue(hasattr(app_module, '_laboratorio_del_formulario'),
                        'falta app._laboratorio_del_formulario(form)')
        return app_module._laboratorio_del_formulario(form)

    def test_elegir_un_nombre_devuelve_ese_nombre(self):
        for nombre in ESPERADOS:
            with self.subTest(nombre=nombre):
                self.assertEqual(self._resolver(laboratorio=nombre), nombre)

    def test_elegir_otro_devuelve_lo_escrito(self):
        self.assertEqual(
            self._resolver(laboratorio=app_module.LABORATORIO_OTRO,
                           laboratorio_otro='Laboratorio Central'),
            'Laboratorio Central')

    def test_elegir_otro_recorta_espacios(self):
        self.assertEqual(
            self._resolver(laboratorio=app_module.LABORATORIO_OTRO, laboratorio_otro='  Central  '),
            'Central')

    def test_elegir_otro_sin_texto_devuelve_vacio(self):
        self.assertEqual(self._resolver(laboratorio=app_module.LABORATORIO_OTRO), '')
        self.assertEqual(
            self._resolver(laboratorio=app_module.LABORATORIO_OTRO, laboratorio_otro='   '), '')

    def test_sin_elegir_nada_devuelve_vacio(self):
        self.assertEqual(self._resolver(), '')
        self.assertEqual(self._resolver(laboratorio=''), '')

    def test_el_texto_libre_se_ignora_si_no_se_eligio_otro(self):
        # evita que un valor viejo en el campo de texto pise la eleccion del combo
        self.assertEqual(self._resolver(laboratorio='Digilab', laboratorio_otro='Basura'), 'Digilab')

    def test_el_centinela_nunca_se_guarda_tal_cual(self):
        self.assertNotEqual(self._resolver(laboratorio=app_module.LABORATORIO_OTRO), 
                            app_module.LABORATORIO_OTRO)


class TestComboRenderizado(unittest.TestCase):
    """Se comprueba el HTML ya renderizado: los nombres vienen de `LABORATORIOS`
    por un bucle, asi que en el fuente de la plantilla no aparecen literales."""

    @classmethod
    def setUpClass(cls):
        cls.uid = next((d.id for d in fb.db.collection('usuarios').limit(1).stream()), None)
        cls.perfil = fa.obtener_usuario_por_uid(cls.uid) if cls.uid else None

    def _html(self):
        cl = app_module.app.test_client()
        with cl.session_transaction() as s:
            s['user_uid'] = self.uid
            s['user_role'] = (self.perfil or {}).get('rol', '')
        r = cl.get('/ordenes/nueva')
        self.assertEqual(r.status_code, 200, f'/ordenes/nueva respondio {r.status_code}')
        return r.get_data(as_text=True)

    def _bloque_combo(self, html):
        bloque = re.search(r'<select[^>]*id="laboratorio".*?</select>', html, re.S)
        self.assertIsNotNone(bloque, 'no hay <select id="laboratorio"> renderizado')
        return bloque.group(0)

    def test_hay_un_select_para_laboratorio(self):
        self.assertTrue(self._bloque_combo(self._html()))

    def test_el_select_ofrece_los_doce_laboratorios(self):
        bloque = self._bloque_combo(self._html())
        for nombre in ESPERADOS:
            with self.subTest(nombre=nombre):
                self.assertIn(f'value="{nombre}"', bloque, f'falta {nombre!r} en el combo')

    def test_el_select_no_ofrece_ningun_valor_inesperado(self):
        bloque = self._bloque_combo(self._html())
        valores = re.findall(r'<option value="([^"]*)"', bloque)
        esperados = ['', *ESPERADOS, app_module.LABORATORIO_OTRO]
        self.assertEqual(valores, esperados)

    def test_hay_un_campo_para_escribir_un_laboratorio_propio(self):
        html = self._html()
        self.assertRegex(html, r'id="laboratorioOtro"',
                         'falta el campo de texto para la opcion "Otro"')

    def test_el_combo_conserva_el_nombre_de_campo_que_lee_el_backend(self):
        self.assertIn('name="laboratorio"', self._bloque_combo(self._html()))

    def test_el_campo_libre_solo_se_muestra_al_elegir_otro(self):
        html = self._html()
        campo = re.search(r'<input[^>]*id="laboratorioOtro"[^>]*>', html, re.S)
        self.assertIsNotNone(campo, 'no se pudo aislar el campo libre')
        self.assertIn('display: none', campo.group(0),
                      'el campo libre debe arrancar oculto')

    def test_ya_no_hay_un_input_de_texto_suelto_para_laboratorio(self):
        # La regresion original: el laboratorio era un texto libre sin lista.
        self.assertNotRegex(self._html(), r'<input[^>]*id="laboratorio"',
                            'quedo un <input id="laboratorio"> ademas del combo')


class TestCreacionGuardaElLaboratorio(unittest.TestCase):
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

    def _post(self, **campos):
        cl = app_module.app.test_client()
        with cl.session_transaction() as s:
            s['user_uid'] = self.uid
            s['user_role'] = (self.perfil or {}).get('rol', '')
        data = {'id_sucursal': 'S1', 'id_cliente': 'cli-test', 'fecha_entrega': '2099-12-31'}
        data.update(campos)
        return cl.post('/ordenes/nueva', data=data)

    def test_guardar_un_laboratorio_del_combo(self):
        r = self._post(laboratorio='Premier')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['laboratorio'], 'Premier')

    def test_guardar_un_laboratorio_escrito_a_mano(self):
        r = self._post(laboratorio=app_module.LABORATORIO_OTRO,
                       laboratorio_otro='Laboratorio Central')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['laboratorio'], 'Laboratorio Central')

    def test_sin_laboratorio_guarda_vacio(self):
        r = self._post()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['laboratorio'], '')

    def test_el_centinela_de_otro_nunca_llega_a_firestore(self):
        r = self._post(laboratorio=app_module.LABORATORIO_OTRO)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['laboratorio'], '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
