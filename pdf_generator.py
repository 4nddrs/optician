"""
Módulo para generación de PDFs de órdenes usando xhtml2pdf
"""
from io import BytesIO
from flask import render_template
from xhtml2pdf import pisa
import logging

logger = logging.getLogger(__name__)


def generar_pdf_orden(orden, cliente, sucursal):
    """
    Genera un PDF de una orden de trabajo.
    
    Args:
        orden (dict): Documento de orden desde Firestore
        cliente (dict): Documento de cliente desde Firestore
        sucursal (dict): Documento de sucursal desde Firestore
    
    Returns:
        BytesIO: Buffer con el PDF generado
        str: Nombre sugerido para el archivo
    """
    try:
        # Renderizar la plantilla HTML con los datos
        html_string = render_template(
            'orden_pdf.html',
            orden=orden,
            cliente=cliente,
            sucursal=sucursal
        )
        
        # Crear buffer para el PDF
        pdf_buffer = BytesIO()
        
        # Convertir HTML a PDF
        status = pisa.CreatePDF(
            src=html_string.encode('utf-8'),
            dest=pdf_buffer,
            encoding='utf-8'
        )
        
        # Verificar si la conversión fue exitosa
        if status.err:
            logger.error(f"Error en generación de PDF: {status.err}")
            raise Exception(f"Error al generar PDF: {status.err}")
        
        # Resetear el puntero del buffer al inicio
        pdf_buffer.seek(0)
        
        # Nombre del archivo
        id_orden = orden.get('id_orden', 'orden')
        filename = f"orden_{id_orden}.pdf"
        
        return pdf_buffer, filename
        
    except Exception as e:
        logger.error(f"Exception generando PDF: {str(e)}")
        raise


def enviar_pdf_respuesta(app, pdf_buffer, filename):
    """
    Prepara la respuesta HTTP para descargar el PDF.
    
    Args:
        app: Instancia de Flask app
        pdf_buffer (BytesIO): Buffer con el contenido del PDF
        filename (str): Nombre del archivo
    
    Returns:
        Response: Respuesta HTTP con el PDF
    """
    from flask import make_response
    
    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response
