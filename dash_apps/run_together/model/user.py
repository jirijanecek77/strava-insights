from flask import session
from dash_apps.run_together.utils.conversion import calculate_age


class User:
    """
    Class to manage all the interaction with the setting of a user
        - Pace & Zone
        - Logging
        - Subscription
    """
    def __init__(self, ):
        self.age = calculate_age(session["run_together_user"]["birthday"])
        self.bpm_max = 220 - 0.7 * self.age
        self.speed_max = session["run_together_user"]["speed_max"]
        self.pace_bpm_mapping = self.get_pace_bpm_mapping()

    def get_pace_bpm_mapping(self):
        bpm_pace_mapping = {
            "100m": {
                "pace": 60 / (1.15 * self.speed_max),
                "bpm": self.bpm_max,
                "color": "rgba(255, 69, 0, 0.3)"  # Dark red
            },
            "5km": {
                "pace": 60 / (0.90 * self.speed_max),
                "bpm": 0.95 * self.bpm_max,
                "color": "rgba(255, 99, 71, 0.3)"  # Light red
            },
            "10km": {
                "pace": 60 / (0.85 * self.speed_max),
                "bpm": 0.90 * self.bpm_max,
                "color": 'rgba(255, 140, 0, 0.3)'  # Dark orange

            },
            "Half-Marathon": {
                "pace": 60 / (0.80 * self.speed_max),
                "bpm": 0.85 * self.bpm_max,
                "color": 'rgba(255, 165, 0, 0.3)'  # Medium orange
            },
            "Marathon": {
                "pace": 60 / (0.75 * self.speed_max),
                "bpm":  0.80 * self.bpm_max,
                "color": 'rgba(255, 215, 0, 0.3)'  # Light yellow
            },
            "Active Jogging": {
                "pace": 60 / (0.70 * self.speed_max),
                "bpm": 0.75 * self.bpm_max,
                "color": 'rgba(34, 139, 34, 0.3)'  # Dark green
            },
            "Slow Jogging": {
                "pace": 60 / (0.50 * self.speed_max),
                "bpm": 0.60 * self.bpm_max,
                "color": 'rgba(50, 205, 50, 0.3)'  # Medium green
            },
            "Walk": {
                "pace": 60 / 4.8, # Marche is not depending on speed max
                "bpm": 0.40 * self.bpm_max,
                "color": 'rgba(144, 238, 144, 0.3)'  # Light green
            },
        }

        # Extract the paces & BPM
        paces = [value['pace'] for value in bpm_pace_mapping.values()]
        bpm = [value['bpm'] for value in bpm_pace_mapping.values()]

        # Create the zone
        i = 0
        for zone, value in bpm_pace_mapping.items():
            if i == 0:
                bpm_pace_mapping[zone]['range_zone_pace'] = (0, (paces[i] + paces[i + 1]) / 2)
                bpm_pace_mapping[zone]['range_zone_bpm'] = ((bpm[i] + bpm[i + 1]) / 2, float('inf'))

            elif i == len(paces) - 1:
                bpm_pace_mapping[zone]['range_zone_pace'] = ((paces[i] + paces[i - 1]) / 2, float('inf'))
                bpm_pace_mapping[zone]['range_zone_bpm'] = (0, (bpm[i] + bpm[i - 1]) / 2)

            else:
                bpm_pace_mapping[zone]['range_zone_pace'] = ((paces[i] + paces[i - 1]) / 2, (paces[i] + paces[i + 1]) / 2)
                bpm_pace_mapping[zone]['range_zone_bpm'] = ((bpm[i] + bpm[i + 1]) / 2, (bpm[i] + bpm[i - 1]) / 2)

            i = i + 1

        return bpm_pace_mapping
