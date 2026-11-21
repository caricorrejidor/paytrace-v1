from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from app.modelos import (
    MENSAJE_NO_ENCONTRADA,
    MENSAJE_SIN_FALLO,
    Caso,
    Diagnostico,
    Estado,
    Operacion,
)
from app.reglas import diagnosticar
from app.store import LimiteDeOperaciones, Store

app = FastAPI(
    title="PayTrace",
    description=(
        "Diagnostica por qué falló o quedó pendiente una transferencia simulada. "
        "Aplica reglas fijas al trace, cita el evento que prueba la causa y "
        "recomienda el próximo paso."
    ),
    version="0.1.0",
)

_store = Store()


def obtener_store() -> Store:
    return _store


StoreDep = Annotated[Store, Depends(obtener_store)]


class SolicitudOperacion(BaseModel):
    caso: Caso


class SinFallo(BaseModel):
    mensaje: str


class Error(BaseModel):
    detail: str


@app.post(
    "/operaciones",
    status_code=status.HTTP_201_CREATED,
    summary="Generar una operación simulada (RF-01)",
)
def crear_operacion(solicitud: SolicitudOperacion, store: StoreDep) -> Operacion:
    try:
        return store.crear(solicitud.caso, inicio=datetime.now(timezone.utc))
    except LimiteDeOperaciones as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e)) from e


@app.post(
    "/operaciones/{id_operacion}/diagnostico",
    summary="Pedir el diagnóstico de una operación (RF-05 a RF-09)",
    responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
)
def pedir_diagnostico(id_operacion: str, store: StoreDep) -> Diagnostico | SinFallo:
    operacion = store.obtener(id_operacion)
    if operacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=MENSAJE_NO_ENCONTRADA)
    # RF-09: una operación OK no se diagnostica.
    if operacion.estado == Estado.OK:
        return SinFallo(mensaje=MENSAJE_SIN_FALLO)
    return diagnosticar(operacion.trace)
