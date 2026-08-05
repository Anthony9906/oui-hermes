# DXF evidence

Prefer native objects in this order:

1. DIMENSION and TOLERANCE objects.
2. LEADER/MLEADER plus attached text or blocks.
3. TEXT/MTEXT and INSERT/ATTRIB.
4. Primitive geometry used to render annotations.

Record both `get_measurement()` and explicit `dxf.text` for DIMENSION. A
non-empty override may intentionally differ from geometry and requires review.

Preserve:

- layout name
- entity handle
- owner/block identity
- layer
- insertion points and vertices
- dimension style
- attached attributes
- recovery/audit findings
