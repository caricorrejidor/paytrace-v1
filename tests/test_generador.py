from datetime import datetime, timezone

import pytest

from app.generador import PASO_ENTRE_EVENTOS, generar
from app.modelos import Caso, CodigoMotivo, Emisor, Estado, TipoEvento

INICIO = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
T = TipoEvento


# AC-01 (RF-01) · Generar una operación de cada caso
@pytest.mark.parametrize(
    ("caso", "estado", "tipo", "codigo", "ultimo_tipo"),
    [
        (Caso.OK, Estado.OK, T.ACREDITACION_DESTINO, None, T.ACREDITACION_DESTINO),
        (Caso.FONDOS_INSUFICIENTES, Estado.FALLIDA, T.RECHAZO_ORIGEN, CodigoMotivo.AM04, T.RECHAZO_ORIGEN),
        (Caso.CUENTA_INCORRECTA, Estado.FALLIDA, T.RECHAZO_BANCO_DESTINO, CodigoMotivo.AC01, T.REVERSA_DEBITO),
        (Caso.TIMEOUT_CON_REVERSA, Estado.FALLIDA, T.RECHAZO_TIMEOUT, CodigoMotivo.AB05, T.REVERSA_DEBITO),
        (Caso.TIMEOUT_SIN_REVERSA, Estado.FALLIDA, T.RECHAZO_TIMEOUT, CodigoMotivo.AB05, T.RECHAZO_TIMEOUT),
        (Caso.TRACE_INCOMPLETO, Estado.PENDIENTE, T.DEBITO_ORIGEN, None, T.DEBITO_ORIGEN),
    ],
)
def test_ac01_generar_operacion_de_cada_caso(caso, estado, tipo, codigo, ultimo_tipo):
    op = generar(caso, "OP-0001", INICIO)

    assert op.estado == estado
    assert any(e.tipo == tipo and e.codigo == codigo for e in op.trace)
    assert op.trace[-1].tipo == ultimo_tipo


# Secuencia completa de cada caso, según la tabla de §3
@pytest.mark.parametrize(
    ("caso", "tipos"),
    [
        (Caso.OK, [T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.ACEPTACION_PROVEEDOR, T.ACREDITACION_DESTINO]),
        (Caso.FONDOS_INSUFICIENTES, [T.ORDEN_ENVIADA, T.RECHAZO_ORIGEN]),
        (Caso.CUENTA_INCORRECTA, [T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.RECHAZO_BANCO_DESTINO, T.REVERSA_DEBITO]),
        (
            Caso.TIMEOUT_CON_REVERSA,
            [T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.ENVIO_PROVEEDOR, T.RECHAZO_TIMEOUT, T.REVERSA_DEBITO],
        ),
        (Caso.TIMEOUT_SIN_REVERSA, [T.ORDEN_ENVIADA, T.DEBITO_ORIGEN, T.ENVIO_PROVEEDOR, T.RECHAZO_TIMEOUT]),
        (Caso.TRACE_INCOMPLETO, [T.ORDEN_ENVIADA, T.DEBITO_ORIGEN]),
    ],
)
def test_trace_completo_de_cada_caso(caso, tipos):
    op = generar(caso, "OP-0001", INICIO)
    assert [e.tipo for e in op.trace] == tipos


# AC-05 (RF-04) · El trace de "cuenta incorrecta" tiene 4 eventos en orden
def test_ac05_cuenta_incorrecta_tiene_4_eventos_en_orden():
    op = generar(Caso.CUENTA_INCORRECTA, "OP-0001", INICIO)

    assert len(op.trace) == 4
    momentos = [e.momento for e in op.trace]
    assert momentos == sorted(momentos)


@pytest.mark.parametrize("caso", list(Caso))
def test_momentos_estrictamente_crecientes_desde_el_inicio(caso):
    op = generar(caso, "OP-0001", INICIO)

    assert op.trace[0].momento == INICIO
    for anterior, siguiente in zip(op.trace, op.trace[1:]):
        assert siguiente.momento - anterior.momento == PASO_ENTRE_EVENTOS


@pytest.mark.parametrize("caso", list(Caso))
def test_ids_de_evento_unicos_y_de_la_operacion(caso):
    op = generar(caso, "OP-0042", INICIO)

    ids = [e.id for e in op.trace]
    assert ids == [f"OP-0042-E{n}" for n in range(1, len(op.trace) + 1)]


@pytest.mark.parametrize("caso", list(Caso))
def test_generacion_determinista(caso):
    assert generar(caso, "OP-0001", INICIO) == generar(caso, "OP-0001", INICIO)


def test_el_timeout_lo_informa_el_proveedor():
    op = generar(Caso.TIMEOUT_SIN_REVERSA, "OP-0001", INICIO)
    timeout = next(e for e in op.trace if e.tipo == T.RECHAZO_TIMEOUT)
    assert timeout.emisor == Emisor.PROVEEDOR


def test_el_rechazo_de_cuenta_lo_emite_el_banco_destino():
    op = generar(Caso.CUENTA_INCORRECTA, "OP-0001", INICIO)
    rechazo = next(e for e in op.trace if e.tipo == T.RECHAZO_BANCO_DESTINO)
    assert rechazo.emisor == Emisor.BANCO_DESTINO
