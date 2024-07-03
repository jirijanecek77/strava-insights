class User:
    """
    Class to manage all the interaction with the setting of a user
        - Pace & Zone
        - Logging
        - Subscription
    """
    def __init__(self, ):
        self.age = 30
        self.bpm_max = 220 - 0.7 * self.age
        self.speed_max = 20
        self.pace_bpm_mapping = self.get_pace_bpm_mapping()

    def get_pace_bpm_mapping(self):
        return {
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

