export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const views = ["dashboard", "calendar", "activities", "best-efforts", "settings"];
export const adminStravaAthleteId = 102168741;
export const windows = [
    {id: "week", label: "Week"},
    {id: "month", label: "Month"},
    {id: "year", label: "Year"},
];
export const sports = [
    {id: "", label: "All Sports"},
    {id: "Run", label: "Run"},
    {id: "Ride", label: "Ride"},
    {id: "EBikeRide", label: "E-Bike"},
];
export const syncPollIntervalMs = 3000;
export const defaultLandingCredentialState = {
    client_id: "",
    has_saved_secret: false,
    can_connect: false,
    strava_api_settings_url: "https://www.strava.com/settings/api",
};
