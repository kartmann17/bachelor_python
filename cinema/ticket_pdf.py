from io import BytesIO

import qrcode
from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


def ticket_pdf(ticket):
    data = BytesIO()
    pdf = Canvas(data, pagesize=(430, 305))
    pdf.setTitle("Billet Le Grand Cinéma")
    booking = ticket.reservation
    screening = booking.screening
    pdf.setFillColor(HexColor("#19241b"))
    pdf.rect(0, 246, 430, 59, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#e1ef9a"))
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawString(24, 269, "Le Grand Cinéma")
    pdf.setFillColor(HexColor("#1b251c"))
    pdf.setFont("Helvetica-Bold", 19)
    title = pdf.beginText(24, 216)
    title.setFont("Helvetica-Bold", 15)
    current_line = ""
    for word in screening.film.title.split():
        candidate = f"{current_line} {word}".strip()
        if current_line and pdf.stringWidth(candidate, "Helvetica-Bold", 15) > 256:
            title.textLine(current_line)
            current_line = word
        else:
            current_line = candidate
    title.textLine(current_line)
    pdf.drawText(title)

    starts = timezone.localtime(screening.starts_at)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(24, 162, f"{starts:%d/%m/%Y à %H:%M}")
    pdf.drawString(24, 142, str(screening.room))
    pdf.drawString(24, 122, f"Statut : {booking.effective_label}")
    pdf.drawString(24, 102, f"Tarif : {booking.unit_price:.2f} EUR")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(24, 59, "Référence du billet")
    pdf.setFont("Courier", 11)
    pdf.drawString(24, 42, str(ticket.reference))

    image = qrcode.make(str(ticket.reference)).get_image()
    pdf.drawImage(ImageReader(image), 295, 100, width=116, height=116, mask="auto")
    pdf.showPage()
    pdf.save()
    data.seek(0)
    return data
