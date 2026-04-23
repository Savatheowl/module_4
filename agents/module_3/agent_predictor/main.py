import argparse

from shared.config import get_config
from shared import database as db
from shared.models import TrajectoryRequest
from agents.agent_predictor.predictor import (
    estimate_time,
    estimate_all_times,
    visualize_time_estimates,
    build_trajectory,
    visualize_trajectory,
)


def main():
    parser = argparse.ArgumentParser(description="Агент предсказаний и траекторий")
    sub = parser.add_subparsers(dest="command")

    time_p = sub.add_parser("estimate-time", help="Оценить время для материала")
    time_p.add_argument("--material-id", type=int, default=0)
    time_p.add_argument("--all", action="store_true")

    traj_p = sub.add_parser("trajectory", help="Построить траекторию")
    traj_p.add_argument("--subject", required=True)
    traj_p.add_argument("--hours", type=float, default=0)
    traj_p.add_argument("--complexity", choices=["easy", "medium", "hard"], default="medium")

    args = parser.parse_args()

    cfg = get_config()
    db.init_db(cfg.database.abs_path)

    if args.command == "estimate-time":
        if args.all:
            results = estimate_all_times()
            for r in results:
                print(f"Material {r.material_id}: {r.estimated_hours}h (conf={r.confidence})")
            reports = str(cfg.database.abs_path).replace(
                "data/saransk.sqlite", "reports/time_estimates.png"
            )
            path = visualize_time_estimates(reports)
            if path:
                print(f"Визуализация: {path}")
        elif args.material_id > 0:
            r = estimate_time(args.material_id)
            print(f"Material {r.material_id}: {r.estimated_hours}h (conf={r.confidence})")
        else:
            print("Укажите --material-id или --all")

    elif args.command == "trajectory":
        request = TrajectoryRequest(
            subject=args.subject,
            available_hours=args.hours,
            preferred_complexity=args.complexity,
        )
        traj = build_trajectory(request)
        print(traj.description)
        for m in traj.materials:
            print(f"  [{m.complexity_level}] {m.topic}: {m.estimated_time_hours}h")
        reports = str(cfg.database.abs_path).replace(
            "data/saransk.sqlite", "reports/trajectory.png"
        )
        path = visualize_trajectory(traj, reports)
        if path:
            print(f"Визуализация: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
