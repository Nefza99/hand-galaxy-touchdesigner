import math
import random


def build(table=None, count=960, arms=6, turns=7.6, seed=7):
    """
    Fill a Table DAT with a richer spiral galaxy layout.

    Usage inside TouchDesigner:
        build(op('galaxy_instances'))
    """
    if table is None:
        table = op("galaxy_instances")

    rng = random.Random(seed)
    table.clear()
    table.appendRow(
        [
            "id",
            "tx",
            "ty",
            "tz",
            "pscale",
            "scale",
            "phase",
            "hue",
            "drift",
            "core",
            "spark",
            "ribbon",
            "dust",
        ]
    )

    for idx in range(int(count)):
        arm = idx % int(max(1, arms))
        arm_ratio = arm / float(max(1, arms))
        t = idx / float(max(1, count - 1))

        angle = t * math.tau * float(turns) + arm_ratio * math.tau
        radius = 0.03 + (t ** 0.72) * 0.5
        radius += rng.uniform(-0.02, 0.02)

        bend = math.sin(angle * 0.45 + t * 5.2) * 0.018
        x = math.cos(angle) * (radius + bend)
        y = math.sin(angle) * radius * 0.64
        z = rng.uniform(-0.14, 0.14) * (0.28 + t)

        core = max(0.0, 1.0 - t * 1.25)
        spark = rng.random() ** 1.6
        ribbon = (1.0 - abs(0.5 - arm_ratio) * 1.35) * (0.28 + spark * 0.72)
        dust = (rng.random() ** 1.2) * (0.35 + t * 0.65)
        point_scale = 0.14 + core * rng.uniform(0.65, 1.35) + spark * 0.18
        orbit_scale = 0.55 + rng.uniform(-0.2, 0.24) + core * 0.08
        phase = rng.random()
        hue = (arm_ratio + rng.uniform(-0.045, 0.045) + t * 0.04) % 1.0
        drift = 0.12 + rng.random() * 1.05

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
                round(core, 6),
                round(spark, 6),
                round(ribbon, 6),
                round(dust, 6),
            ]
        )

    return table
