"""Reports (Section 9 Phase 4 / Section 7): a summary view plus Excel/PDF export. Reachable by
any logged-in user (not admin-only) - the proposal doesn't scope reports to admins, unlike
Settings/tracking-source management (Section 3.9) or notification configuration."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ReportSummaryOut
from app.services.report_service import build_excel_report, build_pdf_report, build_report_summary

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary", response_model=ReportSummaryOut)
def get_report_summary(db: Session = Depends(get_db)):
    """The data behind the Reports page's on-screen view and both export formats below - kept
    as its own endpoint so the frontend can render the summary without downloading a file."""
    return build_report_summary(db)


@router.get("/export.xlsx")
def export_report_excel(db: Session = Depends(get_db)):
    """Same data as /summary, rendered as a downloadable .xlsx. The frontend downloads this as a
    Blob (see frontend/lib/api.ts's downloadReport) rather than a plain `<a href>` navigation, so
    the session cookie is sent correctly and an error response doesn't render as a broken file."""
    summary = build_report_summary(db)
    content = build_excel_report(summary)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="vessel-report.xlsx"'},
    )


@router.get("/export.pdf")
def export_report_pdf(db: Session = Depends(get_db)):
    """Same data as /summary, rendered as a downloadable PDF."""
    summary = build_report_summary(db)
    content = build_pdf_report(summary)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="vessel-report.pdf"'},
    )
