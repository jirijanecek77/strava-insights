export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const views = ["dashboard", "calendar", "activities", "best-efforts", "settings"];
export const adminExternalUserId = String(import.meta.env.VITE_ADMIN_EXTERNAL_USER_ID ?? "68c0e5b9-3370-4e83-904b-de6edcf24551");
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
    external_user_id: "",
    has_saved_secret: false,
    can_connect: false,
    provider: "garmin",
};
