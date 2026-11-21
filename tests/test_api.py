import pytest
from fastapi.testclient import TestClient

from app.main import app, obtener_store
from app.modelos import RECOMENDACION_POR_CASO, Caso
from app.store import Store


@pytest.fixture
def client():
    # Cada test arranca con un store vacío.
    store = Store()
    app.dependency_overrides[obtener_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def crear(client, caso):
    respuesta = client.post("/operaciones", json={"caso": caso})
    assert respuesta.status_code == 201
    return respuesta.json()


def diagnostico(client, id_operacion):
    return client.post(f"/operaciones/{id_operacion}/diagnostico")


# --- Generar (RF-01) ---


@pytest.mark.parametrize(
    ("caso", "estado"),
    [
        ("OK", "OK"),
        ("fondos insuficientes", "fallida"),
        ("cuenta incorrecta", "fallida"),
        ("timeout con reversa", "fallida"),
        ("timeout sin reversa", "fallida"),
        ("trace incompleto", "pendiente"),
    ],
)
def test_generar_devuelve_operacion_con_estado_y_trace(client, caso, estado):
    op = crear(client, caso)
    assert op["id"] == "OP-0001"
    assert op["estado"] == estado
    assert len(op["trace"]) > 0


def test_ids_secuenciales(client):
    ids = [crear(client, "OK")["id"] for _ in range(3)]
    assert ids == ["OP-0001", "OP-0002", "OP-0003"]


def test_caso_inexistente_da_422(client):
    respuesta = client.post("/operaciones", json={"caso": "importe no permitido"})
    assert respuesta.status_code == 422


# --- Diagnóstico (RF-05 a RF-08) ---


@pytest.mark.parametrize(
    ("caso", "causa", "tipo", "codigo"),
    [
        ("fondos insuficientes", "fondos insuficientes", "rechazo_origen", "AM04"),
        ("cuenta incorrecta", "cuenta incorrecta", "rechazo_banco_destino", "AC01"),
        ("timeout con reversa", "timeout", "rechazo_timeout", "AB05"),
        ("timeout sin reversa", "timeout", "rechazo_timeout", "AB05"),
    ],
)
def test_diagnostico_con_causa(client, caso, causa, tipo, codigo):
    op = crear(client, caso)
    respuesta = diagnostico(client, op["id"])

    assert respuesta.status_code == 200
    d = respuesta.json()
    assert d["causa"] == causa  # AC-06
    assert len(d["eventos_citados"]) == 1  # AC-07
    citado = next(e for e in op["trace"] if e["id"] == d["eventos_citados"][0])
    assert (citado["tipo"], citado["codigo"]) == (tipo, codigo)
    assert d["recomendacion"] == RECOMENDACION_POR_CASO[Caso(caso)]  # AC-08


def test_ac09_trace_incompleto_no_concluyente(client):
    op = crear(client, "trace incompleto")
    d = diagnostico(client, op["id"]).json()

    assert d["causa"] == "no concluyente"
    assert d["eventos_citados"] == []
    assert d["recomendacion"] == RECOMENDACION_POR_CASO[Caso.TRACE_INCOMPLETO]


# AC-10 (RF-09) · Operación OK
def test_ac10_operacion_ok_no_se_diagnostica(client):
    op = crear(client, "OK")
    respuesta = diagnostico(client, op["id"])

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "La operación no tiene un fallo para investigar"}


def test_diagnostico_de_operacion_inexistente_da_404(client):
    respuesta = diagnostico(client, "OP-9999")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Operación no encontrada"}


# RNF-04 · Consistencia por la API
@pytest.mark.parametrize("caso", [c.value for c in Caso])
def test_rnf04_mismo_diagnostico_5_veces(client, caso):
    op = crear(client, caso)
    resultados = [diagnostico(client, op["id"]).json() for _ in range(5)]
    assert all(r == resultados[0] for r in resultados)


def test_limite_de_operaciones_da_409(client):
    store = Store()
    store._ultimo_numero = 9999
    app.dependency_overrides[obtener_store] = lambda: store

    respuesta = client.post("/operaciones", json={"caso": "OK"})
    assert respuesta.status_code == 409
