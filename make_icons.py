"""أيقونة التطبيق للتثبيت على الشاشة الرئيسية: إطار عشرة فيه سبعة عدادات. لا خط ولا نص، فلا تحتاج خطًا عربيًا.

    python3 make_icons.py      # يكتب app/icons/icon-192.png و icon-512.png
"""
from PIL import Image, ImageDraw

def icon(size):
    s = size / 512
    im = Image.new('RGB', (size, size), (31, 78, 121))
    d = ImageDraw.Draw(im)
    x0, y0, cell = 56 * s, 156 * s, 80 * s
    d.rounded_rectangle([x0 - 12 * s, y0 - 12 * s, x0 + 5 * cell + 12 * s, y0 + 2 * cell + 12 * s], 24 * s, fill=(250, 246, 236))
    for r in range(2):
        for c in range(5):
            bx, by = x0 + c * cell, y0 + r * cell
            d.rectangle([bx, by, bx + cell, by + cell], outline=(31, 78, 121), width=max(2, round(6 * s)))
            if r * 5 + c < 7:
                m = 14 * s
                d.ellipse([bx + m, by + m, bx + cell - m, by + cell - m], fill=(232, 120, 40))
    return im

for n in (192, 512):
    icon(n).save(f'app/icons/icon-{n}.png', optimize=True)
