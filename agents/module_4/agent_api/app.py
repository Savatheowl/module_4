import pickle
import os
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from shared import database
from shared.models import (
    MaterialCreate,
    MaterialResponse,
    TrajectoryRequest,
    TrajectoryResponse,
    TimeEstimation,
)

_models: dict = {}


def _load_models() -> None:
    models_dir = Path(os.path.join("save_models"))
    if not models_dir.exists():
        return
    for pkl_file in models_dir.glob("*.pkl"):
        _models[pkl_file.stem] = pickle.loads(pkl_file.read_bytes())


def _ensure_db() -> None:
    database.init_db()


@asynccontextmanager
async def lifespan(a):
    _ensure_db()
    _load_models()
    yield


app = FastAPI(title="API", version="1.0.0", lifespan=lifespan)

@app.get("/")
def do_nth():
    return {"status": "working!"}

def _material_to_response(m: dict) -> MaterialResponse:
    return MaterialResponse(
        id=m["id"],
        subject=m["subject"],
        topic=m["topic"],
        text_content=m["text_content"],
        annotation=m["annotation"],
        moderation_verdict=m["moderation_verdict"],
        source_url=m["source_url"],
        file_type=m["file_type"],
        media_descriptions=m["media_descriptions"],
        class_type=m["class_type"],
        is_generated=m["is_generated"],
        has_previous=m["has_previous"],
        has_next=m["has_next"],
        previous_material_id=m.get("previous_material_id"),
        next_material_id=m.get("next_material_id"),
        cluster_parallel=m.get("cluster_parallel"),
        cluster_sequential=m.get("cluster_sequential"),
        complexity_level=m.get("complexity_level"),
        estimated_time_hours=m.get("estimated_time_hours"),
    )


@app.get("/materials", response_model=list[MaterialResponse])
def list_materials():
    materials = database.get_all_materials()
    return [_material_to_response(m) for m in materials]


@app.get("/materials/{material_id}", response_model=MaterialResponse)
def get_material(material_id: int):
    m = database.get_material(material_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return _material_to_response(m)


@app.post("/materials", response_model=MaterialResponse, status_code=201)
def create_material(body: MaterialCreate):
    mid = database.insert_material(
        subject=body.subject,
        topic=body.topic,
        text_content=body.text_content,
        annotation=body.annotation,
        source_url=body.source_url,
        file_type=body.file_type,
        media_descriptions=body.media_descriptions,
        class_type=body.class_type,
        is_generated=body.is_generated,
    )
    return _material_to_response(database.get_material(mid))


@app.get("/clusters/{strategy}", response_model=list[MaterialResponse])
def get_cluster_materials(strategy: str, cluster_id: int = 0):
    field_map = {
        "parallel": "cluster_parallel",
        "sequential": "cluster_sequential",
    }
    field = field_map.get(strategy)
    if field is None:
        raise HTTPException(status_code=400, detail="Strategy must be 'parallel' or 'sequential'")
    all_mats = database.get_all_materials()
    filtered = [m for m in all_mats if m.get(field) == cluster_id]
    return [_material_to_response(m) for m in filtered]


@app.post("/trajectory", response_model=TrajectoryResponse)
def build_trajectory(request: TrajectoryRequest):
    from agents.module_3.agent_predictor.predictor import build_trajectory as _build
    return _build(request)


@app.get("/time/{material_id}", response_model=TimeEstimation)
def estimate_time(material_id: int):
    from agents.module_3.agent_predictor.predictor import estimate_time as _estimate
    m = database.get_material(material_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return _estimate(material_id)


@app.get("/models", response_model=dict)
def loaded_models():
    return {"loaded": list(_models.keys()), "count": len(_models)}
