# Routing rules

| Input | Primary path | Important boundary |
|---|---|---|
| STEP/STP | STEP B-Rep inspector | Prefer AP242 semantic PMI when present |
| DXF | DXF semantic inspector | Preserve handles, layouts, blocks, and dimensions |
| Vector PDF | Future vector-PDF adapter | Do not discard text/path coordinates |
| Scanned PDF | Drawing OCR inspector | Every field remains candidate evidence |
| PNG/JPEG/TIFF/BMP | Drawing OCR inspector | Preserve page and pixel bounding boxes |
| DWG/native CAD | Controlled conversion | Record converter and source revision |

The PDF byte probe only produces hints. Confirm vector content with a real PDF
object parser before release-critical extraction.
