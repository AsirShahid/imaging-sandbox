# Demo datasets

All demo imaging is **public, de-identified research data** from
[The Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net/),
used under **CC BY 3.0**, loaded with [`scripts/load_tcia.sh`](../scripts/load_tcia.sh).
A small multiframe MR and an ultrasound from pydicom test data are also seeded
(the ultrasound drives the de-identification pixel-PHI demo) via
[`scripts/seed_demo_data.py`](../scripts/seed_demo_data.py).

> No clinical / PHI data is used here, and none ever should be. See
> [ARCHITECTURE.md](ARCHITECTURE.md) for the read-only / containment model.

| Collection | Modality · region | Series loaded | License |
|---|---|---|---|
| Pancreas-CT | CT · abdomen | 2 series (~181, ~185 slices) | CC BY 3.0 |
| LIDC-IDRI | CT · chest | 1 series (~92 slices) | CC BY 3.0 |
| Soft-tissue-Sarcoma | MR · T2 | 1 series (~40 slices) | CC BY 3.0 |
| pydicom test data | MR (multiframe), US | 2 instances | redistributable test fixtures |

## Attribution & citations

Data hosting — **TCIA**:

> Clark K, Vendt B, Smith K, et al. *The Cancer Imaging Archive (TCIA):
> Maintaining and Operating a Public Information Repository.* Journal of Digital
> Imaging 26(6):1045–1057, 2013. https://doi.org/10.1007/s10278-013-9622-7

Collection-specific data citations (use the exact citation + DOI shown on each
collection's TCIA page):

- **Pancreas-CT** — Roth H, Farag A, Turkbey EB, Lu L, Liu J, Summers RM (2016).
- **LIDC-IDRI** — Armato SG III, McLennan G, Bidaut L, et al. (2011).
- **Soft-tissue-Sarcoma** — Vallières M, Freeman CR, Skamene SR, El Naqa I (2015).

Each collection is CC BY 3.0; attribution above satisfies the license. Swap in
other public collections by editing the `SERIES` list in `scripts/load_tcia.sh`.

## ADNI (local / admin-only — NOT on the public instance)

[ADNI](https://adni.loni.usc.edu/) (Alzheimer's Disease Neuroimaging Initiative)
brain MRI/PET is excellent test data for the flow / recon / de-id tools, but it
is **not redistributable**: access requires an approved application and a signed
**Data Use Agreement**, and that DUA forbids sharing the data with anyone who
hasn't signed it. So ADNI is treated differently from the TCIA demo set:

- **Never on the public edge.** It must not appear on `imaging.asir.dev`. There
  is also no anonymous download API (unlike TCIA's NBIA), so there is no
  auto-downloader — you download studies from LONI/IDA yourself.
- **Loaded local/admin-only and labelled `private`.** Ingest with
  [`scripts/load_adni.sh`](../scripts/load_adni.sh), which talks to the loopback
  admin port only (refuses any non-loopback target) and tags every loaded study
  with the `private` label.
- **Kept off the public DICOMweb by the guard**, even though it lives in the same
  Orthanc: `private`-labelled studies are never listed or served on the public
  read path. See the private-data guard in [ARCHITECTURE.md](ARCHITECTURE.md)
  (`orthanc/private_guard.py` + `proxy/default.conf`).

```bash
# After requesting access + signing the DUA and downloading from LONI/IDA:
./scripts/load_adni.sh /path/to/ADNI_export_dir     # over the admin SSH tunnel
```

Access & citation — **ADNI / LONI IDA**: request access at
<https://adni.loni.usc.edu/> and cite per ADNI's *Data Use Agreement* and
publication policy (including the ADNI acknowledgement and funding text shown on
the ADNI site). Data collection/sharing for ADNI is funded by NIH grant
U01 AG024904 and DOD ADNI (W81XWH-12-2-0012).
