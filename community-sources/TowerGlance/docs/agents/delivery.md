# Delivery

## Repository default

Every implementation Work Brief, spec, or delivery ticket records:

```markdown
## Delivery strategy

**Delivery path:** direct-main | dedicated-branch
**Publish boundary:** commit | commit-and-push | draft-pr | merge
**Required validation:** <commands or policy>
**Reason:** <risk-based reason>
```

When a Work Brief contains no justified override, use:

**Delivery path:** dedicated-branch

**Publish boundary:** merge

**Required validation:** Before `manage-ci` establishes concrete repository commands, run the narrowest relevant available test, lint, typecheck, or build target and run `git diff --check`. If a required check does not exist or cannot be executed, do not merge automatically; leave a draft PR that names the missing evidence. After `manage-ci` establishes the completion suite, that suite becomes mandatory before merge.

**Reason:** TowerGlance includes network-protocol handling, state models, dependencies, and a public interface, so ordinary product work does not meet the low-risk direct-main criteria.

Use direct-main only for a small, local, reversible change with no schema, data, dependency, security, authentication, public-API, or parallel-work risk, after relevant validation passes and when repository rules permit it. Otherwise use a dedicated branch.

Planning tickets inherit the invoking map's delivery strategy, or this repository strategy when the map records no override. Their durable research artifacts follow the same strategy. Apply an unambiguous direct-main exception autonomously; ask only when the applicable strategy genuinely cannot be determined.

The `merge` boundary is evidence-gated: `deliver-work` attempts every acceptance check it can perform, including browser-based visual and interactive workflows, and merges automatically only when every criterion is checked and all review, validation, CI, and mergeability gates pass. Any criterion lacking evidence leaves the PR as draft for the remaining human input. Use `draft-pr` only when preliminary maintainer review is intentionally required even if all criteria can be proven.
