"""La vendedora de una orden se elige de un combo, con opcion de escribir una propia.

Pedido del usuario (verbatim): "en la parte de vendedora en /ordenes/nueva, quiero
que sea un combo, te lo paso: Mia / Dagmar / Camila / Noe Cano / Sissy / Cristian /
Abigail / Stefani Illin / Estefanny Rodriguez / Dennis / Vianca , ademas me das la
opcion de escribir uno propio".

RED primero: VENDEDORAS y _vendedora_del_formulario todavia no existen.

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
# un espacio final en un nombre crearia una vendedora distinta en los datos.
ESPERADAS = [
    'Mía',
    'Dagmar',
    'Camila',
    'Noe Cano',
    'Sissy',
    'Cristian',
    'Abigail',
    'Stefani Illin',
    'Estefanny Rodríguez',
    'Dennis',
    'Vianca',
]


class TestListaDeVendedoras(unittest.TestCase):
    def test_existe_la_lista_en_el_backend(self):
        self.assertTrue(hasattr(app_module, 'VENDEDORAS'), 'falta app.VENDEDORAS')

    def test_contiene_exactamente_los_nombres_pedidos_en_su_orden(self):
        self.assertEqual(list(app_module.VENDEDORAS), ESPERADAS)

    def test_los_nombres_no_llevan_espacios_sobrantes(self):
        for nombre in app_module.VENDEDORAS:
            self.assertEqual(nombre, nombre.strip(), f'{nombre!r} tiene espacios sobrantes')

    def test_no_hay_duplicados_ni_vacios(self):
        self.assertEqual(len(set(app_module.VENDEDORAS)), len(app_module.VENDEDORAS))
        self.assertNotIn('', app_module.VENDEDORAS)

    def test_el_centinela_de_otro_no_choca_con_un_nombre_real(self):
        self.assertTrue(hasattr(app_module, 'VENDEDORA_OTRO'), 'falta app.VENDEDORA_OTRO')
        self.assertNotIn(app_module.VENDEDORA_OTRO, app_module.VENDEDORAS)


class TestResolucionDeLaVendedora(unittest.TestCase):
    def _resolver(self, **form):
        self.assertTrue(hasattr(app_module, '_vendedora_del_formulario'),
                        'falta app._vendedora_del_formulario(form)')
        return app_module._vendedora_del_formulario(form)

    def test_elegir_un_nombre_devuelve_ese_nombre(self):
        for nombre in ESPERADAS:
            with self.subTest(nombre=nombre):
                self.assertEqual(self._resolver(vendedora=nombre), nombre)

    def test_elegir_otro_devuelve_lo_escrito(self):
        self.assertEqual(
            self._resolver(vendedora=app_module.VENDEDORA_OTRO, vendedora_otro='Juana Perez'),
            'Juana Perez')

    def test_elegir_otro_recorta_espacios(self):
        self.assertEqual(
            self._resolver(vendedora=app_module.VENDEDORA_OTRO, vendedora_otro='  Ana  '),
            'Ana')

    def test_elegir_otro_sin_texto_devuelve_vacio(self):
        self.assertEqual(self._resolver(vendedora=app_module.VENDEDORA_OTRO), '')
        self.assertEqual(self._resolver(vendedora=app_module.VENDEDORA_OTRO, vendedora_otro='   '), '')

    def test_sin_elegir_nada_devuelve_vacio(self):
        self.assertEqual(self._resolver(), '')
        self.assertEqual(self._resolver(vendedora=''), '')

    def test_el_texto_libre_se_ignora_si_no_se_eligio_otro(self):
        # evita que un valor viejo en el campo de texto pise la eleccion del combo
        self.assertEqual(self._resolver(vendedora='Mía', vendedora_otro='Basura'), 'Mía')


class TestComboRenderizado(unittest.TestCase):
    """Se comprueba el HTML ya renderizado: los nombres vienen de `VENDEDORAS`
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
        bloque = re.search(r'<select[^>]*id="vendedora".*?</select>', html, re.S)
        self.assertIsNotNone(bloque, 'no hay <select id="vendedora"> renderizado')
        return bloque.group(0)

    def test_hay_un_select_para_vendedora(self):
        self.assertTrue(self._bloque_combo(self._html()))

    def test_el_select_ofrece_las_once_vendedoras(self):
        bloque = self._bloque_combo(self._html())
        for nombre in ESPERADAS:
            with self.subTest(nombre=nombre):
                self.assertIn(f'value="{nombre}"', bloque, f'falta {nombre!r} en el combo')

    def test_el_select_no_ofrece_ningun_estado_ni_valor_inesperado(self):
        bloque = self._bloque_combo(self._html())
        valores = re.findall(r'<option value="([^"]*)"', bloque)
        esperados = ['', *ESPERADAS, app_module.VENDEDORA_OTRO]
        self.assertEqual(valores, esperados)

    def test_hay_un_campo_para_escribir_una_vendedora_propia(self):
        html = self._html()
        self.assertRegex(html, r'id="vendedoraOtro"',
                         'falta el campo de texto para la opcion "Otro"')

    def test_el_combo_conserva_el_nombre_de_campo_que_lee_el_backend(self):
        self.assertIn('name="vendedora"', self._bloque_combo(self._html()))

    def test_el_campo_libre_solo_se_muestra_al_elegir_otro(self):
        html = self._html()
        campo = re.search(r'<input[^>]*id="vendedoraOtro"[^>]*>', html, re.S)
        self.assertIsNotNone(campo, 'no se pudo aislar el campo libre')
        self.assertIn('display: none', campo.group(0),
                      'el campo libre debe arrancar oculto')


class TestCreacionGuardaLaVendedora(unittest.TestCase):
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

    def test_guardar_una_vendedora_del_combo(self):
        r = self._post(vendedora='Noe Cano')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['vendedora'], 'Noe Cano')

    def test_guardar_una_vendedora_escrita_a_mano(self):
        r = self._post(vendedora=app_module.VENDEDORA_OTRO, vendedora_otro='Juana Perez')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['vendedora'], 'Juana Perez')

    def test_sin_vendedora_guarda_vacio(self):
        r = self._post()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
        self.assertEqual(self.guardadas[0]['vendedora'], '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
