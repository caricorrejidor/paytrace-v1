from datetime import datetime, timedelta, timezone

import pytest

from app.generador import EMISOR_POR_TIPO, generar
from app.modelos import (
    CODIGO_POR_TIPO,
    RECOMENDACION_POR_CASO,
    Caso,
    Causa,
    CodigoMotivo,
    Evento,
    TipoEvento,
)
from app.reglas import diagnosticar

INICIO = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
T = TipoEvento


def diagnostico_de(caso):
    op = generar(caso, "OP-0001", INICIO)
    return op, diagnosticar(op.trace)


def trace_de(*tipos):
    """Arma un trace a mano, en orden, para probar situaciones fuera de la tabla."""
    return [
        Evento(
            id=f"OP-0001-E{n}",
            momento=INICIO + timedelta(seconds=30 * n),
            tipo=tipo,
            emisor=EMISOR_POR_TIPO[tipo],
            codigo=CODIGO_POR_TIPO.get(tipo),
        )
        for n, tipo in enumerate(tipos, start=1)
    ]


# AC-06 (RF-05) · Causa correcta por caso
@pytest.mark.parametrize(
    ("caso", "causa"),
    [
        (Caso.FONDOS_INSUFICIENTES, "fondos insuficientes"),
        (Caso.CUENTA_INCORRECTA, "cuenta incorrecta"),
        (Caso.TIMEOUT_CON_REVERSA, "timeout"),
        (Caso.TIMEOUT_SIN_REVERSA, "timeout"),
    ],
)
def test_ac06_causa_correcta_por_caso(caso, causa):
    _, d = diagnostico_de(caso)
    assert d.causa == causa


# AC-07 (RF-06) · Evidencia del trace
@pytest.mark.parametrize(
    ("caso", "tipo", "codigo"),
    [
        (Caso.FONDOS_INSUFICIENTES, T.RECHAZO_ORIGEN, CodigoMotivo.AM04),
        (Caso.CUENTA_INCORRECTA, T.RECHAZO_BANCO_DESTINO, CodigoMotivo.AC01),
        (Caso.TIMEOUT_CON_REVERSA, T.RECHAZO_TIMEOUT, CodigoMotivo.AB05),
        (Caso.TIMEOUT_SIN_REVERSA, T.RECHAZO_TIMEOUT, CodigoMotivo.AB05),
    ],
)
def test_ac07_cita_un_solo_evento_del_trace(caso, tipo, codigo):
    op, d = diagnostico_de(caso)

    assert len(d.eventos_citados) == 1
    citado = next(e for e in op.trace if e.id == d.eventos_citados[0])
    assert citado.tipo == tipo
    assert citado.codigo == codigo


# AC-08 (RF-07) · Recomendación según la causa
@pytest.mark.parametrize(
    "caso",
    [
        Caso.FONDOS_INSUFICIENTES,
        Caso.CUENTA_INCORRECTA,
        Caso.TIMEOUT_CON_REVERSA,
        Caso.TIMEOUT_SIN_REVERSA,
        Caso.TRACE_INCOMPLETO,
    ],
)
def test_ac08_recomendacion_de_la_tabla(caso):
    _, d = diagnostico_de(caso)
    assert d.recomendacion == RECOMENDACION_POR_CASO[caso]


# AC-09 (RF-08) · No concluyente
def test_ac09_trace_incompleto_es_no_concluyente():
    _, d = diagnostico_de(Caso.TRACE_INCOMPLETO)

    assert d.causa == "no concluyente"
    assert d.eventos_citados == []


# RNF-04 · Consistencia: 5 pedidos, el mismo resultado
@pytest.mark.parametrize("caso", [c for c in Caso if c != Caso.OK])
def test_rnf04_mismo_resultado_5_veces(caso):
    op = generar(caso, "OP-0001", INICIO)
    resultados = [diagnosticar(op.trace) for _ in range(5)]
    assert all(r == resultados[0] for r in resultados)


# --- Traces fuera de la tabla: ante la duda, "no concluyente" ---


def test_trace_vacio_es_no_concluyente():
    d = diagnosticar([])
    assert d.causa == Causa.NO_CONCLUYENTE
    assert d.eventos_citados == []


def test_dos_rechazos_es_no_concluyente():
    d = diagnosticar(trace_de(T.ORDEN_ENVIADA, T.RECHAZO_ORIGEN, T.RECHAZO_TIMEOUT))
    assert d.causa == Causa.NO_CONCLUYENTE
    assert d.eventos_citados == []


def test_rechazo_con_acreditacion_es_no_concluyente():
    d = diagnosticar(
        trace_de(T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.RECHAZO_BANCO_DESTINO, T.ACREDITACION_DESTINO)
    )
    assert d.causa == Causa.NO_CONCLUYENTE
    assert d.eventos_citados == []


def test_reglas_no_dependen_del_caso_sino_del_trace():
    # Un trace armado a mano, igual al de "cuenta incorrecta", da la misma causa.
    trace = trace_de(T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.RECHAZO_BANCO_DESTINO, T.REVERSA_DEBITO)
    d = diagnosticar(trace)
    assert d.causa == Causa.CUENTA_INCORRECTA
    assert d.eventos_citados == ["OP-0001-E3"]


def test_timeout_con_reversa_anterior_al_rechazo_cuenta_como_sin_reversa():
    # Una reversa que no es posterior al timeout no prueba que el débito se devolvió.
    trace = trace_de(T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.REVERSA_DEBITO, T.RECHAZO_TIMEOUT)
    d = diagnosticar(trace)
    assert d.causa == Causa.TIMEOUT
    assert d.recomendacion == RECOMENDACION_POR_CASO[Caso.TIMEOUT_SIN_REVERSA]
