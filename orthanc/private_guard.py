"""Private-data guard for the public DICOMweb edge.

The public instance serves DICOMweb read-only via the internal proxy. Some data
(e.g. ADNI) is fine to keep on the box for *local* experiments but must NEVER be
redistributed publicly. This Orthanc Python plugin makes that safe even though
public and private studies share one Orthanc:

  * The proxy stamps every request that arrives via the public edge with the
    header `X-Public-Access: 1` (see proxy/default.conf). Admin ingest goes
    straight to the loopback admin port (127.0.0.1:8042) with no proxy and no
    header, so admins keep full, unfiltered access.

  * For a public request, this plugin:
      - denies (403) any study-scoped read — WADO-RS pixels/bulk, /metadata,
        and the per-study series/instances QIDO — of a study labelled `private`;
      - serves a *filtered* study list at /guard/qido-studies that mirrors the
        native QIDO-RS study search but removes `private`-labelled studies, so
        they never even appear in the public study browser.

The proxy points the public study-list and the cross-study QIDO listings at the
right places; this plugin enforces the label rule. Label data `private` at
ingest (scripts/load_adni.sh does this automatically) and it stays off the
public edge. See docs/ARCHITECTURE.md and docs/DATASETS.md.
"""

import json
import re
import time
import urllib.parse

import orthanc

PRIVATE_LABEL = "private"
PUBLIC_HEADER = "x-public-access"  # set by the proxy on the public DICOMweb path

# Study-scoped DICOMweb: /dicom-web/studies/<StudyInstanceUID>[/...]
# (WADO-RS retrieve/metadata, per-study series & instances QIDO, frames, bulk).
# Match any non-slash UID segment (not just digits/dots) so the label check is
# fail-safe for any study-scoped path; a segment that isn't a real study simply
# resolves to "not private" and is allowed.
_STUDY_SCOPED = re.compile(r"^/dicom-web/studies/([^/]+)(?:/.*)?$")

# Tiny TTL cache so a burst of frame requests for one study doesn't hammer the
# index. Labels change rarely; 30s staleness is fine for a sandbox.
_CACHE_TTL = 30.0
_label_cache = {}  # study_uid -> (is_private, expires_at)


def _study_uid_is_private(study_uid):
    now = time.time()
    cached = _label_cache.get(study_uid)
    if cached and cached[1] > now:
        return cached[0]

    is_private = False
    matches = json.loads(orthanc.RestApiPost("/tools/find", json.dumps({
        "Level": "Study",
        "Query": {"StudyInstanceUID": study_uid},
    })))
    for orthanc_id in matches:
        labels = json.loads(orthanc.RestApiGet("/studies/%s/labels" % orthanc_id))
        if PRIVATE_LABEL in labels:
            is_private = True
            break

    _label_cache[study_uid] = (is_private, now + _CACHE_TTL)
    return is_private


def _is_public_request(request):
    for key, value in (request.get("headers") or {}).items():
        if key.lower() == PUBLIC_HEADER:
            return value == "1"
    return False


def _filter_incoming(uri, **request):
    # Admin / loopback (no proxy header) keeps full, unfiltered access.
    if not _is_public_request(request):
        return True

    match = _STUDY_SCOPED.match(uri)
    if match and _study_uid_is_private(match.group(1)):
        return False  # -> 403
    return True


def _public_studies(output, uri, **request):
    """Filtered QIDO-RS study list: native search minus `private` studies.

    We delegate to Orthanc's own DICOMweb QIDO (so query filters, includefield,
    paging and the DICOM+JSON shape stay exactly OHIF-compatible) and only drop
    studies carrying the `private` label.
    """
    args = request.get("get") or {}
    query = urllib.parse.urlencode(args)
    native_uri = "/dicom-web/studies" + (("?" + query) if query else "")

    # RestApiGetAfterPlugins (not RestApiGet) so this reaches the DICOMweb
    # plugin's QIDO route rather than only Orthanc's core REST API.
    studies = json.loads(orthanc.RestApiGetAfterPlugins(native_uri))
    visible = [s for s in studies if not _study_json_is_private(s)]
    output.AnswerBuffer(json.dumps(visible), "application/dicom+json")


def _study_json_is_private(study_json):
    uid_tag = study_json.get("0020000D", {})  # StudyInstanceUID
    values = uid_tag.get("Value") or []
    if not values:
        return False
    return _study_uid_is_private(values[0])


orthanc.RegisterIncomingHttpRequestFilter(_filter_incoming)
orthanc.RegisterRestCallback("/guard/qido-studies", _public_studies)
