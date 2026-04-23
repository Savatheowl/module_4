import pandas as pd

from shared import database as db


def build_dataset() -> pd.DataFrame:
    materials = db.get_all_materials()
    if not materials:
        return pd.DataFrame()

    rows = []
    for m in materials:
        compliance = db.get_compliance_for_material(m["id"])
        compliant = sum(1 for c in compliance if c["is_compliant"])
        total = len(compliance)

        row = {
            "id": m["id"],
            "subject": m["subject"],
            "topic": m["topic"],
            "text_length": len(m["text_content"]),
            "word_count": len(m["text_content"].split()),
            "annotation_length": len(m["annotation"]),
            "moderation_verdict": m["moderation_verdict"],
            "file_type": m["file_type"],
            "media_count": len(m["media_descriptions"]),
            "class_type": m["class_type"],
            "is_generated": int(m["is_generated"]),
            "has_previous": int(m["has_previous"]),
            "has_next": int(m["has_next"]),
            "compliance_ratio": compliant / total if total > 0 else 0.0,
            "compliant_count": compliant,
            "total_requirements": total,
            "cluster_parallel": m["cluster_parallel"],
            "cluster_sequential": m["cluster_sequential"],
            "complexity_level": m["complexity_level"],
            "estimated_time_hours": m["estimated_time_hours"],
        }
        rows.append(row)

    return pd.DataFrame(rows)


def save_dataset(df: pd.DataFrame, path: str) -> str:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding="utf-8")
    return str(p)


def load_dataset(path: str) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8")
