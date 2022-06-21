import rawpy
import os
from PIL import Image


def nef_to_jpg(path):
    """Converts an image from .NEF to .jpg format.

    Writes the converted image to disk and deletes the original.

    Args:
        path: A path to an .NEF file

    Returns:
        path: A path to a .jpg file
    """
    with rawpy.imread(path) as raw:
        rgb_image = raw.postprocess(
            no_auto_bright=True,
            use_auto_wb=False,
            gamma=None,
            bright=1.0)
    os.remove(path)
    path = ".".join(["../", path.split(".")[2], "jpg"])
    converted_image = Image.fromarray(rgb_image)
    converted_image.save(f"{path}")
    return path
