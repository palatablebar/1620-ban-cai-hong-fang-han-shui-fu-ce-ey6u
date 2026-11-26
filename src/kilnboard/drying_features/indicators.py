from math import log1p, sqrt


def derive(values: tuple[float, ...]) -> tuple[float, ...]:
    """从烘房层位单原始读数生成五个模型轴。"""
    thickness, hours, steam, inlet, level, vent = values
    saturation = thickness * inlet / (1 + hours / 24)
    residence = hours / thickness
    penetration = steam * sqrt(hours) / sqrt(thickness)
    shadow = level ** 1.3 * thickness / (1 + vent / 100)
    vent_effect = vent * log1p(hours) / (1 + level / 12)
    return saturation, residence, penetration, shadow, vent_effect
