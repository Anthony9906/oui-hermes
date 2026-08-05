# OCR evidence policy

eDOCr2 is used as a segmentation and specialist OCR candidate generator. Its
output is not deterministic source truth.

For every extracted item preserve:

- page number
- pixel bounding box
- raw crop location
- raw OCR text
- OCR engine and model version
- confidence when available
- optional corrected text as a separate inferred record

Use `inferred` for OCR text, even when confidence is high. Promote to
`observed` only through human confirmation or a native semantic source such as
DXF DIMENSION or AP242 PMI.
