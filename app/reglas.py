"""Motor de reglas del diagnóstico (RF-05 a RF-08).

Reglas fijas que miran solo el trace: no conocen el caso con el que se
generó la operación. Ante cualquier duda, el resultado es "no concluyente".
El aviso de operación OK (RF-09) se resuelve antes, en la API, por estado.
"""

from app.modelos import (
    CODIGO_POR_TIPO,
    RECOMENDACION_POR_CASO,
    Caso,
    Causa,
    Diagnostico,
    Evento,
    TipoEvento,
)

T = TipoEvento

# Causa que prueba cada tipo de rechazo. El código ya viene validado por
# el modelo Evento (cada rechazo solo puede tener su propio código).
CAUSA_POR_RECHAZO: dict[TipoEvento, Causa] = {
    T.RECHAZO_ORIGEN: Causa.FONDOS_INSUFICIENTES,
    T.RECHAZO_BANCO_DESTINO: Causa.CUENTA_INCORRECTA,
    T.RECHAZO_TIMEOUT: Causa.TIMEOUT,
}


def diagnosticar(trace: list[Evento]) -> Diagnostico:
    rechazos = [e for e in trace if e.tipo in CODIGO_POR_TIPO]
    hubo_acreditacion = any(e.tipo == T.ACREDITACION_DESTINO for e in trace)

    # Se nombra una causa solo si hay exactamente un rechazo y ninguna
    # acreditación que lo contradiga.
    if len(rechazos) != 1 or hubo_acreditacion:
        return _no_concluyente()

    rechazo = rechazos[0]
    return Diagnostico(
        causa=CAUSA_POR_RECHAZO[rechazo.tipo],
        eventos_citados=[rechazo.id],
        recomendacion=_recomendacion(rechazo, trace),
    )


def _recomendacion(rechazo: Evento, trace: list[Evento]) -> str:
    if rechazo.tipo == T.RECHAZO_ORIGEN:
        return RECOMENDACION_POR_CASO[Caso.FONDOS_INSUFICIENTES]
    if rechazo.tipo == T.RECHAZO_BANCO_DESTINO:
        return RECOMENDACION_POR_CASO[Caso.CUENTA_INCORRECTA]

    # Timeout: la recomendación depende de si el débito ya se devolvió.
    # Solo cuenta una reversa posterior al rechazo; si no la hay, se pide
    # la reversa antes de reintentar (evita cobrar dos veces).
    hubo_reversa = any(
        e.tipo == T.REVERSA_DEBITO and e.momento > rechazo.momento for e in trace
    )
    if hubo_reversa:
        return RECOMENDACION_POR_CASO[Caso.TIMEOUT_CON_REVERSA]
    return RECOMENDACION_POR_CASO[Caso.TIMEOUT_SIN_REVERSA]


def _no_concluyente() -> Diagnostico:
    return Diagnostico(
        causa=Causa.NO_CONCLUYENTE,
        eventos_citados=[],
        recomendacion=RECOMENDACION_POR_CASO[Caso.TRACE_INCOMPLETO],
    )
