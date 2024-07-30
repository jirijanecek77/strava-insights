from typing import List


def speed_to_pace(speed_mps):
    """
    Convert speed from meters per second (m/s) to minutes per kilometer (min/km).

    Parameters:
    speed_mps (float): Speed in meters per second.

    Returns:
    float: Speed in minutes per kilometer.
    """
    if speed_mps <= 0:
        raise ValueError("Speed must be a positive value.")

    # Convert speed from m/s to km/s
    speed_kps = speed_mps / 1000.0

    # Convert km/s to s/km
    time_per_km_s = 1 / speed_kps

    # Convert seconds per kilometer to minutes per kilometer
    time_per_km_min = time_per_km_s / 60.0

    return time_per_km_min


def normalize_value(value: float, original_range: List[float], target_range: List[float]):
    """
     Normalize a value based on a given original range and a target range using linear interpolation.

     This function takes an input value and maps it from its original range to a target range.
     The function handles cases where the original range values can be either increasing or decreasing.


     Parameters:
     value (float): The value to be normalized.
     original_range (list of float): A list of values representing the original range.
     target_range (list of float): A list of values representing the target range.

     Returns:
        float: The normalized value mapped from the original range to the target range.
    """
    # Example usage:
    # original_range = [190.0, 180.0, 170.0, 160.0, 150.0, 130.0]
    # target_range = [5, 4, 3, 2, 1, 0]
    # normalize_value(140, original_range, target_range) will return 0.5

    # Sort original and target ranges in ascending order
    sorted_pairs = sorted(zip(original_range, target_range))
    sorted_original = [pair[0] for pair in sorted_pairs]
    sorted_target = [pair[1] for pair in sorted_pairs]

    # Handle case where value is below the minimum of the original range
    if value <= sorted_original[0]:
        return sorted_target[0]
    # Handle case where value is above the maximum of the original range
    if value >= sorted_original[-1]:
        return sorted_target[-1]

    # Iterate through the sorted original range to find the correct interval
    for i in range(1, len(sorted_original)):
        if value <= sorted_original[i]:
            x0, x1 = sorted_original[i - 1], sorted_original[i]
            y0, y1 = sorted_target[i - 1], sorted_target[i]

            # Linear interpolation formula
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)

    # Return None if value does not fall within the original range (should not reach here)
    return None


def convert_min_to_min_sec(minutes: float):
    """
    Convert a float value in minutes to a string in "M:S" format with minutes and seconds.

    Parameters:
    - minutes (float): Time in minutes.

    Returns:
    - str: Time in "M:S" format.
    """
    # Separate the integer part (minutes) from the fractional part (seconds)
    int_minutes = int(minutes)
    secs = (minutes - int_minutes) * 60
    return f"{int_minutes}:{int(secs):02d}"


def convert_min_sec_to_min(time_str: str) -> float:
    """
    Convert a string in "M:S" format with minutes and seconds to a float value in minutes.

    Parameters:
    - time_str (str): Time in "M:S" format.

    Returns:
    - float: Time in minutes.
    """
    # Split the string into minutes and seconds
    minutes, seconds = map(int, time_str.split(':'))

    # Convert the time to minutes
    total_minutes = minutes + seconds / 60

    return total_minutes


def calculate_pace(seconds: List[int], distances: List[float], range_points: int) -> List[float]:
    """
    Calculate the speed in minutes per kilometer (min/km) for an athlete's run.

    Parameters:
    - seconds (list of int): List of time points in seconds.
    - distances (list of float): List of distances corresponding to each time point in meters.
    - range_points (int): Number of points before and after to consider for pace calculation.

    Returns:
    - list of float: Speeds in min/km for the given points. it provides a float time minute  and not MM:SS
    """
    # Initialize list to hold the speeds
    paces = []

    # Calculate speed for each point considering range_points
    for i in range(len(seconds)):
        start_index = max(0, i - range_points)
        end_index = min(len(seconds) - 1, i + range_points)

        # TIme and distance from the point i + N and j + N
        total_time = seconds[end_index] - seconds[start_index]
        total_distance = distances[end_index] - distances[start_index]

        if total_distance == 0:
            paces.append(float('inf'))
        else:
            # Convert meters to kilometers and seconds to minutes
            total_time_min = total_time / 60
            total_distance_km = total_distance / 1000
            # Calculation of the pace
            speed_min_per_km = total_time_min / total_distance_km

            # Minimum to 16 min / km to avoid weird value)
            paces.append(min(16, speed_min_per_km))

    return paces


def moving_average(data: List[float], range_points: int):
    """
    Calculate the moving average for each point in the data using N elements before and after.

    Args:
    - data: list of numerical values
    - n: int, number of elements before and after each point to include in the average

    Returns:
    - averages: list of calculated averages
    """
    if not data or range_points <= 0:
        return []

    length = len(data)
    averages = []

    for i in range(length):
        start = max(0, i - range_points)
        end = min(length, i + range_points + 1)
        window = data[start:end]
        avg = sum(window) / len(window)
        averages.append(avg)

    return averages
