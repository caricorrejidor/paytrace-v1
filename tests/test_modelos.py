from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modelos import (
    RECOMENDACION_POR_CASO,
    Caso,
    Causa,
    CodigoMotivo,
    Diagnostico,
    Emisor,
    Estado,
    Evento,
    Operacion,
    TipoEvento,
)

MOMENTO = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def evento(tipo, codigo=None, id_="OP-0001-E1"):
    return Evento(id=id_, momento=MOMENTO, tipo=tipo, emisor=Emisor.ORIGEN, codigo=codigo)


# --- Textos fijos (copia literal del PRD) ---


def test_casos_del_prd():
    assert [c.value for c in Caso] == [
        "OK",
        "fondos insuficientes",
        "cuenta incorrecta",
        "timeout con reversa",
        "timeout sin reversa",
        "trace incompleto",
    ]


def test_tipos_de_evento_del_prd():
    assert {t.value for t in TipoEvento} == {
        "orden_enviada",
        "debito_origen",
        "envio_proveedor",
        "aceptacion_proveedor",
        "acreditacion_destino",
        "rechazo_origen",
        "rechazo_banco_destino",
        "rechazo_timeout",
        "reversa_debito",
    }


def test_causas_del_prd():
    assert {c.value for c in Causa} == {
        "fondos insuficientes",
        "cuenta incorrecta",
        "timeout",
        "no concluyente",
    }


@pytest.mark.parametrize(
    ("caso", "texto"),
    [
        (Caso.FONDOS_INSUFICIENTES, "Avisar al cliente que no tenía saldo. No se debitó nada"),
        (
            Caso.CUENTA_INCORRECTA,
            "Pedir al cliente que verifique el CBU/CVU y confirmar que la reversa se acreditó",
        ),
        (Caso.TIMEOUT_CON_REVERSA, "El débito ya se devolvió: se puede reintentar la transferencia"),
        (
            Caso.TIMEOUT_SIN_REVERSA,
            "El débito todavía no se devolvió: pedir la reversa antes de reintentar. "
            "Si se reintenta antes, se cobra dos veces",
        ),
        (Caso.TRACE_INCOMPLETO, "Pedir los logs del proveedor desde el último evento conocido"),
    ],
)
def test_recomendaciones_textuales(caso, texto):
    assert RECOMENDACION_POR_CASO[caso] == texto


def test_ok_no_tiene_recomendacion():
    assert Caso.OK not in RECOMENDACION_POR_CASO


# --- Evento: solo los rechazos llevan código, y el suyo ---


@pytest.mark.parametrize(
    ("tipo", "codigo"),
    [
        (TipoEvento.RECHAZO_ORIGEN, CodigoMotivo.AM04),
        (TipoEvento.RECHAZO_BANCO_DESTINO, CodigoMotivo.AC01),
        (TipoEvento.RECHAZO_TIMEOUT, CodigoMotivo.AB05),
        (TipoEvento.DEBITO_ORIGEN, None),
    ],
)
def test_evento_valido(tipo, codigo):
    assert evento(tipo, codigo).codigo == codigo


@pytest.mark.parametrize(
    ("tipo", "codigo"),
    [
        (TipoEvento.RECHAZO_ORIGEN, None),  # rechazo sin código
        (TipoEvento.RECHAZO_ORIGEN, CodigoMotivo.AC01),  # código equivocado
        (TipoEvento.DEBITO_ORIGEN, CodigoMotivo.AM04),  # código en evento que no es rechazo
    ],
)
def test_evento_con_codigo_incoherente_se_rechaza(tipo, codigo):
    with pytest.raises(ValidationError):
        evento(tipo, codigo)


def test_codigo_fuera_del_mvp_se_rechaza():
    with pytest.raises(ValidationError):
        evento(TipoEvento.RECHAZO_ORIGEN, "AM02")


# --- Operacion: ID con formato OP-0000 ---


@pytest.mark.parametrize("id_", ["op-0001", "OP-00001", "OP-001", "OP-0001 ", ""])
def test_operacion_con_id_mal_formado_se_rechaza(id_):
    with pytest.raises(ValidationError):
        Operacion(id=id_, estado=Estado.PENDIENTE, trace=[])


def test_operacion_valida():
    op = Operacion(id="OP-0001", estado=Estado.PENDIENTE, trace=[evento(TipoEvento.ORDEN_ENVIADA)])
    assert op.id == "OP-0001"


# --- Diagnostico: principio de producto ---


def test_diagnostico_con_causa_cita_un_evento():
    d = Diagnostico(causa=Causa.TIMEOUT, eventos_citados=["OP-0001-E4"], recomendacion="x")
    assert d.eventos_citados == ["OP-0001-E4"]


@pytest.mark.parametrize("citados", [[], ["E1", "E2"]])
def test_diagnostico_con_causa_sin_exactamente_un_evento_se_rechaza(citados):
    with pytest.raises(ValidationError):
        Diagnostico(causa=Causa.TIMEOUT, eventos_citados=citados, recomendacion="x")


def test_no_concluyente_no_cita_eventos():
    d = Diagnostico(causa=Causa.NO_CONCLUYENTE, eventos_citados=[], recomendacion="x")
    assert d.eventos_citados == []


def test_no_concluyente_con_eventos_se_rechaza():
    with pytest.raises(ValidationError):
        Diagnostico(causa=Causa.NO_CONCLUYENTE, eventos_citados=["E1"], recomendacion="x")
