"""Modelos y textos fijos de PayTrace.

Los nombres de casos, tipos de evento, códigos, causas y recomendaciones
son copia literal del PRD (§1 Términos y §3 tabla de casos). Los criterios
de aceptación comparan textos exactos: no reformular.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Caso(StrEnum):
    """Escenarios que se pueden generar (RF-01, tabla de §3)."""

    OK = "OK"
    FONDOS_INSUFICIENTES = "fondos insuficientes"
    CUENTA_INCORRECTA = "cuenta incorrecta"
    TIMEOUT_CON_REVERSA = "timeout con reversa"
    TIMEOUT_SIN_REVERSA = "timeout sin reversa"
    TRACE_INCOMPLETO = "trace incompleto"


class Estado(StrEnum):
    OK = "OK"
    FALLIDA = "fallida"
    PENDIENTE = "pendiente"


class TipoEvento(StrEnum):
    ORDEN_ENVIADA = "orden_enviada"
    DEBITO_ORIGEN = "debito_origen"
    ENVIO_PROVEEDOR = "envio_proveedor"
    ACEPTACION_PROVEEDOR = "aceptacion_proveedor"
    ACREDITACION_DESTINO = "acreditacion_destino"
    RECHAZO_ORIGEN = "rechazo_origen"
    RECHAZO_BANCO_DESTINO = "rechazo_banco_destino"
    RECHAZO_TIMEOUT = "rechazo_timeout"
    REVERSA_DEBITO = "reversa_debito"


class Emisor(StrEnum):
    ORIGEN = "origen"
    PROVEEDOR = "proveedor"
    BANCO_DESTINO = "banco destino"


class CodigoMotivo(StrEnum):
    """Códigos de motivo ISO 20022 que usa el MVP (y ningún otro)."""

    AM04 = "AM04"  # fondos insuficientes
    AC01 = "AC01"  # la cuenta no existe en el banco destino
    AB05 = "AB05"  # timeout del banco destino


class Causa(StrEnum):
    FONDOS_INSUFICIENTES = "fondos insuficientes"
    CUENTA_INCORRECTA = "cuenta incorrecta"
    TIMEOUT = "timeout"
    NO_CONCLUYENTE = "no concluyente"


# Solo los 3 tipos de rechazo tienen código; el resto es "sin código".
CODIGO_POR_TIPO: dict[TipoEvento, CodigoMotivo] = {
    TipoEvento.RECHAZO_ORIGEN: CodigoMotivo.AM04,
    TipoEvento.RECHAZO_BANCO_DESTINO: CodigoMotivo.AC01,
    TipoEvento.RECHAZO_TIMEOUT: CodigoMotivo.AB05,
}

# Columna "Recomendación" de la tabla de casos (AC-08 exige el texto exacto).
# El caso OK no tiene recomendación: no se diagnostica (RF-09).
RECOMENDACION_POR_CASO: dict[Caso, str] = {
    Caso.FONDOS_INSUFICIENTES: (
        "Avisar al cliente que no tenía saldo. No se debitó nada"
    ),
    Caso.CUENTA_INCORRECTA: (
        "Pedir al cliente que verifique el CBU/CVU y confirmar que la reversa se acreditó"
    ),
    Caso.TIMEOUT_CON_REVERSA: (
        "El débito ya se devolvió: se puede reintentar la transferencia"
    ),
    Caso.TIMEOUT_SIN_REVERSA: (
        "El débito todavía no se devolvió: pedir la reversa antes de reintentar. "
        "Si se reintenta antes, se cobra dos veces"
    ),
    Caso.TRACE_INCOMPLETO: (
        "Pedir los logs del proveedor desde el último evento conocido"
    ),
}

MENSAJE_SIN_FALLO = "La operación no tiene un fallo para investigar"  # AC-10
MENSAJE_NO_ENCONTRADA = "Operación no encontrada"  # AC-04

PATRON_ID_OPERACION = r"^OP-[0-9]{4}$"


class Evento(BaseModel):
    id: str
    momento: datetime
    tipo: TipoEvento
    emisor: Emisor
    codigo: CodigoMotivo | None = None

    @model_validator(mode="after")
    def codigo_coherente_con_tipo(self) -> "Evento":
        esperado = CODIGO_POR_TIPO.get(self.tipo)
        if self.codigo != esperado:
            raise ValueError(
                f"El evento {self.tipo} debe tener código {esperado}, no {self.codigo}"
            )
        return self


class Operacion(BaseModel):
    id: str = Field(pattern=PATRON_ID_OPERACION)
    estado: Estado
    trace: list[Evento]


class Diagnostico(BaseModel):
    causa: Causa
    eventos_citados: list[str]
    recomendacion: str

    @model_validator(mode="after")
    def evidencia_segun_causa(self) -> "Diagnostico":
        # Principio de producto: una causa cita exactamente un evento;
        # "no concluyente" no cita ninguno.
        if self.causa == Causa.NO_CONCLUYENTE:
            if self.eventos_citados:
                raise ValueError('"no concluyente" no puede citar eventos')
        elif len(self.eventos_citados) != 1:
            raise ValueError("una causa debe citar exactamente un evento")
        return self
