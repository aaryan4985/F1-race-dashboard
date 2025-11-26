# File: main.py

from src.f1_data import get_race_telemetry, get_driver_colors, load_race_session
from src.arcade_replay import run_arcade_replay
import argparse


def main(year: int, round_number: int, playback_speed: float = 1.0) -> None:
    # Load the race session
    session = load_race_session(year, round_number)
    print(f"Loaded session: {session.event['EventName']} - Round {session.event['RoundNumber']} ({year})")

    # Get telemetry for the full race
    race_telemetry = get_race_telemetry(session)

    # Use the fastest lap as an example for the track layout
    example_lap = session.laps.pick_fastest().get_telemetry()

    # Get driver list and colors
    drivers = session.drivers
    driver_colors = get_driver_colors(session)

    # Run the arcade replay
    run_arcade_replay(
        frames=race_telemetry,
        example_lap=example_lap,
        drivers=drivers,
        playback_speed=playback_speed,
        driver_colors=driver_colors,
        title=f"{session.event['EventName']} - Race"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="F1 Race Replay")

    parser.add_argument(
        "--year",
        type=int,
        help="F1 season year (e.g. 2024). If omitted, you will be prompted."
    )
    parser.add_argument(
        "--round",
        type=int,
        help="Round number within the season (1 = first race). If omitted, you will be prompted."
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (default: 1.0)"
    )

    args = parser.parse_args()

    # Ask interactively if not provided in CLI
    if args.year is None:
        args.year = int(input("Enter F1 season year (e.g. 2024): "))

    if args.round is None:
        args.round = int(input("Enter race round (1 = first race of season): "))

    main(args.year, args.round, args.speed)
