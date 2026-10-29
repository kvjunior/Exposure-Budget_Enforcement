# Historical filename; current semantics pointer

The active semantics are now consolidated in decision_index_contract.md (Slice 2.2.1).
The original Slice 2.1 text is preserved in frozen_slice_2_1/. In particular, timed arrivals,
queue/deadline behavior and interleaved owner/production events were not implemented then and are
not claimed by the current decision-index harness. A plan-local retry is not a persistent queue.
