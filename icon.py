# icon.py  -- creates a dictionary-style .ico file (works with modern Pillow)
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os

out_path = "dictionary_icon.ico"   # writes to current working directory
size = 256

# Create base image
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Colors
bg_color = (30, 144, 255, 255)        # blue background
cover_color = (255, 255, 255, 255)    # white cover
spine_color = (220, 220, 220, 255)    # light gray spine
page_line_color = (200, 200, 200, 255)# page lines
letter_color = (20, 40, 80, 255)      # dark letters
magnifier_color = (80, 80, 80, 255)   # magnifier handle

# Draw background circle
margin = 8
draw.ellipse((margin, margin, size-margin, size-margin), fill=bg_color)

# Draw a stylized book (dictionary) — a cover with a spine and page lines
book_w = int(size * 0.62)
book_h = int(size * 0.62)
book_x = int((size - book_w) / 2) - 6
book_y = int((size - book_h) / 2) - 6

# Spine (left)
spine_w = int(book_w * 0.14)
draw.rectangle([book_x, book_y, book_x + spine_w, book_y + book_h], fill=spine_color, outline=None)

# Cover (main)
cover_x0 = book_x + spine_w - 2
cover_x1 = book_x + book_w
draw.rounded_rectangle([cover_x0, book_y, cover_x1, book_y + book_h], radius=10, fill=cover_color)

# Page edge lines (right side)
line_x = cover_x1 - 6
for i in range(6):
    y = book_y + 14 + i * (book_h - 28) / 6
    draw.line([(line_x, y), (cover_x1, y)], fill=page_line_color, width=2)

# Add 'ABC' text on the cover (dictionary title)
try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
except Exception:
    font = ImageFont.load_default()

text = "ABC"
# compute text bounding box (compatible with recent Pillow versions)
bbox = draw.textbbox((0, 0), text, font=font)  # returns (x0, y0, x1, y1)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]

text_x = cover_x0 + (book_w - spine_w - tw) / 2 - 4
text_y = book_y + (book_h - th) / 2 - 8
draw.text((text_x, text_y), text, font=font, fill=letter_color)

# Draw a small magnifying glass overlapping the bottom-right of the book
mg_center = (cover_x1 - 30, book_y + book_h - 34)
mg_radius = 22
draw.ellipse([mg_center[0]-mg_radius, mg_center[1]-mg_radius, mg_center[0]+mg_radius, mg_center[1]+mg_radius], outline=magnifier_color, width=6)
handle_start = (mg_center[0] + int(mg_radius*0.6), mg_center[1] + int(mg_radius*0.6))
handle_end = (handle_start[0] + 28, handle_start[1] + 28)
draw.line([handle_start, handle_end], fill=magnifier_color, width=8)
draw.ellipse([mg_center[0]-8, mg_center[1]-8, mg_center[0]-2, mg_center[1]-2], fill=(255,255,255,120))

# Apply slight shadow under the book for depth
shadow = Image.new("RGBA", img.size, (0,0,0,0))
sd = ImageDraw.Draw(shadow)
sd.ellipse([book_x+6, book_y+book_h-8, cover_x1-6, book_y+book_h+10], fill=(0,0,0,80))
img = Image.alpha_composite(img, shadow)

# Save as ICO with multiple sizes for compatibility
sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
img.save(out_path, format="ICO", sizes=sizes)

print("Created dictionary icon at:", os.path.abspath(out_path))
print("File exists:", os.path.exists(out_path))
