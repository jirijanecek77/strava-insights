def which_race_button(button_id: str):
    if button_id == 'ten-k-button':
        distance, coefficient = 10, 0.85
    elif button_id == 'semi-button':
        distance, coefficient = 21.4125, 0.8
    elif button_id == 'full-button':
        distance, coefficient = 41.925, 0.75
    return distance, coefficient
