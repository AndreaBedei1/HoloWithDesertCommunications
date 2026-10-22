# Validation records

The files in this directory are dated validation and diagnosis records written
in Italian during development. They are kept unchanged (apart from relative
links) for provenance: they document what was executed, on which machine and
software versions, and the numbers observed at that date. They are not
maintained as user documentation; current behaviour is described in the
English documents listed in [../index.md](../index.md).

| File | Date | Content |
|---|---|---|
| [validation.md](validation.md) | 16 October 2026 | First end-to-end validation: official sample and sockets, E01–E06 with HoloOcean, controlled DESERT channel experiments, Linux package check |
| [consolidation-validation.md](consolidation-validation.md) | 16 October 2026 | Consolidation run: dashboard HTTP path for E03–E06, E04 MAC comparison metrics, Windows MIME fix, Ubuntu package check |
| [e03-loss-diagnosis.md](e03-loss-diagnosis.md) | 20 October 2026 | Attribution of the E03 delivery failures (BER, upstream second noise test) |
| [desert-laboratory.md](desert-laboratory.md) | 20 October 2026 | DESERT laboratory extension: image audit, stack builder, corrected BPSK test, native and integrated test results, Windows IPC fix |
| [ui-review.md](ui-review.md) | 20 October 2026 | Visual review of the dashboard and personal scenario editor, browser tests |

Later statements in these records can be superseded by subsequent work (for
example, modules listed there as not integrated were integrated afterwards).
Where a record and the current code disagree, the code and the English
documentation take precedence.
