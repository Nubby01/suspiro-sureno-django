"""Cotización comercial A4. Solo usa datos guardados y contactos configurados."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, LongTable, TableStyle, Image, KeepTogether

from apps.core.negocio import CORREO, FACEBOOK, INSTAGRAM, NOMBRE, WHATSAPP_VISIBLE

TINTA = colors.HexColor("#352821")
MARCA = colors.HexColor("#994215")
CREMA = colors.HexColor("#f7f1e8")
BORDE = colors.HexColor("#e3d6c5")


def _texto(valor):
    # No markup from names, descriptions or notes enters the document.
    return escape(str(valor or "")).replace("\n", "<br/>")


def construir_cotizacion(cotizacion):
    salida = BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=A4, rightMargin=42, leftMargin=42,
                                 topMargin=133, bottomMargin=62,
                                 title=f"Cotización {cotizacion.codigo}", author=NOMBRE,
                                 pageCompression=0)
    estilos = {
        "texto": ParagraphStyle("texto", fontName="Helvetica", fontSize=10, leading=15, textColor=TINTA, spaceAfter=6, wordWrap="CJK"),
        "pequeno": ParagraphStyle("pequeno", fontName="Helvetica", fontSize=8.5, leading=12, textColor=TINTA, wordWrap="CJK"),
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=10, leading=15, textColor=MARCA, spaceBefore=10, spaceAfter=8),
        "importe": ParagraphStyle("importe", fontName="Helvetica", fontSize=9, leading=13, textColor=TINTA, alignment=TA_RIGHT, wordWrap="CJK"),
        "total": ParagraphStyle("total", fontName="Helvetica-Bold", fontSize=17, leading=23, textColor=MARCA, alignment=TA_RIGHT),
    }
    def par(texto, estilo="texto"):
        return Paragraph(_texto(texto), estilos[estilo])

    def cabecera_pie(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(CREMA)
        canvas.rect(0, A4[1]-108, A4[0], 108, fill=1, stroke=0)
        logo = Path(settings.BASE_DIR)/"static"/"imagenes"/"logo.png"
        if logo.is_file():
            canvas.drawImage(str(logo), 42, A4[1]-88, width=62, height=62, preserveAspectRatio=True, mask="auto")
        canvas.setFillColor(TINTA)
        canvas.setFont("Times-Roman", 22)
        canvas.drawString(116, A4[1]-44, NOMBRE)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(116, A4[1]-62, "Repostería artesanal")
        canvas.setFont("Helvetica-Bold", 11)
        canvas.setFillColor(MARCA)
        canvas.drawRightString(A4[0]-42, A4[1]-40, "COTIZACIÓN")
        canvas.setFont("Helvetica", 10)
        canvas.drawRightString(A4[0]-42, A4[1]-58, cotizacion.codigo)
        canvas.setStrokeColor(BORDE)
        canvas.line(42, 48, A4[0]-42, 48)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(TINTA)
        canvas.drawString(42, 32, f"{NOMBRE} | {cotizacion.codigo}")
        canvas.drawRightString(A4[0]-42, 32, f"Página {doc.page}")
        canvas.restoreState()

    fecha = timezone.localtime(cotizacion.creada).strftime("%d-%m-%Y %H:%M")
    meta = Table([[par("PREPARADA PARA", "titulo"), par("DATOS DE LA COTIZACIÓN", "titulo")],
                  [par(cotizacion.nombre), par(f"Fecha: {fecha}")],
                  [par(cotizacion.correo, "pequeno"), par(f"Estado: {cotizacion.get_estado_display()}", "pequeno")],
                  [par(cotizacion.telefono, "pequeno"), par("Montos en pesos chilenos (CLP)", "pequeno")]], colWidths=[276,235])
    meta.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    cuerpo = [meta, Spacer(1, 18), par("DETALLE DE PRODUCTOS", "titulo")]
    filas = [[par("Producto / presentación", "pequeno"),par("Cant.", "importe"),par("P. unitario", "importe"),par("Subtotal", "importe")]]
    for linea in cotizacion.lineas.all():
        descripcion = linea.nombre_producto
        if linea.nombre_variante:
            descripcion += "\n" + linea.nombre_variante
        if linea.detalle:
            descripcion += "\n" + linea.detalle
        filas.append([par(descripcion),par(str(linea.cantidad),"importe"),par(linea.precio_texto(),"importe"),par(linea.importe_texto(),"importe")])
    if len(filas) == 1:
        filas.append([par("Sin productos registrados."), "", "", ""])
    tabla = LongTable(filas,colWidths=[275,40,98,98],repeatRows=1,splitInRow=1,hAlign="LEFT")
    tabla.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),CREMA), ("VALIGN",(0,0),(-1,-1),"TOP"),
                              ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
                              ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                              ("LINEBELOW",(0,0),(-1,0),1,BORDE),("LINEBELOW",(0,1),(-1,-1),.4,BORDE)]))
    cuerpo.extend([tabla, Spacer(1,18)])
    total = Table([[par("TOTAL", "titulo"),par(cotizacion.total_texto(),"total")]],colWidths=[220,291])
    total.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),CREMA),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12),("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14)]))
    resumen = [total]
    if cotizacion.total() is None:
        resumen.extend([Spacer(1,8),par("Hay precios pendientes de confirmar. El total se mostrará cuando todos los productos tengan precio acordado.","pequeno")])
    cuerpo.append(KeepTogether(resumen))
    for titulo,valor in [("OBSERVACIONES",cotizacion.observaciones),("MOTIVO",cotizacion.motivo)]:
        if valor:
            cuerpo.extend([par(titulo,"titulo"),par(valor)])
    contactos = [f"WhatsApp: {WHATSAPP_VISIBLE}" if WHATSAPP_VISIBLE else "",
                 f"Correo: {CORREO}" if CORREO else "",
                 f"Instagram: {INSTAGRAM}" if INSTAGRAM else "",
                 f"Facebook: {FACEBOOK}" if FACEBOOK else ""]
    if any(contactos):
        cuerpo.extend([Spacer(1,12),par("CONTACTO","titulo"),par("\n".join(x for x in contactos if x),"pequeno")])
    documento.build(cuerpo,onFirstPage=cabecera_pie,onLaterPages=cabecera_pie)
    return salida.getvalue()
