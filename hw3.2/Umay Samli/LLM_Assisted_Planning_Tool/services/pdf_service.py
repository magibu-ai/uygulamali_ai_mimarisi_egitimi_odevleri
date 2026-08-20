"""Haftalik plan taslaklarini indirilebilir PDF dosyasina donusturur."""

from __future__ import annotations

import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.domain import PlanDraft, Task


DAY_NAMES = {
    0: "Pazartesi",
    1: "Sali",
    2: "Carsamba",
    3: "Persembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}


class PDFService:
    def __init__(self) -> None:
        """PDF ciktisinda kullanilacak uygun fontlari kaydeder."""

        self.regular_font, self.bold_font = self._register_fonts()

    def generate(
        self,
        draft: PlanDraft,
        tasks: list[Task],
        session_id: str,
        confirmed: bool = False,
    ) -> str:
        """Plan taslagini oturuma ozel indirilebilir bir PDF dosyasina yazar."""

        safe_session = "".join(
            character
            for character in session_id
            if character.isalnum() or character in {"-", "_"}
        ) or "session"
        output_directory = (
            Path(tempfile.gettempdir()) / "weekly-planner-pdfs" / safe_session
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / "haftalik-plan.pdf"

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title="Haftalik Plan",
            author="LLM Destekli Haftalik Planlayici",
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PlannerTitle",
            parent=styles["Title"],
            fontName=self.bold_font,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1e3a8a"),
        )
        body_style = ParagraphStyle(
            "PlannerBody",
            parent=styles["BodyText"],
            fontName=self.regular_font,
            fontSize=9,
            leading=12,
        )
        heading_style = ParagraphStyle(
            "PlannerHeading",
            parent=styles["Heading2"],
            fontName=self.bold_font,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1e40af"),
        )

        status = "Onaylanmis" if confirmed else "Taslak"
        story = [
            Paragraph(f"{status} Haftalik Plan", title_style),
            Spacer(1, 4 * mm),
            Paragraph(
                f"Hafta baslangici: {draft.week_start.strftime('%d.%m.%Y')}",
                body_style,
            ),
            Spacer(1, 5 * mm),
        ]

        table_data = [["Gun", "Saat", "Gorev", "Sure"]]
        for block in sorted(draft.blocks, key=lambda item: item.start):
            duration = int((block.end - block.start).total_seconds() // 60)
            table_data.append(
                [
                    DAY_NAMES[block.start.weekday()],
                    f"{block.start.strftime('%H:%M')} - {block.end.strftime('%H:%M')}",
                    Paragraph(escape(block.title), body_style),
                    f"{duration} dk",
                ]
            )
        if len(table_data) == 1:
            table_data.append(["-", "-", "Planlanmis gorev yok", "-"])

        plan_table = Table(
            table_data,
            colWidths=[31 * mm, 38 * mm, 91 * mm, 22 * mm],
            repeatRows=1,
        )
        plan_table.setStyle(self._table_style())
        story.append(plan_table)

        if draft.unscheduled:
            task_map = {task.id: task for task in tasks}
            story.extend(
                [
                    Spacer(1, 7 * mm),
                    Paragraph("Planlanamayan Gorevler", heading_style),
                    Spacer(1, 2 * mm),
                ]
            )
            unscheduled_data = [["Gorev", "Neden"]]
            for item in draft.unscheduled:
                task = task_map.get(item.task_id)
                title = task.title if task else f"Gorev {item.task_id}"
                unscheduled_data.append(
                    [
                        Paragraph(escape(title), body_style),
                        Paragraph(escape(item.reason), body_style),
                    ]
                )
            unscheduled_table = Table(
                unscheduled_data,
                colWidths=[75 * mm, 107 * mm],
                repeatRows=1,
            )
            unscheduled_table.setStyle(self._table_style())
            story.append(unscheduled_table)

        document.build(story)
        return str(output_path)

    def _table_style(self) -> TableStyle:
        """Plan ve planlanamayan gorev tablolari icin ortak stili olusturur."""

        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), self.bold_font),
                ("FONTNAME", (0, 1), (-1, -1), self.regular_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (1, -1), "CENTER"),
                ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#eff6ff"),
                ]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )

    @staticmethod
    def _register_fonts() -> tuple[str, str]:
        """Turkce karakter destekli fontlari bulur veya yerlesik fontlara geri doner."""

        regular_path = Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        bold_path = Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        )
        if regular_path.exists() and bold_path.exists():
            if "PlannerSans" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("PlannerSans", regular_path))
            if "PlannerSans-Bold" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("PlannerSans-Bold", bold_path))
            return "PlannerSans", "PlannerSans-Bold"
        return "Helvetica", "Helvetica-Bold"
