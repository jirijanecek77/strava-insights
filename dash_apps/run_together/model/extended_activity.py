from dash_apps.run_together.model.strava_manager import StravaManager

from dash_apps.run_together.utils.conversion import calculate_pace
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec
from dash_apps.run_together.utils.conversion import moving_average
from dash_apps.run_together.utils.conversion import normalize_value

from dash_apps.run_together.utils.interval import get_bpm_pace_zone_intervals

from dash_apps.run_together.model.user import User


class ExtendedActivity:
    """
    Class to manage all the information for an activity
        - Name & relevant information from Activity Model of Strava Manager
        - Stream Data rom Activity Model of Strava Manager
        - Normalized & other data needed not available in the Strava Manager
    """
    def __init__(self, activity_id: int):
        # Get Data Available in the Strava Manager
        self.activity_id = activity_id
        self.strava_manager = StravaManager()
        self.activity = self.strava_manager.get_activity(
            activity_id=activity_id
        )
        self.user = User()
        # Extend the stream to have distance in km
        self.extended_stream = self.get_extended_stream()

        # Get an average to have a smoother visualisation
        # TODO Find the best fit for n depending on the number of points got by the user devise
        self.moving_average_heartrate = moving_average(
            data=self.extended_stream['heartrate']['data'],
            range_points=10
        )

        # Get The pace since we have only the distance and time
        self.range_points_pace = 20
        self.moving_average_pace = self.get_moving_average_pace(
            range_points=self.range_points_pace
        )
        self.intervals_moving_average_pace_zone = self.get_intervals_moving_average_pace_zone()

        # Get The normalize value based on the user setting
        self.normalized_moving_average_heartrate = [
            normalize_value(
                value=x,
                original_range=[x['bpm'] for x in self.user.pace_bpm_mapping.values()],
                target_range=list(range(len(self.user.pace_bpm_mapping.values())))
            )
            for x in self.moving_average_heartrate
        ]

        # Get The normalize value based on the user setting
        self.normalized_moving_average_pace = [
            normalize_value(
                value=x,
                original_range=[x['pace'] for x in self.user.pace_bpm_mapping.values()],
                target_range=list(range(len(self.user.pace_bpm_mapping.values())))
            )
            for x in self.moving_average_pace['minute_per_km']
        ]

    def get_extended_stream(self):

        extended_activity_stream = self.strava_manager.get_activity_stream(
            activity_id=self.activity_id
        )
        extended_activity_stream["distance_km"] = [
            x / 1000
            for x in extended_activity_stream["distance"]["data"]
        ]
        return extended_activity_stream

    def get_moving_average_pace(self, range_points: int) -> dict:
        """
        Calculate and add pace information to an activity stream.

        This function processes an activity stream to calculate the running pace in two formats:
        minutes per kilometer (MM.2f) and minutes:seconds per kilometer (MM:SS). It adds these
        calculated pace values to the activity stream dictionary.

        Parameters:
        activity_stream (dict): A dictionary containing activity data streams. Expected keys in the
                                dictionary include "distance" and "time", each with a nested "data"
                                key holding lists of distance (in meters) and time (in seconds)
                                values, respectively.
        range_points (int): The number of data points over which to calculate the moving average
                            pace. This helps in smoothing out the pace calculation.

        Returns:
            dict: The updated activity stream dictionary with additional "pace" key containing two new
              lists: "minute_per_km" and "minute_second_per_km".
        """
        # Get also the pace in both format (MM.2f use for the real y value and MM:SS for the better display)
        moving_average_pace = {
            'minute_per_km': calculate_pace(
                seconds=self.extended_stream['time']['data'][0:],
                distances=self.extended_stream['distance']['data'][0:],
                range_points=range_points,
            )
        }

        # Get the moving in the format MM:SS
        moving_average_pace['minute_second_per_km'] = [
            convert_min_to_min_sec(x)
            for x in moving_average_pace['minute_per_km']
        ]

        return moving_average_pace

    def get_intervals_moving_average_pace_zone(self):

        bpm_pace_zone_intervals = get_bpm_pace_zone_intervals(
            distance_km=self.extended_stream['distance_km'],
            paces=self.moving_average_pace['minute_per_km'],
            heart_rates=self.moving_average_heartrate,
            pace_bpm_mapping=self.user.get_pace_bpm_mapping()
        )
        return bpm_pace_zone_intervals
