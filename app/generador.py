"""Generador de operaciones simuladas (RF-01).

Arma el trace de cada caso según la tabla de §3 del PRD. Es una función
pura: con el mismo caso, ID e inicio devuelve siempre la misma operación.
"""

from datetime import datetime, timedelta

from app.modelos import (
    CODIGO_POR_TIPO,
    Caso,
    Emisor,
    Estado,
    Evento,
    Operacion,
    TipoEvento,
)

T = TipoEvento

# Trace de cada caso, del evento más antiguo al más nuevo (tabla de §3).
TRACE_POR_CASO: dict[Caso, list[TipoEvento]] = {
    Caso.OK: [
        T.ORDEN_ENVIADA,
        T.DEBITO_ORIGEN,
        T.ACEPTACION_PROVEEDOR,
        T.ACREDITACION_DESTINO,
    ],
    Caso.FONDOS_INSUFICIENTES: [
        T.ORDEN_ENVIADA,
        T.RECHAZO_ORIGEN,
    ],
    Caso.CUENTA_INCORRECTA: [
        T.ORDEN_ENVIADA,
        T.DEBITO_ORIGEN,
        T.RECHAZO_BANCO_DESTINO,
        T.REVERSA_DEBITO,
    ],
    Caso.TIMEOUT_CON_REVERSA: [
        T.ORDEN_ENVIADA,
        T.DEBITO_ORIGEN,
        T.ENVIO_PROVEEDOR,
        T.RECHAZO_TIMEOUT,
        T.REVERSA_DEBITO,
    ],
    Caso.TIMEOUT_SIN_REVERSA: [
        T.ORDEN_ENVIADA,
        T.DEBITO_ORIGEN,
        T.ENVIO_PROVEEDOR,
        T.RECHAZO_TIMEOUT,
    ],
    Caso.TRACE_INCOMPLETO: [
        T.ORDEN_ENVIADA,
        T.DEBITO_ORIGEN,
    ],
}

ESTADO_POR_CASO: dict[Caso, Estado] = {
    Caso.OK: Estado.OK,
    Caso.FONDOS_INSUFICIENTES: Estado.FALLIDA,
    Caso.CUENTA_INCORRECTA: Estado.FALLIDA,
    Caso.TIMEOUT_CON_REVERSA: Estado.FALLIDA,
    Caso.TIMEOUT_SIN_REVERSA: Estado.FALLIDA,
    Caso.TRACE_INCOMPLETO: Estado.PENDIENTE,
}

# Quién emite cada tipo de evento. El timeout lo informa el proveedor.
EMISOR_POR_TIPO: dict[TipoEvento, Emisor] = {
    T.ORDEN_ENVIADA: Emisor.ORIGEN,
    T.DEBITO_ORIGEN: Emisor.ORIGEN,
    T.ENVIO_PROVEEDOR: Emisor.ORIGEN,
    T.ACEPTACION_PROVEEDOR: Emisor.PROVEEDOR,
    T.ACREDITACION_DESTINO: Emisor.BANCO_DESTINO,
    T.RECHAZO_ORIGEN: Emisor.ORIGEN,
    T.RECHAZO_BANCO_DESTINO: Emisor.BANCO_DESTINO,
    T.RECHAZO_TIMEOUT: Emisor.PROVEEDOR,
    T.REVERSA_DEBITO: Emisor.ORIGEN,
}

# Separación fija entre eventos consecutivos del trace.
PASO_ENTRE_EVENTOS = timedelta(seconds=30)


def generar(caso: Caso, id_operacion: str, inicio: datetime) -> Operacion:
    """Genera la operación simulada del caso elegido.

    `inicio` es el momento del primer evento; cada evento siguiente ocurre
    PASO_ENTRE_EVENTOS después del anterior. Los eventos se identifican
    como `<id_operacion>-E<n>`, con n desde 1.
    """
    trace = [
        Evento(
            id=f"{id_operacion}-E{n}",
            momento=inicio + (n - 1) * PASO_ENTRE_EVENTOS,
            tipo=tipo,
            emisor=EMISOR_POR_TIPO[tipo],
            codigo=CODIGO_POR_TIPO.get(tipo),
        )
        for n, tipo in enumerate(TRACE_POR_CASO[caso], start=1)
    ]
    return Operacion(id=id_operacion, estado=ESTADO_POR_CASO[caso], trace=trace)
