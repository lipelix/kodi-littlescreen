"""Shrink saved API responses into test fixtures: drop tracking noise, keep structure."""

import json
import sys

DROP = {
    "trackingParams",
    "clickTrackingParams",
    "responseContext",
    "menu",
    "richThumbnail",
    "accessibility",
    "loggingDirectives",
    "serviceTrackingParams",
    "frameworkUpdates",
}


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if k not in DROP}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


for src, dst in zip(sys.argv[1::2], sys.argv[2::2]):
    with open(src, encoding="utf-8") as fh:
        data = clean(json.load(fh))
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
