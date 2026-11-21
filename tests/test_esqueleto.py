from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_docs_responde():
    respuesta = client.get("/docs")
    assert respuesta.status_code == 200


def test_openapi_tiene_el_titulo_de_paytrace():
    respuesta = client.get("/openapi.json")
    assert respuesta.status_code == 200
    assert respuesta.json()["info"]["title"] == "PayTrace"
