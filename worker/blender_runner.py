import subprocess
import sys
from pathlib import Path
from typing import Optional

BLENDER_PATHS = [
    "/home/wano/Tools/blender-5.1.2-linux-x64/blender",
    "/home/wano/Art/RenderFarm/blender-5.1.2-linux-x64/blender",
    "/usr/bin/blender",
    "/usr/local/bin/blender",
]


def find_blender() -> Optional[str]:
    for path in BLENDER_PATHS:
        if Path(path).exists():
            return path
    return None


def run_render(
    blend_file: str,
    output_dir: str,
    frame_start: int,
    frame_end: int,
    output_format: str = "PNG",
    scene: Optional[str] = None,
) -> tuple[bool, str, list[str]]:
    blender = find_blender()
    if not blender:
        return False, "Blender not found", []

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        blender,
        "-b",
        blend_file,
        "-y",
    ]

    if scene:
        cmd += ["--scene", scene]

    cmd += [
        "-o", str(out_dir / "#####"),
        "-F", output_format,
        "-f", f"{frame_start}..{frame_end}",
        "--python-expr",
        "import bpy; bpy.context.scene.render.use_overwrite = False",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        return False, result.stderr[:2000] or result.stdout[:2000], []

    frames = sorted(
        str(f) for f in out_dir.iterdir()
        if f.suffix.lower().lstrip(".") in {"png", "jpg", "jpeg", "exr", "tga", "tif", "tiff", "bmp"}
    )

    return True, result.stdout[-500:] if result.stdout else "", frames
