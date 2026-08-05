#!/usr/bin/env python3
from __future__ import annotations

import json

from mdi_common import dependency_status


if __name__ == "__main__":
    print(json.dumps(dependency_status(), indent=2, sort_keys=True))
