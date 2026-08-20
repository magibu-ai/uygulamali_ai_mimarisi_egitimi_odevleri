from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.domain import PlanBlock, PlanDraft
from services.pdf_service import PDFService


TZ = ZoneInfo("Europe/Istanbul")


def test_pdf_is_generated_from_plan(tmp_path, monkeypatch):
    """Plan ciktisinin gecerli ve bos olmayan bir PDF dosyasi oldugunu dogrular."""

    monkeypatch.setattr("services.pdf_service.tempfile.gettempdir", lambda: str(tmp_path))
    start = datetime(2026, 8, 3, 9, 0, tzinfo=TZ)
    draft = PlanDraft(
        week_start=datetime(2026, 8, 3, tzinfo=TZ),
        blocks=[
            PlanBlock(
                task_id=1,
                title="Proje sunumu",
                start=start,
                end=start + timedelta(minutes=120),
            )
        ],
        unscheduled=[],
    )

    output = Path(PDFService().generate(draft, [], "session-a", confirmed=True))

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
