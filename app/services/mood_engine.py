def get_tamagotchi_mood(health_score: int) -> str:
    if health_score > 80:
        return "thriving"
    if health_score > 60:
        return "content"
    if health_score > 40:
        return "worried"
    if health_score > 20:
        return "stressed"
    return "exhausted"
