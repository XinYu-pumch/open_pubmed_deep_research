#!/usr/bin/env python3
"""
Generate the application icon for Open Pubmed Deep Research.

The macOS `iconutil` tool rejects iconsets on some environments in this
project, so we generate the `.icns` file directly with Pillow instead.
"""

import math
import os

from PIL import Image, ImageDraw


def create_icon_image(size):
    """Create an icon image at the specified size."""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate dimensions
    padding = int(size * 0.1)
    inner_size = size - 2 * padding

    # Background - rounded rectangle with gradient-like effect
    bg_color = (79, 70, 229)  # Indigo
    bg_lighter = (99, 102, 241)

    # Draw main background circle
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=bg_color
    )

    # Draw decorative DNA helix strands
    center_x = size // 2
    center_y = size // 2
    helix_width = int(inner_size * 0.35)
    helix_height = int(inner_size * 0.6)

    # Draw simplified DNA symbol
    strand_width = max(3, size // 50)

    # Left strand
    points_left = []
    for i in range(20):
        t = i / 19
        y = center_y - helix_height // 2 + int(t * helix_height)
        x = center_x - helix_width // 4 + int(math.sin(t * 3 * math.pi) * helix_width // 4)
        points_left.append((x, y))

    # Right strand
    points_right = []
    for i in range(20):
        t = i / 19
        y = center_y - helix_height // 2 + int(t * helix_height)
        x = center_x + helix_width // 4 + int(math.sin(t * 3 * math.pi + math.pi) * helix_width // 4)
        points_right.append((x, y))

    # Draw strands
    if len(points_left) >= 2:
        draw.line(points_left, fill='white', width=strand_width, joint='curve')
    if len(points_right) >= 2:
        draw.line(points_right, fill='white', width=strand_width, joint='curve')

    # Draw connecting rungs
    for i in range(4):
        t = (i + 0.5) / 4
        idx = min(int(t * 19), 18)
        left_point = points_left[idx]
        right_point = points_right[idx]
        draw.line([left_point, right_point], fill='white', width=strand_width // 2)

    # Draw a small document icon in corner
    doc_size = int(size * 0.25)
    doc_x = size - padding - doc_size
    doc_y = size - padding - doc_size

    # Document background
    draw.rectangle(
        [doc_x, doc_y, doc_x + doc_size, doc_y + doc_size],
        fill='white',
        outline=None
    )

    # Document corner fold
    fold_size = doc_size // 4
    draw.polygon(
        [
            (doc_x + doc_size - fold_size, doc_y),
            (doc_x + doc_size, doc_y + fold_size),
            (doc_x + doc_size - fold_size, doc_y + fold_size)
        ],
        fill=bg_lighter
    )

    # Document lines
    line_color = (200, 200, 200)
    line_margin = doc_size // 6
    line_height = max(1, doc_size // 15)
    for i in range(3):
        y = doc_y + line_margin * 2 + i * (line_margin + line_height)
        width = doc_size - line_margin * 2 if i < 2 else (doc_size - line_margin * 2) * 2 // 3
        draw.rectangle(
            [doc_x + line_margin, y, doc_x + line_margin + width, y + line_height],
            fill=line_color
        )

    return img


def create_icns(output_path):
    """Create a multi-resolution `.icns` file for macOS."""
    master = create_icon_image(1024)
    sizes = [
        (16, 16),
        (32, 32),
        (64, 64),
        (128, 128),
        (256, 256),
        (512, 512),
        (1024, 1024),
    ]

    master.save(output_path, format='ICNS', sizes=sizes)
    print(f"Created: {output_path}")
    return True


def main():
    """Main entry point."""
    # Ensure resources directory exists
    resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
    os.makedirs(resources_dir, exist_ok=True)

    # Generate icon
    output_path = os.path.join(resources_dir, 'app_icon.icns')
    try:
        create_icns(output_path)
    except Exception as exc:
        print(f"Error creating icns: {exc}")
        img = create_icon_image(512)
        png_path = output_path.replace('.icns', '.png')
        img.save(png_path)
        print(f"Fallback: Created PNG at {png_path}")

    # Also save a preview PNG
    preview_path = os.path.join(resources_dir, 'app_icon_preview.png')
    img = create_icon_image(512)
    img.save(preview_path)
    print(f"Preview: {preview_path}")


if __name__ == '__main__':
    main()
