import logging
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.RequestModels import GeocodingRequest, Place
from backend.ReverseGeocoding import reverse_geocoding
from backend.userstudy_routes import router as userstudy_router

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
VIEWS_DIR = os.path.join(FRONTEND_DIR, "views")

app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")
app.mount("/views", StaticFiles(directory=VIEWS_DIR), name="views")
app.include_router(userstudy_router)


def serve_view(filename: str) -> FileResponse | dict:
    """Serve una vista statica dello user study dalla cartella frontend/views."""
    file_path = os.path.join(VIEWS_DIR, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)


@app.get("/")
async def root():
    """Reindirizza sempre la root della app al punto di ingresso dello user study."""
    return RedirectResponse(url="/userstudy/welcome", status_code=302)


@app.get("/userstudy/welcome")
async def serve_userstudy_welcome():
    """Serve la pagina iniziale dello user study."""
    return serve_view("userstudy_welcome.html")


@app.get("/userstudy/questionnaire1")
async def serve_userstudy_questionnaire1():
    """Serve il primo questionario anagrafico."""
    return serve_view("userstudy_questionnaire1.html")


@app.get("/userstudy/questionnaire2")
async def serve_userstudy_questionnaire2():
    """Serve il questionario di percezione pre-esplorazione."""
    return serve_view("userstudy_questionnaire2.html")


@app.get("/userstudy/search")
async def serve_userstudy_search():
    """Serve il passo 3 in cui l'utente seleziona la via da analizzare."""
    return serve_view("userstudy_search.html")


@app.get("/userstudy/personal")
async def serve_userstudy_personal():
    """Serve il passo 4 con la scelta personalizzata di categorie e parametri."""
    return serve_view("userstudy_personal.html")


@app.get("/userstudy/results")
async def serve_userstudy_results():
    """Serve il passo 5 con mappa, POI e radar chart dei risultati."""
    return serve_view("userstudy_results.html")


@app.get("/userstudy/questionnaire3")
async def serve_userstudy_questionnaire3():
    """Serve il questionario finale di post-esplorazione."""
    return serve_view("userstudy_questionnaire3.html")


@app.get("/userstudy/thanks")
async def serve_userstudy_thanks():
    """Serve la pagina finale di ringraziamento e download dati."""
    return serve_view("userstudy_thanks.html")


@app.post("/api/geocoding")
def geocoding(request: GeocodingRequest) -> List[Place]:
    """Espone al frontend la ricerca geocodificata di indirizzi usata nello step 3."""
    status_code, message, result = reverse_geocoding(request.text)

    if status_code == 200:
        return result

    raise HTTPException(
        status_code=status_code,
        detail=[{"loc": [], "msg": message, "type": status_code}],
    )








