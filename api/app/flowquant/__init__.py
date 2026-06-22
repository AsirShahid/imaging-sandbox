"""Phase-contrast (PC) MRI flow quantification.

Pure-numpy core (no Orthanc / matplotlib dependency) so the physics is fast to
unit-test in isolation:

- ``quantify``  : phase images -> velocity -> ROI flow curve -> flow metrics.
- ``phantom``   : a digital PC-MRI acquisition with a *known* flow waveform, so
                  recovery error is measurable (ground-truth validation).
- ``validate``  : sweep VENC / SNR and report recovered-vs-true error stats.

Plotting (matplotlib) lives in ``plots`` and is imported lazily by the worker
task only, keeping the math importable on its own.
"""
