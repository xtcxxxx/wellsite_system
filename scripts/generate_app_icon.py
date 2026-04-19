"""生成 assets/app.ico。

优先使用 assets/app_icon_source.png：默认 **透明底** 居中缩放。
若资源管理器里 exe 显示成空白「应用程序」图标，可改回白底打包一次：
  $env:APP_ICON_BG="white"
可选环境变量（PowerShell）：
  $env:APP_ICON_BG="white"        # 不透明白底
  $env:APP_ICON_BG="gradient"     # 蓝绿渐变底（旧版剪影风）
  $env:APP_ICON_KNOCKOUT="1"      # 按亮度抠浅色像素（白底位图可与 transparent / gradient 搭配）

若无 app_icon_source.png，则使用内置矢量风图标。

需 Pillow：.venv\\Scripts\\pip install pillow
"""
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("请先安装 Pillow: .venv\\Scripts\\pip install pillow", file=sys.stderr)
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SOURCE_PNG = os.path.join(ASSETS, "app_icon_source.png")
os.makedirs(ASSETS, exist_ok=True)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _gradient_background(n: int) -> Image.Image:
    """深蓝 → 青蓝竖向渐变。"""
    top = (12, 42, 88, 255)
    bot = (26, 118, 168, 255)
    im = Image.new("RGBA", (n, n), top)
    px = im.load()
    last = max(n - 1, 1)
    for y in range(n):
        t = y / last
        row = (
            int(_lerp(top[0], bot[0], t)),
            int(_lerp(top[1], bot[1], t)),
            int(_lerp(top[2], bot[2], t)),
            255,
        )
        for x in range(n):
            px[x, y] = row
    return im


def _draw_rounded_rect(
    d: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    radius: float,
    fill,
    outline=None,
    width: int = 1,
) -> None:
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _knock_out_light_background(im: Image.Image, lum_thresh: float = 238.0) -> Image.Image:
    """将接近白/浅灰的背景变透明（剪影图常用）。"""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum >= lum_thresh:
                px[x, y] = (0, 0, 0, 0)
    return im


def build_icon_from_user_png(path: str, n: int = 512) -> Image.Image:
    src = Image.open(path).convert("RGBA")
    knock = os.environ.get("APP_ICON_KNOCKOUT", "").strip().lower()
    if knock in ("1", "true", "yes", "on"):
        src = _knock_out_light_background(src, lum_thresh=236.0)

    w, h = src.size
    margin = int(n * 0.08)
    max_w, max_h = n - 2 * margin, n - 2 * margin
    scale = min(max_w / max(w, 1), max_h / max(h, 1))
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    src = src.resize((nw, nh), Image.Resampling.LANCZOS)

    bg = os.environ.get("APP_ICON_BG", "transparent").strip().lower()
    if bg == "gradient":
        canvas = _gradient_background(n)
    elif bg in ("white", "solid"):
        canvas = Image.new("RGBA", (n, n), (255, 255, 255, 255))
    else:
        canvas = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    ox = (n - nw) // 2
    oy = (n - nh) // 2
    canvas.alpha_composite(src, (ox, oy))
    return canvas


def draw_builtin_icon(n: int = 512) -> Image.Image:
    """无用户图源时的默认图标（透明底）。"""
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = n * 0.5
    body_w, body_h = n * 0.52, n * 0.38
    body_x0 = cx - body_w / 2
    body_y0 = n * 0.34
    body_x1 = cx + body_w / 2
    body_y1 = body_y0 + body_h
    shadow_off = max(2, n // 128)
    _draw_rounded_rect(
        d,
        (
            body_x0 + shadow_off,
            body_y0 + shadow_off,
            body_x1 + shadow_off,
            body_y1 + shadow_off,
        ),
        radius=n * 0.06,
        fill=(0, 0, 0, 55),
    )
    _draw_rounded_rect(
        d,
        (body_x0, body_y0, body_x1, body_y1),
        radius=n * 0.06,
        fill=(248, 252, 255, 255),
        outline=(200, 220, 235, 255),
        width=max(1, n // 128),
    )
    lip_h = n * 0.07
    _draw_rounded_rect(
        d,
        (body_x0 - n * 0.02, body_y0 - lip_h * 0.85, body_x1 + n * 0.02, body_y0 + lip_h * 0.35),
        radius=n * 0.04,
        fill=(64, 158, 255, 255),
        outline=(36, 120, 200, 255),
        width=max(1, n // 160),
    )
    door_w = n * 0.2
    door_x0 = cx - door_w / 2
    door_y0 = body_y0 + body_h * 0.35
    door_x1 = cx + door_w / 2
    door_y1 = body_y1 - n * 0.05
    _draw_rounded_rect(
        d,
        (door_x0, door_y0, door_x1, door_y1),
        radius=n * 0.03,
        fill=(230, 242, 255, 255),
        outline=(90, 160, 220, 255),
        width=max(1, n // 200),
    )
    win_w, win_h = n * 0.11, n * 0.1
    wy = body_y0 + body_h * 0.22
    for sign in (-1, 1):
        wx0 = cx + sign * n * 0.17 - win_w / 2
        _draw_rounded_rect(
            d,
            (wx0, wy, wx0 + win_w, wy + win_h),
            radius=n * 0.02,
            fill=(210, 232, 255, 255),
            outline=(70, 140, 210, 200),
            width=1,
        )
    arr = n * 0.22
    ax0 = cx + n * 0.14
    ay0 = body_y1 - n * 0.02
    pts = [
        (ax0, ay0),
        (ax0 + arr * 0.75, ay0 - arr * 0.35),
        (ax0 + arr * 0.45, ay0 - arr * 0.35),
        (ax0 + arr * 0.45, ay0 - arr * 0.75),
        (ax0 - arr * 0.05, ay0 - arr * 0.75),
        (ax0 - arr * 0.05, ay0 - arr * 0.32),
        (ax0 - arr * 0.35, ay0 - arr * 0.32),
    ]
    d.polygon(pts, fill=(255, 193, 7, 255), outline=(200, 150, 0, 220))
    flat: list[float] = []
    for x, y in pts + [pts[0]]:
        flat.extend([x, y])
    d.line(flat, fill=(120, 80, 0, 120), width=max(1, n // 256))
    return im


def main() -> None:
    if os.path.isfile(SOURCE_PNG):
        base = build_icon_from_user_png(SOURCE_PNG, 512)
        bg = os.environ.get("APP_ICON_BG", "transparent")
        ko = os.environ.get("APP_ICON_KNOCKOUT", "0")
        src_note = f"from {SOURCE_PNG} (APP_ICON_BG={bg!r}, APP_ICON_KNOCKOUT={ko!r})"
    else:
        base = draw_builtin_icon(512)
        src_note = "builtin"

    ico_path = os.path.join(ASSETS, "app.ico")
    png_path = os.path.join(ASSETS, "app.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    # 使用 BMP 帧而非 PNG 帧，否则部分 Windows 外壳无法把 exe 图标显示出来（只显示空白“应用程序”图标）。
    base.save(ico_path, format="ICO", sizes=sizes, bitmap_format="bmp")
    base.resize((256, 256), Image.Resampling.LANCZOS).save(png_path, format="PNG")
    print("written:", ico_path, os.path.getsize(ico_path), "bytes", "|", src_note)


if __name__ == "__main__":
    main()
