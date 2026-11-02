# Five-paper referee revision: preliminary code only

This repository releases a small selection of author-owned code and protocols from a work-in-progress manuscript revision. It contains **no source datasets, participant-level records, fitted checkpoints, candidate figures, manuscripts, or scientific result tables**. It is not an independently reproducible evidence package, a journal submission, or a completed Zenodo deposit. The manuscript review remains a set of simulated reviews, not independent human peer review.

The scripts include hard-coded private-repository paths, hashes and local registration references so their exact checks are visible. The full analyses cannot run from this repository alone: their registered Git objects and original saved inputs are not included. Public access to the exact data and supporting evidence remains to be resolved under source terms and applicable ethics. The synthetic checks below do run without those data, using Python and NumPy:

```sh
python3 -B tools/revision_20261102/a_nonempty_sensitivity.py --self-test
python3 -B tools/revision_20261102/reviewer_saved_cells.py --self-test
```

The support-matched sensitivity distinguishes width on nonempty exact intersections from contradictions excluded from that comparison. Its input-dependent outputs must not be inferred from the synthetic checks. The reviewer-cell protocol is post hoc and its outcomes had already been inspected; a local registration does not turn them into confirmatory results.

The author's own code is MIT licensed (see `LICENSE`). The author's original protocol and documentation text is CC BY 4.0 (see `TEXT-LICENSE.md`). These licenses do not apply to third-party datasets or their derivatives. In particular, the ABIDE I source describes noncommercial/share-alike conditions and registration for access; consult its own usage agreement before use or redistribution. No dataset or derivative is distributed in this repository.

No DOI has been issued for this preliminary code-only repository. A broader release will need its own evidence inventory, source permissions, ethics determination and accurate reproducibility statement.
