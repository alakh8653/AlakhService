"""Draws the AlakhService brand mark (a white "A" on the primary colour) into assets/branding/.

Run from apps/mobile_app with `python3 tool/make_brand_assets.py` (needs Pillow), then
`dart run flutter_launcher_icons` and `dart run flutter_native_splash:create` (see pubspec.yaml).
"""
from pathlib import Path

from PIL import Image, ImageDraw

PRIMARY = (0x5B, 0x52, 0xF0, 255)  # AppColors.primary
WHITE = (255, 255, 255, 255)
OUT = Path(__file__).resolve().parent.parent / "assets" / "branding"
SS = 4  # supersampling for smooth edges


def draw_a(draw: ImageDraw.ImageDraw, cx: float, cy: float, h: float, colour) -> None:
    """A geometric "A": two legs meeting in a flat apex, and a crossbar."""
    w = h * 0.86          # overall width at the base
    stroke = h * 0.20     # leg thickness
    top_w = h * 0.22      # width of the flat apex
    top, base = cy - h / 2, cy + h / 2
    left, right = cx - w / 2, cx + w / 2
    # Outer outline of the A, then the triangular counter cut out of it.
    outer = [(cx - top_w / 2, top), (cx + top_w / 2, top), (right, base), (right - stroke * 1.15, base),
             (cx, top + stroke * 1.2), (left + stroke * 1.15, base), (left, base)]
    draw.polygon(outer, fill=colour)
    # Crossbar between the inner edges of the legs.
    bar_top, bar_h = cy + h * 0.08, h * 0.15

    def inner_x(y: float, side: int) -> float:
        # Inner edge of a leg runs from the inner apex (cx, top + 1.2*stroke) to the inner base corner.
        y0, y1 = top + stroke * 1.2, base
        x1 = (right - stroke * 1.15) if side > 0 else (left + stroke * 1.15)
        t = (y - y0) / (y1 - y0)
        return cx + (x1 - cx) * t

    draw.polygon([(inner_x(bar_top, -1) - 2, bar_top), (inner_x(bar_top, 1) + 2, bar_top),
                  (inner_x(bar_top + bar_h, 1) + 2, bar_top + bar_h), (inner_x(bar_top + bar_h, -1) - 2, bar_top + bar_h)],
                 fill=colour)


def render(size: int, background, mark_height: float, rounded: float = 0.0) -> Image.Image:
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if background is not None:
        if rounded:
            d.rounded_rectangle([0, 0, big - 1, big - 1], radius=big * rounded, fill=background)
        else:
            d.rectangle([0, 0, big, big], fill=background)
    draw_a(d, big / 2, big / 2 + big * 0.01, big * mark_height, WHITE)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Full icon (iOS, legacy Android): mark on a solid square (the OS applies its own mask).
    render(1024, PRIMARY, 0.54).save(OUT / "app_icon.png")
    # Android adaptive foreground: the mark inside the 66% safe zone, on transparent.
    render(1024, None, 0.36).save(OUT / "app_icon_foreground.png")
    # Splash mark: white on transparent, shown on the primary colour.
    render(768, None, 0.5).save(OUT / "splash_mark.png")


if __name__ == "__main__":
    main()
