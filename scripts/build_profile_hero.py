from __future__ import annotations

from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
CAR_PATH = ASSETS / "polo-6c-gti-study.jpg"
README_PATH = ROOT / "README.md"

RED = "#E30613"
RED_SOFT = "#FF6B73"
CANVAS = "#06080B"
SURFACE = "#0D0F13"
PANEL = "#10141A"
BORDER = "#1C2026"
WHITE = "#FFFFFF"
TEXT = "#A7ADB7"
MUTED = "#6F7682"
FAINT = "#4F5661"

FONT_REG = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def rr(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def place_contain(dst: Image.Image, src: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    ratio = min(bw / src.width, bh / src.height)
    nw, nh = max(1, round(src.width * ratio)), max(1, round(src.height * ratio))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    x = x0 + (bw - nw) // 2
    y = y0 + (bh - nh) // 2
    dst.paste(resized, (x, y))
    return x, y, x + nw, y + nh


def make_car_mask(car: Image.Image) -> Image.Image:
    rgb = car.convert("RGB")
    gray = rgb.convert("L")
    # Preserve dark painted body while suppressing the near-black background.
    mask = gray.point(lambda p: max(0, min(255, (p - 8) * 11)))
    r, g, b = rgb.split()
    red_delta = ImageChops.subtract(r, g).point(lambda p: min(255, p * 6))
    mask = ImageChops.lighter(mask, red_delta)
    return mask.filter(ImageFilter.GaussianBlur(1.2))


def scan_frame(base: Image.Image, car_box, car_mask: Image.Image, progress: float) -> Image.Image:
    frame = base.copy()
    x0, y0, x1, y1 = car_box
    w, h = x1 - x0, y1 - y0

    scan_x = int(-60 + progress * (w + 120))
    strip_w = 78

    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = strip.load()
    center = scan_x
    for x in range(max(0, center - strip_w), min(w, center + strip_w)):
        d = abs(x - center) / strip_w
        if d >= 1:
            continue
        alpha = int((1 - d) ** 2 * 42)
        if abs(x - center) <= 1:
            color = (255, 255, 255, 145)
        elif abs(x - center) <= 5:
            color = (255, 107, 115, max(alpha, 58))
        else:
            color = (227, 6, 19, alpha)
        for y in range(h):
            px[x, y] = color

    fitted_mask = car_mask.resize((w, h), Image.Resampling.LANCZOS)
    strip.putalpha(ImageChops.multiply(strip.getchannel("A"), fitted_mask))
    frame.alpha_composite(strip, (x0, y0))
    return frame


def palette_frames(frames: list[Image.Image]) -> list[Image.Image]:
    # Stable shared palette keeps GIF size reasonable and avoids palette flicker.
    sample = frames[0].convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    out = []
    for frame in frames:
        out.append(frame.convert("RGB").quantize(palette=sample, dither=Image.Dither.FLOYDSTEINBERG))
    return out


def save_gif(base: Image.Image, car_box, car_mask: Image.Image, out: Path):
    idle = base.copy()
    progress = [0.02, 0.18, 0.34, 0.50, 0.66, 0.82, 0.98]
    frames = [idle] + [scan_frame(base, car_box, car_mask, p) for p in progress] + [idle]
    frames = palette_frames(frames)
    durations = [1700, 150, 150, 150, 150, 150, 150, 150, 2300]
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def desktop() -> None:
    img = Image.new("RGBA", (1200, 430), CANVAS)
    draw = ImageDraw.Draw(img)
    rr(draw, (0, 0, 1199, 429), 22, CANVAS, BORDER, 2)

    # top navigation
    rr(draw, (28, 22, 1172, 76), 12, SURFACE, BORDER, 1)
    rr(draw, (42, 35, 70, 63), 7, "#11151B", RED, 1)
    draw.line((48, 56, 54, 42, 58, 42, 64, 56), fill=RED, width=2)
    draw.text((82, 36), "VAGTechNL", font=font(FONT_BOLD, 19), fill=WHITE)
    draw.text((214, 42), "TECHNIEK · KENNIS · COMMUNITY", font=font(FONT_MONO, 10), fill=MUTED)

    nav = [("FORUM", 836), ("KENNISBANK", 910), ("CODEGARAGE", 1012), ("TOOLS", 1121)]
    for label, x in nav:
        draw.text((x, 42), label, font=font(FONT_BOLD, 10), fill=WHITE if label == "FORUM" else TEXT)
    draw.line((836, 73, 874, 73), fill=RED, width=2)

    # headline
    draw.line((52, 118, 78, 118), fill=RED, width=3)
    draw.text((90, 111), "TECHNICAL VAG PLATFORM", font=font(FONT_MONO, 11), fill=TEXT)
    draw.text((52, 146), "Engineering first.", font=font(FONT_BOLD, 42), fill=WHITE)
    draw.text((52, 193), "Evidence over assumptions.", font=font(FONT_BOLD, 42), fill=WHITE)
    draw.text((52, 259), "Forum-first community, durable knowledge and technical tooling.", font=font(FONT_REG, 16), fill=TEXT)
    draw.text((52, 287), "Volkswagen Group · diagnostics · coding · retrofits · software", font=font(FONT_REG, 12), fill=MUTED)

    chips = [("FORUM FIRST", 52, 100), ("EVIDENCE DRIVEN", 164, 122), ("UNKNOWN STAYS UNKNOWN", 298, 140)]
    for label, x, w in chips:
        rr(draw, (x, 339, x + w, 368), 7, "#11151B", "#252A32", 1)
        tw = draw.textlength(label, font=font(FONT_MONO, 9))
        draw.text((x + (w - tw) / 2, 349), label, font=font(FONT_MONO, 9), fill="#E6E8EB")

    draw.text((52, 400), "FOR DRIVERS | BY ENTHUSIASTS", font=font(FONT_MONO, 9), fill=FAINT)

    car = Image.open(CAR_PATH).convert("RGB")
    car_mask_src = make_car_mask(car)
    car_box = place_contain(img, car, (596, 138, 1186, 374))
    x0, y0, x1, y1 = car_box

    # bottom-right identifiers
    draw = ImageDraw.Draw(img)
    label = "POLO 6C GTI · APPROVED VISUAL"
    tw = draw.textlength(label, font=font(FONT_MONO, 8))
    draw.text((1156 - tw, 382), label, font=font(FONT_MONO, 8), fill=FAINT)
    label2 = "KNOWLEDGE DRIVES FURTHER"
    tw2 = draw.textlength(label2, font=font(FONT_MONO, 8))
    draw.text((1156 - tw2, 400), label2, font=font(FONT_MONO, 8), fill=FAINT)

    save_gif(img, car_box, car_mask_src, ASSETS / "header-v15.gif")


def mobile() -> None:
    img = Image.new("RGBA", (640, 650), CANVAS)
    draw = ImageDraw.Draw(img)
    rr(draw, (0, 0, 639, 649), 22, CANVAS, BORDER, 2)

    rr(draw, (22, 20, 618, 76), 11, SURFACE, BORDER, 1)
    rr(draw, (36, 34, 64, 62), 7, "#11151B", RED, 1)
    draw.line((42, 55, 48, 41, 52, 41, 58, 55), fill=RED, width=2)
    draw.text((76, 35), "VAGTechNL", font=font(FONT_BOLD, 19), fill=WHITE)
    draw.text((284, 43), "TECHNIEK · KENNIS · COMMUNITY", font=font(FONT_MONO, 8), fill=MUTED)

    draw.line((34, 112, 58, 112), fill=RED, width=3)
    draw.text((70, 105), "TECHNICAL VAG PLATFORM", font=font(FONT_MONO, 10), fill=TEXT)
    draw.text((34, 142), "Engineering first.", font=font(FONT_BOLD, 34), fill=WHITE)
    draw.text((34, 182), "Evidence over assumptions.", font=font(FONT_BOLD, 34), fill=WHITE)
    draw.text((34, 232), "Forum-first community, durable knowledge", font=font(FONT_REG, 14), fill=TEXT)
    draw.text((34, 253), "and technical tooling.", font=font(FONT_REG, 14), fill=TEXT)

    car = Image.open(CAR_PATH).convert("RGB")
    car_mask_src = make_car_mask(car)
    car_box = place_contain(img, car, (24, 292, 616, 528))

    draw = ImageDraw.Draw(img)
    draw.text((34, 566), "POLO 6C GTI · APPROVED VISUAL", font=font(FONT_MONO, 9), fill=MUTED)
    label = "VAGTECHNL"
    tw = draw.textlength(label, font=font(FONT_MONO, 9))
    draw.text((606 - tw, 566), label, font=font(FONT_MONO, 9), fill=RED)
    draw.line((34, 589, 606, 589), fill=BORDER, width=1)
    draw.text((34, 606), "FOR DRIVERS | BY ENTHUSIASTS", font=font(FONT_MONO, 8), fill=FAINT)
    label2 = "KNOWLEDGE DRIVES FURTHER"
    tw2 = draw.textlength(label2, font=font(FONT_MONO, 8))
    draw.text((606 - tw2, 606), label2, font=font(FONT_MONO, 8), fill=FAINT)

    save_gif(img, car_box, car_mask_src, ASSETS / "header-mobile-v15.gif")


def update_readme() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    start = text.index("<p align=\"center\">\n  <picture>")
    end = text.index("</p>", start) + len("</p>")
    hero = """<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="https://raw.githubusercontent.com/VAGTechNL/VAGTechNL/main/assets/header-mobile-v15.gif?v=15">
    <img src="https://raw.githubusercontent.com/VAGTechNL/VAGTechNL/main/assets/header-v15.gif?v=15" alt="VAGTechNL - premium technical automotive community, knowledge and tooling platform" width="100%" />
  </picture>
</p>"""
    text = text[:start] + hero + text[end:]
    README_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    desktop()
    mobile()
    update_readme()
