from typing import List, Tuple, Union
from statistics import mean

from typing import List, Dict


test = {
    'Marathon': {
            'average_heart_rate': 0,
            'average_pace': 0,
            'total_distance': 0,
            'intervals': [],
            'Marathon': {
                'average_heart_rate': 0,
                'average_pace': 0,
                'total_distance': 0,
                'intervals': [],

            },
            'Half-Marathon': {
                'average_heart_rate': 0,
                'average_pace': 0,
                'total_distance': 0,
                'intervals': [],

            }
    }
}



def get_kpi_interval(intervals: List[Dict[str, List[float]]]) -> Tuple[float, float, float]:
    """
    Combine the list of intervals and return the average heart_rate, average pace, and total distance.

    Parameters:
    - intervals: List of dictionaries, each containing:
        - 'distance_km': List of distances within the interval.
        - 'pace': List of paces within the interval.
        - 'heart_rate': List of heart_rate values within the interval.

    Returns:
    - A tuple containing:
        - Average heart_rate for all intervals combined.
        - Average pace for all intervals combined (formatted as 'MM:SS').
        - Total distance of all intervals combined.
    """
    total_distance = 0
    pace = []
    heart_rate = []

    for interval in intervals:
        total_distance += max(interval['distance_km']) - min(interval['distance_km'])
        pace += interval['pace']
        heart_rate += interval['heart_rate']

    average_pace = mean(pace) if len(pace) > 0 else 0
    average_heart_rate = mean(heart_rate) if len(pace) > 0 else 0

    return average_heart_rate, average_pace, total_distance


def extract_intervals(distance_km: List[float], pace: List[float], heart_rate: List[int], lower_bound: float, upper_bound: float) -> List[Dict[str, List[float]]]:
    """
    Extract intervals where the pace falls within a specified range.

    This function identifies continuous intervals in the provided distance, pace, and heart_rate lists where the pace is consistently within a specified range (between `lower_bound` and `upper_bound`). It returns a list of intervals, each containing the distances, paces, and heart rate values for that interval.

    Parameters:
    - distance_km (List[float]): A list of distances in kilometers.
    - pace (List[float]): A list of pace values corresponding to each distance point.
    - heart_rate (List[int]): A list of heart_rate values corresponding to each distance point.
    - lower_bound (float): The lower bound of the pace range to identify intervals.
    - upper_bound (float): The upper bound of the pace range to identify intervals.

    Returns:
    - List[Dict[str, List[float]]]: A list of dictionaries where each dictionary represents an interval and contains:
        - 'distance_km' (List[float]): The list of distances within the interval.
        - 'pace' (List[float]): The list of paces within the interval.
        - 'heart_rate' (List[int]): The list of heart_rate values within the interval.
    """
    intervals = []
    interval = {}
    start_interval = False

    for i in range(len(pace)):

        if lower_bound <= pace[i] < upper_bound:
            # If interval didn't start, initiate it and change value for start
            if not start_interval:
                start_interval = True
                interval = {
                    'distance_km': [],
                    'pace': [],
                    'heart_rate': [],
                }

            # Add the value (if start was already True or not)
            interval['distance_km'].append(distance_km[i])
            interval['pace'].append(pace[i])
            interval['heart_rate'].append(heart_rate[i])

        # If condition is not met anymore, set start to False and add the interval
        else:
            if start_interval:
                intervals.append(interval)
                start_interval = False

    # In case the interval was still open at the end
    if start_interval:
        intervals.append(interval)

    return intervals


def get_zone_pace_bpm(pace_bpm_mapping: Dict[str, Dict[str, Tuple[float, float]]], pace: float, heart_rate: float) -> Dict[str, str]:
    """
    Determine the zones for a given pace and heart_rate based on the provided pace_bpm_mapping.

    Args:
        pace_bpm_mapping (Dict[str, Dict[str, float]]): A dictionary where each key is a zone name and the value is another dictionary
            containing 'pace', 'heart_rate', 'color', and 'range_zone_pace' (tuple with lower and upper bounds for pace)
            and 'range_zone_bpm' (tuple with lower and upper bounds for heart_rate).
        pace (float): The pace value to be mapped to a zone.
        heart_rate (float): The heart_rate value to be mapped to a zone.

    Returns:
        Dict[str, str]: A dictionary with 'zone_pace' and 'zone_bpm' keys corresponding to the zone names for the given pace and heart_rate
        .
            If the pace or heart_rate does not match any zone, 'Unknown' is returned for that value.
    """
    zone_pace = "Unknown"
    zone_heart_rate = "Unknown"

    for zone_name, data in pace_bpm_mapping.items():
        pace_lower_bound, pace_upper_bound = data['range_zone_pace']
        heart_rate_lower_bound, heart_rate_upper_bound = data['range_zone_bpm']

        if pace_lower_bound <= pace < pace_upper_bound:
            zone_pace = zone_name

        if heart_rate_lower_bound <= heart_rate < heart_rate_upper_bound:
            zone_heart_rate = zone_name

    return {"zone_pace": zone_pace, "zone_heart_rate": zone_heart_rate}


def get_bpm_pace_zone_intervals(
        distance_km: List[float],
        paces: List[float],
        heart_rates: List[int],
        pace_bpm_mapping: Dict[str, Dict[str, Tuple[float, float]]]
) -> List[Dict[str, List[float]]]:
    """
    Extract intervals where the pace falls within a specified range.

    This function identifies continuous intervals in the provided distance, pace, and heart_rate lists where the pace is consistently within a specified range (between `lower_bound` and `upper_bound`). It returns a list of intervals, each containing the distances, paces, and heart rate values for that interval.

    Parameters:
    - distance_km (List[float]): A list of distances in kilometers.
    - paces (List[float]): A list of pace values corresponding to each distance point.
    - heart_rates (List[int]): A list of heart_rates values corresponding to each distance point.
    - pace_bpm_mapping (Dict[str, Tuple[float, float]]): A dictionary mapping zones to (pace_lower_bound, pace_upper_bound).

    Returns:
    - List[Dict[str, List[float]]]: A list of dictionaries where each dictionary represents an interval and contains:
        - 'distance_km' (List[float]): The list of distances within the interval.
        - 'pace' (List[float]): The list of paces within the interval.
        - 'heart_rate' (List[int]): The list of heart_rate values within the interval.
    """

    intervals=[{
        'distance_km': [distance_km[0]],
        'pace': [paces[0]],
        'heart_rate': [heart_rates[0]],
        'zones': get_zone_pace_bpm(pace_bpm_mapping=pace_bpm_mapping, pace=paces[0], heart_rate=heart_rates[0])
    }]

    # Init first Interval

    # Loop to each pace append to the interval.
    for i in range(1, len(paces)):
        pace = paces[i]
        heart_rate = heart_rates[i]

        zones = get_zone_pace_bpm(pace_bpm_mapping=pace_bpm_mapping, pace=pace, heart_rate=heart_rate)

        # If the zone is still the same (Pace & BPM)  - We add to the last interval
        if intervals[len(intervals) - 1]["zones"] == zones:
            intervals[len(intervals) - 1]['distance_km'].append(distance_km[i])
            intervals[len(intervals) - 1]['pace'].append(pace)
            intervals[len(intervals) - 1]['heart_rate'].append(heart_rate)

        # In the other case we set up a new interval
        else:
            intervals.append({
                'distance_km': [distance_km[i]],
                'pace': [pace],
                'heart_rate': [heart_rate],
                'zones': zones
            })

    return intervals


