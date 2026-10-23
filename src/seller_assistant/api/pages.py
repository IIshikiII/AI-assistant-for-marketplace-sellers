"""HTML-страницы и HTMX-фрагменты."""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from seller_assistant.db import get_session
from seller_assistant.models import Product, Recommendation
from seller_assistant.services import ai, analytics, shop
from seller_assistant.web.templating import templates

log = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)


def _render(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


def _ai_error(request: Request, exc: Exception) -> HTMLResponse:
    log.exception("Ошибка LLM")
    return _render(request, "partials/ai_error.html", error=str(exc))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    kpis, _ = shop.overview(session)
    recs = shop.list_recommendations(session)
    by_area: dict[str, float] = {}
    for r in recs:
        by_area[r.area] = by_area.get(r.area, 0) + r.effect_rub
    return _render(
        request,
        "dashboard.html",
        active="dashboard",
        kpis=kpis,
        top=recs[:5],
        total_effect=sum(r.effect_rub for r in recs),
        open_count=len(recs),
        critical=sum(1 for r in recs if r.severity == 3),
        by_area=by_area,
    )


@router.get("/recommendations", response_class=HTMLResponse)
def recommendations(
    request: Request,
    area: str | None = None,
    status: str = "new",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    recs = shop.list_recommendations(session, status=status, area=area)
    return _render(
        request,
        "recommendations.html",
        active="recs",
        recs=recs,
        area=area,
        status=status,
        total_effect=sum(r.effect_rub for r in recs),
    )


@router.post("/recommendations/refresh")
def refresh(session: Session = Depends(get_session)) -> RedirectResponse:
    shop.refresh_recommendations(session)
    return RedirectResponse("/recommendations", status_code=303)


def _get_rec(session: Session, rec_id: int) -> Recommendation:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(404)
    return rec


@router.post("/recommendations/{rec_id}/explain", response_class=HTMLResponse)
def explain(rec_id: int, request: Request, session: Session = Depends(get_session)):
    rec = _get_rec(session, rec_id)
    if not rec.ai_explanation:
        try:
            rec.ai_explanation = ai.explain_recommendation(rec)
        except Exception as exc:
            return _ai_error(request, exc)
        session.commit()
    return _render(
        request, "partials/ai_text.html", text=rec.ai_explanation, label="Объяснение marketPilot AI"
    )


@router.post("/recommendations/{rec_id}/decide", response_class=HTMLResponse)
def decide(
    rec_id: int,
    request: Request,
    decision: str = Form(...),
    comment: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rec = _get_rec(session, rec_id)
    shop.decide(session, rec, decision, comment)
    return _render(request, "partials/rec_card.html", rec=rec, compact=False)


@router.get("/products", response_class=HTMLResponse)
def products(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    _, stats = shop.overview(session)
    open_recs = shop.list_recommendations(session)
    issues: dict[int, list[Recommendation]] = {}
    for r in open_recs:
        if r.product_id:
            issues.setdefault(r.product_id, []).append(r)
    return _render(request, "products.html", active="products", stats=stats, issues=issues)


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(
    product_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    product = session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.sales),
            selectinload(Product.reviews),
            selectinload(Product.campaigns),
        )
    )
    if product is None:
        raise HTTPException(404)
    st = analytics.compute_stats(product)
    recs = [
        r for r in shop.list_recommendations(session, status=None) if r.product_id == product_id
    ]
    return _render(
        request,
        "product.html",
        active="products",
        p=product,
        st=st,
        recs=recs,
        causes=analytics.diagnose_drop(st),
    )


@router.post("/products/{product_id}/reviews/analyze", response_class=HTMLResponse)
def analyze_reviews(
    product_id: int,
    request: Request,
    fresh: bool = False,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404)
    if fresh or not product.review_analysis:
        try:
            product.review_analysis = ai.analyze_reviews(product)
        except Exception as exc:
            return _ai_error(request, exc)
        session.commit()
    return _render(request, "partials/review_analysis.html", a=product.review_analysis, p=product)


@router.post("/ai/digest", response_class=HTMLResponse)
def digest(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    kpis, stats = shop.overview(session)
    try:
        text = ai.weekly_digest(kpis, stats, shop.list_recommendations(session))
    except Exception as exc:
        return _ai_error(request, exc)
    return _render(request, "partials/ai_text.html", text=text, label="Сводка недели")


@router.get("/copilot", response_class=HTMLResponse)
def copilot(request: Request) -> HTMLResponse:
    return _render(request, "copilot.html", active="copilot")


@router.post("/copilot/ask", response_class=HTMLResponse)
def copilot_ask(
    request: Request, question: str = Form(...), session: Session = Depends(get_session)
) -> HTMLResponse:
    kpis, stats = shop.overview(session)
    try:
        answer = ai.ask_copilot(question, kpis, stats, shop.list_recommendations(session))
    except Exception as exc:
        return _ai_error(request, exc)
    return _render(request, "partials/chat_pair.html", question=question, answer=answer)


@router.get("/journal", response_class=HTMLResponse)
def journal(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    entries = shop.journal(session)
    accepted = [e for e in entries if e.decision == "accepted"]
    return _render(
        request,
        "journal.html",
        active="journal",
        entries=entries,
        accepted_effect=sum(e.snapshot_effect_rub for e in accepted),
        accepted=len(accepted),
        rejected=len(entries) - len(accepted),
    )


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    return _render(request, "about.html", active="about", assumptions=analytics.ASSUMPTIONS)


@router.post("/demo/reset")
def reset_demo(session: Session = Depends(get_session)) -> RedirectResponse:
    shop.reset_demo(session)
    return RedirectResponse("/", status_code=303)
