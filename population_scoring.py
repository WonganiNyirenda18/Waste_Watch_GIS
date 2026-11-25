
def calculate_population_score(
    density,
    preferred_max=500,
    unsuitable_min=5000
):
    """
    Converts population density into a suitability score
    between 0 and 100.

    Lower population density receives a higher score.
    """

    if preferred_max < 0 or unsuitable_min <= preferred_max:
        raise ValueError("Invalid population thresholds.")

    if density < 0:
        raise ValueError("Population density cannot be negative.")

    if density <= preferred_max:
        return 100.0

    if density >= unsuitable_min:
        return 0.0

    score = (
        (unsuitable_min - density) /
        (unsuitable_min - preferred_max)
    ) * 100

    return round(score, 2)


# Test the scoring function
test_values = [100, 500, 1000, 2000, 3000, 4000, 5000]

for value in test_values:
    score = calculate_population_score(value)
    print(f"{value} people/km² = {score} suitability points")
