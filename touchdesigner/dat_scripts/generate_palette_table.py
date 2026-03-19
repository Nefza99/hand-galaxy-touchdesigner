import colorsys


PALETTES = [
    ("Arctic Ice", [(0.57, 0.32, 0.22), (0.55, 0.54, 0.78), (0.50, 0.16, 1.00)]),
    ("Plasma Orchid", [(0.77, 0.42, 0.24), (0.83, 0.76, 0.86), (0.90, 0.32, 1.00)]),
    ("Aurora Mint", [(0.34, 0.46, 0.22), (0.41, 0.78, 0.88), (0.49, 0.28, 1.00)]),
    ("Solar Flare", [(0.06, 0.74, 0.24), (0.12, 0.92, 0.96), (0.17, 0.34, 1.00)]),
    ("Toxic Neon", [(0.25, 0.86, 0.24), (0.31, 1.00, 0.96), (0.37, 0.38, 1.00)]),
    ("Sunset Ember", [(0.95, 0.58, 0.26), (0.02, 0.88, 0.92), (0.08, 0.46, 1.00)]),
]


def build(table=None):
    """
    Fill a Table DAT with six high-contrast palette families.

    Usage inside TouchDesigner:
        build(op('galaxy_palettes'))
    """
    if table is None:
        table = op("galaxy_palettes")

    table.clear()
    table.appendRow(["palette_id", "palette_name", "stop", "h", "s", "v", "r", "g", "b"])

    for palette_id, (palette_name, stops) in enumerate(PALETTES):
        for stop, (hue, saturation, value) in enumerate(stops):
            red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
            table.appendRow(
                [
                    palette_id,
                    palette_name,
                    stop,
                    round(hue, 6),
                    round(saturation, 6),
                    round(value, 6),
                    round(red, 6),
                    round(green, 6),
                    round(blue, 6),
                ]
            )

    return table
