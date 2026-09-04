from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, settings
from database import DEMO_CUSTOMERS
from utils import format_currency, format_datetime, format_time, friendly_label, mask_cpf
from utils import format_cpf


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters.update(
    br_datetime=format_datetime,
    br_time=format_time,
    friendly=friendly_label,
    cpf_mask=mask_cpf,
    currency=format_currency,
)


def _render(request: Request, template: str, page: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={"page": page, "demo_fallback": settings.demo_fallback, **context},
    )


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    demo_customers = [
        {"cpf": format_cpf(cpf), "name": name} for cpf, name in DEMO_CUSTOMERS
    ]
    return _render(request, "index.html", "home", demo_customers=demo_customers)


@router.get("/telefone", response_class=HTMLResponse)
def telefone(request: Request):
    return _render(request, "telefone.html", "telefone")


@router.get("/whatsapp", response_class=HTMLResponse)
def whatsapp(request: Request):
    return _render(request, "whatsapp.html", "whatsapp")


@router.get("/minha-claro", response_class=HTMLResponse)
def minha_claro(request: Request):
    return _render(request, "minha_claro.html", "minha-claro")


@router.get("/atendente", response_class=HTMLResponse)
def atendente(request: Request):
    return _render(request, "atendente.html", "atendente")


@router.get("/debug", response_class=HTMLResponse)
def debug(request: Request):
    return _render(request, "debug.html", "debug")
