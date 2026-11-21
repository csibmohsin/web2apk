"""
Icon processing module for Android launcher and adaptive icons.
Processes a single user-supplied image (PNG/JPG) into all required Android mipmap densities:
- mdpi: 48x48
- hdpi: 72x72
- xhdpi: 96x96
- xxhdpi: 144x144
- xxxhdpi: 192x192
Also generates adaptive icon foregrounds and circular round icons.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class IconProcessor:
    """Processes application icons into standard Android launcher resource densities."""

    # Standard Android launcher icon pixel dimensions
    DENSITIES: Dict[str, int] = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }

    # Adaptive icon foreground dimensions (432x432 for xxxhdpi base)
    ADAPTIVE_FOREGROUND_SIZE = 432
    # Safe zone for adaptive icon foreground (inner 66% area to prevent launcher circular clipping)
    ADAPTIVE_SAFE_SCALE = 0.68

    @classmethod
    def process_icon(cls, source_path: str, target_res_dir: str) -> bool:
        """
        Takes a source image path (PNG, JPG, etc.) and generates all density mipmaps
        and adaptive icon foregrounds into target_res_dir.
        """
        source_p = Path(source_path)
        if not source_p.exists():
            raise FileNotFoundError(f"Source icon file not found: {source_path}")

        res_path = Path(target_res_dir)
        res_path.mkdir(parents=True, exist_ok=True)

        # Remove existing template icon files to prevent "Duplicate resources" conflicts between .webp, .xml, and .png
        for p in res_path.rglob("ic_launcher*"):
            if p.is_file() and p.name not in ["ic_launcher_background.xml"]:
                # Keep adaptive xml in mipmap-anydpi-v26 unless it's ic_launcher_foreground.xml
                if p.suffix in [".webp", ".png"] or p.name == "ic_launcher_foreground.xml":
                    try:
                        p.unlink()
                    except Exception:
                        pass


        if not PIL_AVAILABLE:
            # Fallback when PIL is not installed: copy the source image directly to densities
            return cls._fallback_copy(source_p, res_path)

        try:
            with Image.open(source_p) as img:
                # Ensure RGBA mode for transparency support
                img_rgba = img.convert("RGBA")

                # 1. Fit into a square transparent canvas preserving aspect ratio
                square_img = cls._create_square_canvas(img_rgba)

                # 2. Generate standard launcher icons (ic_launcher.png) for each density
                for density, size in cls.DENSITIES.items():
                    density_dir = res_path / density
                    density_dir.mkdir(parents=True, exist_ok=True)

                    # Standard square launcher
                    resized_standard = square_img.resize((size, size), Image.Resampling.LANCZOS)
                    resized_standard.save(density_dir / "ic_launcher.png", format="PNG", optimize=True)

                    # Round launcher with circular mask
                    round_img = cls._apply_circular_mask(resized_standard)
                    round_img.save(density_dir / "ic_launcher_round.png", format="PNG", optimize=True)

                # 3. Generate adaptive icon foreground
                cls._generate_adaptive_foreground(square_img, res_path)

            return True
        except Exception as e:
            raise RuntimeError(f"Failed to process icon '{source_path}': {str(e)}")

    @classmethod
    def _create_square_canvas(cls, img: "Image.Image") -> "Image.Image":
        """
        Places the image in the center of a square transparent canvas,
        preserving original aspect ratio.
        """
        w, h = img.size
        max_dim = max(w, h)
        square = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))

        offset_x = (max_dim - w) // 2
        offset_y = (max_dim - h) // 2
        square.paste(img, (offset_x, offset_y), img if img.mode == "RGBA" else None)
        return square

    @classmethod
    def _apply_circular_mask(cls, img: "Image.Image") -> "Image.Image":
        """
        Applies a high-quality antialiased circular mask for ic_launcher_round.png.
        """
        size = img.size[0]
        # Super-sample mask 4x for smooth antialiasing
        mask_size = size * 4
        mask = Image.new("L", (mask_size, mask_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, mask_size, mask_size), fill=255)
        mask = mask.resize((size, size), Image.Resampling.LANCZOS)

        output = img.copy()
        output.putalpha(mask)
        return output

    @classmethod
    def _generate_adaptive_foreground(cls, square_img: "Image.Image", res_path: Path):
        """
        Generates adaptive icon foreground (432x432) with proper safe zone scaling
        so launcher icons aren't cropped when shaped into circles/squircles by the OS.
        """
        fg_canvas = Image.new("RGBA", (cls.ADAPTIVE_FOREGROUND_SIZE, cls.ADAPTIVE_FOREGROUND_SIZE), (0, 0, 0, 0))
        target_content_size = int(cls.ADAPTIVE_FOREGROUND_SIZE * cls.ADAPTIVE_SAFE_SCALE)

        scaled_content = square_img.resize((target_content_size, target_content_size), Image.Resampling.LANCZOS)
        offset = (cls.ADAPTIVE_FOREGROUND_SIZE - target_content_size) // 2
        fg_canvas.paste(scaled_content, (offset, offset), scaled_content)

        drawable_dir = res_path / "drawable"
        drawable_dir.mkdir(parents=True, exist_ok=True)
        fg_canvas.save(drawable_dir / "ic_launcher_foreground.png", format="PNG", optimize=True)

    @classmethod
    def _fallback_copy(cls, source_p: Path, res_path: Path) -> bool:
        """Fallback when Pillow is not installed."""
        for density in cls.DENSITIES.keys():
            density_dir = res_path / density
            density_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_p, density_dir / "ic_launcher.png")
            shutil.copy2(source_p, density_dir / "ic_launcher_round.png")

        drawable_dir = res_path / "drawable"
        drawable_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_p, drawable_dir / "ic_launcher_foreground.png")
        return True

    @classmethod
    def generate_default_icon(cls, target_file: str, app_name: str = "Evidentix") -> str:
        """
        Generates a modern, professional Evidentix branded default application icon
        if the user does not provide one.
        """
        target_p = Path(target_file)
        target_p.parent.mkdir(parents=True, exist_ok=True)

        if not PIL_AVAILABLE:
            return None

        size = 512
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded background plate
        margin = 32
        corner_radius = 96
        # Evidentix Deep Navy to Slate Gradient/Color
        bg_color = (11, 25, 44, 255)  # #0B192C
        draw.rounded_rectangle(
            (margin, margin, size - margin, size - margin),
            radius=corner_radius,
            fill=bg_color,
            outline=(0, 141, 218, 255),  # Evidentix Blue #008DDA
            width=8,
        )

        # Draw a stylized modern 'E' or web globe icon
        accent_color = (0, 180, 216, 255)  # #00B4D8
        white_color = (255, 255, 255, 255)

        # Stylized Web / E emblem
        cx, cy = size // 2, size // 2
        r = 120

        # Outer ring
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=accent_color, width=12)
        # Inner horizontal equator
        draw.line((cx - r + 8, cy, cx + r - 8, cy), fill=accent_color, width=10)
        # Vertical ellipse
        draw.ellipse((cx - r // 2, cy - r, cx + r // 2, cy + r), outline=white_color, width=10)

        img.save(target_p, format="PNG", optimize=True)
        return str(target_p)
