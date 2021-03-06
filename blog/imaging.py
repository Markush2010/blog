import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from os.path import basename, dirname, exists, join, splitext

FILENAME = object()


COVER_IMAGE_SIZES = (
    # index
    (682, 316),  # 1 col, small
    (502, 232),  # 2 col, medium
    (380, 176),  # 3 col, large
    # detail
    # 1 col, small: as above
    (682, 316),  # 1 col, small
    (1075, 316),  # 1 col, medium
    (1280, 375),  # 1 col, large
    # Open Graph
    # Google: https://developers.google.com/+/web/snippet/article-rendering#example_with_full-bleed_image
    (1012, 422),  # 2 x (506, 211)
)

IMG_BASE_DIR = join("content", "images")
EQUATION_BASE_DIR = join(IMG_BASE_DIR, "equation")
THUMB_BASE_DIR = join(IMG_BASE_DIR, "thumb")
MANIFEST_FILE = join(THUMB_BASE_DIR, ".manifest.json")

OPTIMIZE_COMMANDS = {
    ".jpg": [
        "jpeg-recompress",
        "--quality",
        "medium",
        "--method",
        "smallfry",
        "--min",
        "40",
        "--max",
        "85",
        FILENAME,
        FILENAME,
    ]
}


def load_manifest():
    data = {}
    if exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as fp:
            data = json.load(fp)
    return data


def write_manifest(data):
    with open(MANIFEST_FILE, "w") as fp:
        json.dump(data, fp)


def get_hash(filename):
    with open(filename, "rb") as fp:
        data = fp.read()
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def get_optimize_command(ext, filename):
    if ext not in OPTIMIZE_COMMANDS:
        return None
    cmd = OPTIMIZE_COMMANDS[ext]
    return [(filename if part is FILENAME else part) for part in cmd]


def gen_article_thumbnails(source, sizes=None, crop=True):
    out = []
    source_dir = dirname(source)
    source_name = basename(source)
    name, ext = splitext(source_name)
    source_file = join(IMG_BASE_DIR, source)
    dest_dir = join(THUMB_BASE_DIR, source_dir)
    if not exists(dest_dir):
        os.makedirs(dest_dir)

    manifest = load_manifest()
    hash = get_hash(source_file)
    if hash == manifest.get(source, ""):
        skip = True
    else:
        skip = False
        manifest[source] = hash

    if sizes is None:
        sizes = COVER_IMAGE_SIZES
    for width, height in sizes:
        if crop:
            dest_name = f"{name}-{width}x{height}.jpg"
        else:
            dest_name = f"{name}-{width}x{height}-nocrop.jpg"
        dest = join(dest_dir, dest_name)
        out.append(join(source_dir, dest_name))
        if skip and exists(dest):
            continue
        cmd = ["convert", "-verbose", source_file, "-resize", f"{width}x{height}^"]
        if crop:
            cmd += ["+repage", "-gravity", "center", "-crop", f"{width}x{height}+0+0"]
        if ext != "jpg":
            cmd += ["+repage", "-background", "white", "-flatten"]
        cmd += ["+repage", "-auto-orient", dest]
        subprocess.call(cmd)

        optimize = get_optimize_command("jpg", dest)
        if optimize:
            try:
                subprocess.call(optimize)
            except OSError:
                raise OSError("Image optimzation failed. All dependencies installed?")

    if not skip:
        write_manifest(manifest)
    return out


def gen_equation_image(equation):
    if not exists(EQUATION_BASE_DIR):
        os.makedirs(EQUATION_BASE_DIR)

    content = [
        r"\documentclass[convert={density=150,outext=.png},preview]{standalone}",
        r"\usepackage{amsmath}",
        r"\begin{document}",
    ]
    content.extend(equation)
    content.extend([r"\end{document}"])

    text = "\n".join(content)
    hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    dest_file = join(EQUATION_BASE_DIR, hash + ".png")

    l = len("content")
    out = dest_file[l:]

    if exists(dest_file):
        return out

    with tempfile.NamedTemporaryFile("w", suffix=".tex") as tfp:
        tfp.write(text)
        tfp.flush()
        try:
            subprocess.call(
                ["pdflatex", "-shell-escape", tfp.name], cwd=dirname(tfp.name)
            )
        except OSError:
            raise OSError("No pdflatex installed?")
        name, ext = splitext(tfp.name)
        source_file = name + ".png"
        subprocess.call(
            ["convert", "-verbose", "-trim", source_file, source_file],
            cwd=dirname(tfp.name),
        )
        shutil.move(source_file, dest_file)
        for ext in (".aux", ".log", ".pdf"):
            fn = name + ext
            if exists(fn):
                os.unlink(fn)

    return out
