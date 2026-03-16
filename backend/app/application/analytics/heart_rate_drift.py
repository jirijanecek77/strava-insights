from decimal import Decimal, ROUND_HALF_UP


def calculate_heart_rate_drift_bpm(
    *,
    distance_stream_meters: list[float] | None,
    heartrate_stream_bpm: list[float] | None,
) -> Decimal | None:
    if not distance_stream_meters or not heartrate_stream_bpm:
        return None
    usable_length = min(len(distance_stream_meters), len(heartrate_stream_bpm))
    if usable_length < 4:
        return None

    distances = [float(value) for value in distance_stream_meters[:usable_length]]
    heart_rates = [float(value) for value in heartrate_stream_bpm[:usable_length]]
    total_distance = distances[-1]
    if total_distance <= 0:
        return None

    halfway_distance = total_distance / 2
    split_index = next((index for index, distance in enumerate(distances) if distance >= halfway_distance), None)
    if split_index is None or split_index <= 0 or split_index >= usable_length - 1:
        return None

    first_half = heart_rates[: split_index + 1]
    second_half = heart_rates[split_index + 1 :]
    if not first_half or not second_half:
        return None

    first_average = sum(first_half) / len(first_half)
    second_average = sum(second_half) / len(second_half)
    drift = Decimal(str(second_average - first_average))
    return drift.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
