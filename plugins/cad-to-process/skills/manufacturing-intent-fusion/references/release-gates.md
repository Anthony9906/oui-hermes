# Release gates

Block or require review when any condition applies:

- invalid B-Rep
- semantic PMI expected but not extracted
- DXF recovery/audit finding
- explicit dimension text override not reconciled
- raster-only critical evidence
- unresolved value or tolerance conflict
- missing critical annotation-to-geometry association
- critical requirement state is inferred, assumed, or unknown
- unpromoted machining-feature candidate
- empty requirement set

`candidate_for_release` means only that automated evidence checks found no
known blocker. It is not engineering approval, process certification, or CAM
authorization.
