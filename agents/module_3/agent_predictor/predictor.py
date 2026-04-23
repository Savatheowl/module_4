from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from shared import database as db  # noqa: E402
from shared.models import (  # noqa: E402
    TimeEstimation, TrajectoryRequest,
    TrajectoryResponse, MaterialResponse,
)
from agents.agent_dataset.dataset_builder import build_dataset  # noqa: E402


def estimate_time(material_id: int) -> TimeEstimation:
    m = db.get_material(material_id)
    if m is None:
        return TimeEstimation(material_id=material_id, estimated_hours=0.0, confidence=0.0)

    word_count = len(m["text_content"].split())
    media_count = len(m["media_descriptions"])

    reading_speed = 200
    base_hours = word_count / reading_speed / 60
    media_bonus = media_count * 0.1

    complexity = m.get("complexity_level", "")
    multiplier = 1.0
    if complexity == "продвинутый":
        multiplier = 1.5
    elif complexity == "начальный":
        multiplier = 0.7

    estimated = round((base_hours + media_bonus) * multiplier, 2)
    estimated = max(0.1, estimated)

    compliance = db.get_compliance_for_material(material_id)
    compliant = sum(1 for c in compliance if c["is_compliant"])
    total = len(compliance)
    confidence = round(compliant / total, 2) if total > 0 else 0.5

    db.update_material(material_id, estimated_time_hours=estimated)

    return TimeEstimation(
        material_id=material_id,
        estimated_hours=estimated,
        confidence=confidence,
    )


def estimate_all_times() -> list[TimeEstimation]:
    materials = db.get_all_materials()
    results = []
    for m in materials:
        results.append(estimate_time(m["id"]))
    return results


def visualize_time_estimates(save_path: str) -> str:
    df = build_dataset()
    if df.empty or "estimated_time_hours" not in df.columns:
        return ""

    valid = df[df["estimated_time_hours"].notna() & (df["estimated_time_hours"] > 0)]
    if valid.empty:
        return ""

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(
        valid["estimated_time_hours"], bins=15,
        color="#3498db", edgecolor="black", alpha=0.7,
    )
    axes[0].set_xlabel("Время (часы)")
    axes[0].set_ylabel("Количество")
    axes[0].set_title("Распределение времени освоения")

    by_subj = df.groupby("subject")["estimated_time_hours"].mean().dropna()
    if not by_subj.empty:
        by_subj.plot(kind="barh", ax=axes[1], color="#2ecc71")
        axes[1].set_xlabel("Среднее время (часы)")
        axes[1].set_title("Среднее время по дисциплинам")

    plt.tight_layout()
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def build_trajectory(request: TrajectoryRequest) -> TrajectoryResponse:
    all_materials = db.get_all_materials()
    subject_materials = [m for m in all_materials if m["subject"] == request.subject]

    if not subject_materials:
        return TrajectoryResponse(
            subject=request.subject,
            materials=[],
            total_hours=0.0,
            description=f"Нет материалов по дисциплине '{request.subject}'",
        )

    complexity_order = {"начальный": 0, "средний": 1, "продвинутый": 2}

    if request.preferred_complexity == "easy":
        target_levels = ["начальный", "средний"]
    elif request.preferred_complexity == "hard":
        target_levels = ["средний", "продвинутый"]
    else:
        target_levels = ["начальный", "средний", "продвинутый"]

    scored = []
    for m in subject_materials:
        level = m.get("complexity_level") or "средний"
        level_score = complexity_order.get(level, 1)
        time_h = m.get("estimated_time_hours") or 0.5
        scored.append((m, level, level_score, time_h))

    scored.sort(key=lambda x: (x[2], x[0]["id"]))

    selected = []
    total_hours = 0.0

    for m, level, _, time_h in scored:
        if level not in target_levels:
            continue
        if request.available_hours > 0 and total_hours + time_h > request.available_hours * 1.2:
            continue
        selected.append(m)
        total_hours += time_h

    mat_responses = []
    for m in selected:
        mat_responses.append(MaterialResponse(
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
            previous_material_id=m["previous_material_id"],
            next_material_id=m["next_material_id"],
            cluster_parallel=m["cluster_parallel"],
            cluster_sequential=m["cluster_sequential"],
            complexity_level=m["complexity_level"],
            estimated_time_hours=m["estimated_time_hours"],
        ))

    description = (
        f"Траектория по '{request.subject}': {len(selected)} материалов, "
        f"~{total_hours:.1f} ч. Уровни: {', '.join(target_levels)}."
    )

    return TrajectoryResponse(
        subject=request.subject,
        materials=mat_responses,
        total_hours=round(total_hours, 2),
        description=description,
    )


def visualize_trajectory(trajectory: TrajectoryResponse, save_path: str) -> str:
    if not trajectory.materials:
        return ""

    fig, ax = plt.subplots(figsize=(12, max(4, len(trajectory.materials) * 0.6)))

    topics = [f"{m.topic} ({m.complexity_level or '?'})" for m in trajectory.materials]
    hours = [m.estimated_time_hours or 0.5 for m in trajectory.materials]

    colors = []
    for m in trajectory.materials:
        cl = m.complexity_level or ""
        if cl == "начальный":
            colors.append("#2ecc71")
        elif cl == "продвинутый":
            colors.append("#e74c3c")
        else:
            colors.append("#3498db")

    y_pos = range(len(topics))
    ax.barh(y_pos, hours, color=colors, edgecolor="black", alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(topics)
    ax.set_xlabel("Время (часы)")
    ax.set_title(f"Траектория: {trajectory.subject} ({trajectory.total_hours:.1f} ч)")
    ax.invert_yaxis()

    plt.tight_layout()
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path
