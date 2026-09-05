"""Small offline software preview for GLB QA when a browser surface is unavailable."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont


def render(mesh: trimesh.Trimesh, azimuth: float, width: int = 700, height: int = 480) -> Image.Image:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    vertices -= (mesh.bounds[0] + mesh.bounds[1]) / 2
    angle = np.deg2rad(azimuth)
    rotation = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    points = vertices @ rotation.T
    faces = np.asarray(mesh.faces)
    triangles = points[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)

    uv = np.asarray(mesh.visual.uv)
    texture = np.asarray(mesh.visual.material.baseColorTexture.convert("RGB"))
    face_uv = uv[faces].mean(axis=1)
    tx = np.clip((face_uv[:, 0] % 1) * (texture.shape[1] - 1), 0, texture.shape[1] - 1).astype(int)
    ty = np.clip((1 - face_uv[:, 1] % 1) * (texture.shape[0] - 1), 0, texture.shape[0] - 1).astype(int)
    colours = texture[ty, tx].astype(np.float64)
    light = np.array([-0.35, 0.72, 0.60]); light /= np.linalg.norm(light)
    shade = np.clip(0.48 + 0.52 * np.abs(normals @ light), 0.35, 1.0)[:, None]
    colours = np.clip(colours * shade, 0, 255).astype(np.uint8)

    xy = points[:, [0, 1]]
    scale = min((width - 70) / max(np.ptp(xy[:, 0]), 1e-6), (height - 70) / max(np.ptp(xy[:, 1]), 1e-6))
    projected = np.empty_like(xy)
    projected[:, 0] = width / 2 + xy[:, 0] * scale
    projected[:, 1] = height / 2 - xy[:, 1] * scale
    projected = np.round(projected).astype(np.int32)

    canvas = np.full((height, width, 3), (246, 248, 252), dtype=np.uint8)
    order = np.argsort(triangles[:, :, 2].mean(axis=1))
    for face_index in order:
        cv2.fillConvexPoly(canvas, projected[faces[face_index]], tuple(int(x) for x in colours[face_index][::-1]), lineType=cv2.LINE_AA)
    return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))


def main(source: Path, target: Path) -> None:
    scene = trimesh.load(source, force="scene")
    mesh = trimesh.util.concatenate(tuple(scene.geometry.values()))
    views = [("FRONT ¾", 32), ("SIDE", 90), ("REAR ¾", 212), ("FRONT", 0)]
    tiles = []
    for label, angle in views:
        tile = render(mesh, angle)
        ImageDraw.Draw(tile).rounded_rectangle((16, 16, 116, 44), radius=6, fill=(20, 35, 58))
        ImageDraw.Draw(tile).text((27, 24), label, fill="white", font=ImageFont.load_default())
        tiles.append(tile)
    out = Image.new("RGB", (1400, 960), "white")
    for index, tile in enumerate(tiles):
        out.paste(tile, ((index % 2) * 700, (index // 2) * 480))
    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target, quality=95)
    print(target)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: render_glb_qa.py source.glb target.png")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
