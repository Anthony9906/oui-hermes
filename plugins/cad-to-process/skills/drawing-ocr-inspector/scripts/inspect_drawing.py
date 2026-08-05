#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import evidence, finding, new_manifest, write_json


def _rect_payload(rect: Any) -> dict[str, int]:
    return {
        "x": int(rect.x),
        "y": int(rect.y),
        "width": int(rect.w),
        "height": int(rect.h),
    }


def _cluster_bounds(cluster: dict[Any, Any]) -> dict[str, int]:
    root = next(iter(cluster))
    return _rect_payload(root)


def _load_pages(path: Path) -> list[Any]:
    import cv2
    import numpy as np

    if path.suffix.lower() == ".pdf":
        from pdf2image import convert_from_path

        return [
            cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
            for page in convert_from_path(path)
        ]
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"OpenCV could not read image: {path}")
    return [image]


def inspect(path: Path, language: str) -> dict[str, Any]:
    try:
        import cv2
        from edocr2 import tools
    except ImportError as exc:
        raise RuntimeError(
            "OCR runtime unavailable. Install requirements-ocr.txt and a reviewed eDOCr2 revision."
        ) from exc

    manifest = new_manifest(path, "raster_drawing", "drawing-ocr-inspector")
    pages = _load_pages(path)
    views: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []

    for page_index, image in enumerate(pages, start=1):
        _preview, frame, gdt_boxes, tables, dim_boxes = (
            tools.layer_segm.segment_img(
                image,
                autoframe=True,
                frame_thres=0.7,
                GDT_thres=0.02,
                binary_thres=127,
            )
        )
        views.append(
            {
                "id": f"page:{page_index}",
                "kind": "raster_page",
                "state": "observed",
                "pixel_size": [int(image.shape[1]), int(image.shape[0])],
                "frame": _rect_payload(frame) if frame else None,
            }
        )

        regions: list[tuple[str, dict[str, int]]] = []
        regions.extend(("gdt_candidate", _cluster_bounds(item)) for item in gdt_boxes)
        regions.extend(("table_candidate", _cluster_bounds(item)) for item in tables)
        regions.extend(("dimension_candidate", _rect_payload(item)) for item in dim_boxes)
        for region_index, (kind, bounds) in enumerate(regions, start=1):
            x = bounds["x"]
            y = bounds["y"]
            width = bounds["width"]
            height = bounds["height"]
            crop = image[y : y + height, x : x + width]
            text = ""
            try:
                _tokens, text = tools.ocr_pipelines.ocr_img_cv2(
                    crop, language=language, psm=7
                )
            except Exception:
                pass
            item_id = f"ocr:p{page_index}:r{region_index}"
            annotations.append(
                {
                    "id": item_id,
                    "kind": kind,
                    "state": "inferred",
                    "confidence": 0.5 if text.strip() else 0.25,
                    "page": page_index,
                    "bbox_px": bounds,
                    "raw_text": text.strip(),
                    "engine": "edocr2-segmentation+tesseract",
                }
            )

    manifest["views"] = views
    manifest["annotations"] = annotations
    manifest["evidence"].append(
        evidence(
            "ocr-regions",
            state="inferred",
            source_ref={"path": str(path.resolve()), "coordinate_space": "pixels"},
            confidence=0.5,
            value={"pages": len(pages), "regions": len(annotations)},
        )
    )
    manifest["findings"].append(
        finding(
            "OCR_REQUIRES_CONFIRMATION",
            "All raster-derived requirements require native-source or human confirmation.",
            severity="warning",
            state="inferred",
        )
    )
    manifest["release"]["decision"] = "needs_review"
    manifest["release"]["blockers"].append("raster_only_evidence")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--language", default="eng")
    args = parser.parse_args()
    if args.input.suffix.lower() not in {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }:
        parser.error("unsupported raster drawing extension")
    if not args.input.is_file():
        parser.error(f"input does not exist: {args.input}")
    try:
        payload = inspect(args.input, args.language)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
