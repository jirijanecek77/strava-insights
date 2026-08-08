export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const views = ["dashboard", "calendar", "activities", "best-efforts", "settings"];
export const adminAthleteId = Number(import.meta.env.VITE_ADMIN_ATHLETE_ID ?? 632291);
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
export const syncPollIntervalMs = 60*1000;
export const defaultLandingCredentialState = {
    athlete_id: "",
    has_saved_secret: false,
    can_connect: false,
    intervals_settings_url: "https://intervals.icu/settings",
};
