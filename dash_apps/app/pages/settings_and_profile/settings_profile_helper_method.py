def which_race_button(button_id: str) -> tuple[float, float]:
    if button_id == "ten-k-button":
        return 10, 0.85
    elif button_id == "semi-button":
        return 21.4125, 0.8
    return 41.925, 0.75


def which_race_distance(button_id: str) -> str:
    if button_id == "ten-k-button":
        return "10 kilometer"
    elif button_id == "semi-button":
        return "Semi-marathon"
    return "Marathon"
