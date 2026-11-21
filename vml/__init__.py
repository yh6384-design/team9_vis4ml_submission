"""Shared code for the Team 9 VisML project (DS-GA 3001, Fall 2026).

Every stage folder (features/, profiles/, models/, ...) imports from here, so that every stage computes
calibration, bootstrap intervals and slices with exactly the same code.

    vml.paths    where the inputs are and where outputs go (set VML_CORPUS / VML_OUT)
    vml.params   every number we chose (seeds, bins, thresholds) in one place
    vml.common   small helpers: logging, json, the run manifest written next to every output
    vml.metrics  ECE, signed gap, Brier, log loss, AUROC, reliability tables
    vml.bootstrap  family bootstrap (resample whole patent families, keep their rounds together)
    vml.learned  learned reliability curve with an EBM (as in Calibrate / pycalibrate), family cross-fitted
    vml.slicing  candidate slices, the two Slice Finder tests, ranking and the frozen top five
"""
