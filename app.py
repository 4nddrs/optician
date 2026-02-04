from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
import firebase_config as fb
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'tu-clave-secreta-super-segura-cambiar-en-produccion')

# Main route - Dashboard
@app.route('/')
def index():
    try:
        ordenes = fb.get_all_orders()
        sucursales = fb.get_all_branches()
        clientes = fb.get_all_clients()
        
        # Create a dictionary for quick client lookup
        clientes_dict = {cliente['id']: cliente for cliente in clientes}
        
        # Statistics
        total_ordenes = len(ordenes)
        ordenes_pendientes = len([o for o in ordenes if o.get('estado') == 'pendiente'])
        ordenes_entregadas = len([o for o in ordenes if o.get('estado') == 'entregado'])
        
        return render_template('index.html', 
                             ordenes=ordenes[:10],  # Últimas 10 órdenes
                             sucursales=sucursales,
                             clientes_dict=clientes_dict,
                             total_ordenes=total_ordenes,
                             ordenes_pendientes=ordenes_pendientes,
                             ordenes_entregadas=ordenes_entregadas)
    except Exception as e:
        return render_template('error.html', error=str(e))

# Client routes
@app.route('/clientes')
def clientes():
    try:
        clientes = fb.get_all_clients()
        return render_template('clientes.html', clientes=clientes)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        try:
            data = {
                'ci': request.form.get('ci'),
                'nombre_completo': request.form.get('nombre_completo'),
                'telefono': request.form.get('telefono')
            }
            cliente_id = fb.create_client(data)
            return jsonify({'success': True, 'cliente_id': cliente_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    return render_template('nuevo_cliente.html')

@app.route('/clientes/<cliente_id>')
def ver_cliente(cliente_id):
    try:
        cliente = fb.get_client_by_id(cliente_id)
        if not cliente:
            return render_template('error.html', error='Cliente no encontrado')
        
        # Get client orders
        ordenes = fb.get_all_orders()
        ordenes_cliente = [o for o in ordenes if o.get('id_cliente') == cliente_id]
        
        return render_template('ver_cliente.html', cliente=cliente, ordenes=ordenes_cliente)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/api/clientes/buscar')
def buscar_cliente():
    ci = request.args.get('ci')
    if not ci:
        return jsonify({'success': False, 'error': 'CI requerido'}), 400
    
    try:
        cliente = fb.get_client_by_ci(ci)
        if cliente:
            return jsonify({'success': True, 'cliente': cliente})
        return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Order routes
@app.route('/ordenes')
def ordenes():
    try:
        ordenes = fb.get_all_orders()
        sucursales = fb.get_all_branches()
        clientes = fb.get_all_clients()
        
        # Create a dictionary for quick client lookup
        clientes_dict = {cliente['id']: cliente for cliente in clientes}
        
        return render_template('ordenes.html', ordenes=ordenes, sucursales=sucursales, clientes_dict=clientes_dict)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/ordenes/nueva', methods=['GET', 'POST'])
def nueva_orden():
    if request.method == 'POST':
        try:
            # Basic data
            data = {
                'id_sucursal': request.form.get('id_sucursal'),
                'id_cliente': request.form.get('id_cliente'),
                'fecha_creacion': datetime.utcnow().isoformat() + 'Z',
                'fecha_entrega': request.form.get('fecha_entrega'),
                'estado': 'pendiente',
                
                # Specifications
                'especificaciones': {
                    'material': request.form.get('material'),
                    'tratamientos': request.form.getlist('tratamientos'),
                    'tipo_lente': request.form.get('tipo_lente'),
                    'marca_lente': request.form.get('marca_lente')
                },
                
                # Graduation
                'graduacion': {
                    'lejos': {
                        'od': {
                            'esf': float(request.form.get('od_esf', 0)),
                            'cil': float(request.form.get('od_cil')) if request.form.get('od_cil') else None,
                            'eje': int(request.form.get('od_eje')) if request.form.get('od_eje') else None
                        },
                        'oi': {
                            'esf': float(request.form.get('oi_esf', 0)),
                            'cil': float(request.form.get('oi_cil')) if request.form.get('oi_cil') else None,
                            'eje': int(request.form.get('oi_eje')) if request.form.get('oi_eje') else None
                        },
                        'di': int(request.form.get('di', 0))
                    },
                    'cerca': {
                        'adicion': float(request.form.get('adicion')) if request.form.get('adicion') else None
                    }
                },
                
                # Frame
                'montura': {
                    'modelo': request.form.get('modelo_montura'),
                    'observaciones': request.form.get('observaciones_montura', '')
                },
                
                # Payments
                'pagos': {
                    'total': float(request.form.get('total', 0)),
                    'adelanto': float(request.form.get('adelanto', 0)),
                    'saldo': float(request.form.get('total', 0)) - float(request.form.get('adelanto', 0)),
                    'metodo_pago': request.form.get('metodo_pago')
                }
            }
            
            orden_id = fb.create_order(data)
            return jsonify({'success': True, 'orden_id': orden_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    # GET - Show form
    try:
        clientes = fb.get_all_clients()
        sucursales = fb.get_all_branches()
        return render_template('nueva_orden.html', clientes=clientes, sucursales=sucursales)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/ordenes/<orden_id>')
def ver_orden(orden_id):
    try:
        orden = fb.get_order_by_id(orden_id)
        if not orden:
            return render_template('error.html', error='Orden no encontrada')
        
        cliente = fb.get_client_by_id(orden.get('id_cliente'))
        sucursal = fb.get_branch_by_id(orden.get('id_sucursal'))
        
        return render_template('ver_orden.html', orden=orden, cliente=cliente, sucursal=sucursal)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/api/ordenes/<orden_id>/estado', methods=['PUT'])
def actualizar_estado(orden_id):
    try:
        new_status = request.json.get('estado')
        if not new_status:
            return jsonify({'success': False, 'error': 'Estado requerido'}), 400
        
        fb.update_order_status(orden_id, new_status)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ordenes/<orden_id>', methods=['DELETE'])
def eliminar_orden(orden_id):
    try:
        fb.delete_order(orden_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Branch routes
@app.route('/sucursales')
def sucursales():
    try:
        sucursales = fb.get_all_branches()
        return render_template('sucursales.html', sucursales=sucursales)
    except Exception as e:
        return render_template('error.html', error=str(e))

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Página no encontrada'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Error interno del servidor'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
