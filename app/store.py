"""Operaciones en memoria, sin base de datos (se pierden al reiniciar)."""

from datetime import datetime
from threading import Lock

from app.generador import generar
from app.modelos import Caso, Operacion

MAX_OPERACIONES = 9999  # el formato OP-0000 admite hasta OP-9999


class LimiteDeOperaciones(Exception):
    pass


class Store:
    def __init__(self) -> None:
        self._operaciones: dict[str, Operacion] = {}
        self._ultimo_numero = 0
        self._lock = Lock()

    def crear(self, caso: Caso, inicio: datetime) -> Operacion:
        """Genera una operación del caso con el próximo ID libre (OP-0001, OP-0002…)."""
        with self._lock:
            if self._ultimo_numero >= MAX_OPERACIONES:
                raise LimiteDeOperaciones(
                    f"Se alcanzó el máximo de {MAX_OPERACIONES} operaciones"
                )
            self._ultimo_numero += 1
            id_operacion = f"OP-{self._ultimo_numero:04d}"
            operacion = generar(caso, id_operacion, inicio)
            self._operaciones[id_operacion] = operacion
            return operacion

    def obtener(self, id_operacion: str) -> Operacion | None:
        return self._operaciones.get(id_operacion)
