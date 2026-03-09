from dataclasses import dataclass


ZONE_DEFINITIONS = (
    ("100m", 1.15, 1.00, "rgba(255, 69, 0, 0.3)"),
    ("5km", 0.90, 0.95, "rgba(255, 99, 71, 0.3)"),
    ("10km", 0.85, 0.90, "rgba(255, 140, 0, 0.3)"),
    ("Half-Marathon", 0.80, 0.85, "rgba(255, 165, 0, 0.3)"),
    ("Marathon", 0.75, 0.80, "rgba(255, 215, 0, 0.3)"),
    ("Active Jogging", 0.70, 0.75, "rgba(34, 139, 34, 0.3)"),
    ("Slow Jogging", 0.50, 0.60, "rgba(50, 205, 50, 0.3)"),
    ("Walk", None, 0.40, "rgba(144, 238, 144, 0.3)"),
)


@dataclass(slots=True)
class ZoneRange:
    lower: float
    upper: float


@dataclass(slots=True)
class RunningZone:
    name: str
    pace: float
    bpm: float
    color: str
    range_zone_pace: ZoneRange
    range_zone_bpm: ZoneRange


def bpm_max_for_age(age: int) -> float:
    return 220 - 0.7 * age


def build_running_zones(*, age: int, speed_max: float) -> list[RunningZone]:
    bpm_max = bpm_max_for_age(age)
    anchors: list[dict[str, float | str]] = []
    for zone_name, pace_factor, bpm_factor, color in ZONE_DEFINITIONS:
        pace = 60 / 4.8 if zone_name == "Walk" else 60 / (pace_factor * speed_max)
        anchors.append(
            {
                "name": zone_name,
                "pace": pace,
                "bpm": bpm_factor * bpm_max,
                "color": color,
            }
        )

    zones: list[RunningZone] = []
    paces = [float(anchor["pace"]) for anchor in anchors]
    bpms = [float(anchor["bpm"]) for anchor in anchors]
    for index, anchor in enumerate(anchors):
        if index == 0:
            pace_range = ZoneRange(0.0, (paces[index] + paces[index + 1]) / 2)
            bpm_range = ZoneRange((bpms[index] + bpms[index + 1]) / 2, float("inf"))
        elif index == len(anchors) - 1:
            pace_range = ZoneRange((paces[index] + paces[index - 1]) / 2, float("inf"))
            bpm_range = ZoneRange(0.0, (bpms[index] + bpms[index - 1]) / 2)
        else:
            pace_range = ZoneRange((paces[index] + paces[index - 1]) / 2, (paces[index] + paces[index + 1]) / 2)
            bpm_range = ZoneRange((bpms[index] + bpms[index + 1]) / 2, (bpms[index] + bpms[index - 1]) / 2)

        zones.append(
            RunningZone(
                name=str(anchor["name"]),
                pace=float(anchor["pace"]),
                bpm=float(anchor["bpm"]),
                color=str(anchor["color"]),
                range_zone_pace=pace_range,
                range_zone_bpm=bpm_range,
            )
        )
    return zones


def resolve_running_zone(zones: list[RunningZone], *, pace: float, heart_rate: float) -> dict[str, str]:
    zone_pace = "Unknown"
    zone_heart_rate = "Unknown"
    for zone in zones:
        if zone.range_zone_pace.lower <= pace < zone.range_zone_pace.upper:
            zone_pace = zone.name
        if zone.range_zone_bpm.lower <= heart_rate < zone.range_zone_bpm.upper:
            zone_heart_rate = zone.name
    return {"zone_pace": zone_pace, "zone_heart_rate": zone_heart_rate}
