You are given the path to one Documents/plans/chunk-*.md file. Confirm its
Status is FROZEN before doing anything else — if it isn't, stop and report
that instead of implementing.

Read only:
1. The frozen plan itself.
2. The interface files listed in its section 4.
3. Documents/SRS-lean.md, but only the specific sections the plan's section 3
   points to, if you need to resolve a wording question the plan didn't
   fully capture.

Do not open or rely on any other chunk's plan file, and do not read ahead in
requirements-dependency-map.md beyond this chunk's section.

Implement exactly the scope in the plan's sections 1, 2, 6, and 7, following
the task breakdown in section 7 in order. Respect section 11's explicit
prohibitions and the project rule's module-boundary and traceability rules
without exception.

As you go:
- Write tests alongside implementation, not after — one test per checklist
  item where section 9 calls for it, each with its @pytest.mark.lreq marker
  and a matching tests/traceability.json entry.
- If you find yourself wanting to touch a file not listed in section 6, or to
  implement something the plan marks as another chunk's ownership, stop and
  report that instead of proceeding.
- If a requirement's exact behavior is ambiguous even after reading the cited
  SRS section, stop and report the ambiguity rather than choosing an
  interpretation silently.

When the task breakdown is complete, run the test suite for the files you own
and return pass/fail. Do not change the plan's Status — that happens in
 gate-verifier next.
