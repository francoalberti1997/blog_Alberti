# reports/utils/pdf/styles.py
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    name='Title', fontName='Helvetica-Bold', fontSize=28,
    textColor=colors.darkblue, spaceAfter=32,
    alignment=TA_CENTER, leading=34
)

h1 = ParagraphStyle(
    name='H1', fontName='Helvetica-Bold', fontSize=16,
    textColor=colors.darkslategray, spaceBefore=22,
    spaceAfter=10, alignment=TA_LEFT, leading=20
)

normal = ParagraphStyle(
    name='Normal', fontName='Helvetica', fontSize=12,
    leading=16, spaceAfter=10
)

normal_bold = ParagraphStyle(
    'NormalBold',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=10,
    leading=12,
    textColor=HexColor('#2C3E50'),
)

h2 = ParagraphStyle(
    'Heading2',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=14,                        # Más grande que el normal
    leading=18,
    textColor=HexColor('#2C3E50'),      # Color oscuro profesional (gris azulado)
    spaceBefore=18,
    spaceAfter=10,
    alignment=TA_LEFT,
)