import math
import random


def build(table=None, count=840, arms=5, turns=7.0, seed=7):
    """
    Fill a Table DAT with a stylized spiral galaxy layout.

    Usage inside TouchDesigner:
        build(op('galaxy_instances'))
    """
    if table is None:
        table = op("galaxy_instances")

    rng = random.Random(seed)
    table.clear()
    table.appendRow(["id", "tx", "ty", "tz", "pscale", "scale", "phase", "hue", "drift"])

    for idx in range(int(count)):
        arm = idx % int(max(1, arms))
        arm_ratio = arm / float(max(1, arms))
        t = idx / float(max(1, count - 1))

        angle = t * math.tau * float(turns) + arm_ratio * math.tau
        radius = 0.03 + (t ** 0.72) * 0.48
        radius += rng.uniform(-0.018, 0.018)

        x = math.cos(angle) * radius
        y = math.sin(angle) * radius * 0.62
        z = rng.uniform(-0.12, 0.12) * (0.35 + t)

        point_scale = 0.18 + (1.0 - t) * rng.uniform(0.7, 1.35)
        orbit_scale = 0.55 + rng.uniform(-0.18, 0.22)
        phase = rng.random()
        hue = (arm_ratio + rng.uniform(-0.03, 0.03)) % 1.0
        drift = 0.15 + rng.random() * 0.95

        table.appendRow(
            [
                idx,
                round(x, 6),
                round(y, 6),
                round(z, 6),
                round(point_scale, 6),
                round(orbit_scale, 6),
                round(phase, 6),
                round(hue, 6),
                round(drift, 6),
            ]
        )

    return table
