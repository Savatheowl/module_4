from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    subject: str
    topic: str
    text_content: str
    annotation: str = ""
    source_url: str = ""
    file_type: str = ""
    media_descriptions: list[str] = Field(default_factory=list)
    class_type: str = ""
    is_generated: bool = False


class MaterialResponse(BaseModel):
    id: int
    subject: str
    topic: str
    text_content: str
    annotation: str
    moderation_verdict: str
    source_url: str
    file_type: str
    media_descriptions: list[str]
    class_type: str
    is_generated: bool
    has_previous: bool
    has_next: bool
    previous_material_id: int | None = None
    next_material_id: int | None = None
    cluster_parallel: int | None = None
    cluster_sequential: int | None = None
    complexity_level: str | None = None
    estimated_time_hours: float | None = None


class ComplianceResult(BaseModel):
    material_id: int
    requirement_id: int
    is_compliant: bool
    details: str = ""


class ModerationResult(BaseModel):
    material_id: int
    overall_verdict: str
    compliant_count: int
    total_count: int
    results: list[ComplianceResult] = Field(default_factory=list)


class TrajectoryRequest(BaseModel):
    subject: str
    goal: str = ""
    available_hours: float = 0.0
    preferred_complexity: str = "medium"


class TrajectoryResponse(BaseModel):
    subject: str
    materials: list[MaterialResponse]
    total_hours: float
    description: str = ""


class ModelVersionInfo(BaseModel):
    model_name: str
    version: int
    file_path: str
    metrics: dict = Field(default_factory=dict)
    data_hash: str = ""


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


class ClusteringResult(BaseModel):
    strategy: str
    n_clusters: int
    labels: list[int]
    silhouette: float = 0.0
    calinski_harabasz: float = 0.0


class TimeEstimation(BaseModel):
    material_id: int
    estimated_hours: float
    confidence: float = 0.0
