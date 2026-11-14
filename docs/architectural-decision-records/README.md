# Architectural decision records

One file for each decision: what was decided, when, who decided, and the evidence that settled it. A record sits beside the `CLAUDE.md` rule that states the decision today and does not replace it.

This folder started with the chart, on 2026-11-12. Decisions about the site itself live in trailhead's records (zimmertr/trailhead `docs/architectural-decision-records/`).

## Write a record

- Copy [`0000-template.md`](0000-template.md) to `NNNN-slug.md` with the next free number. Numbers have four digits and are never reused.
- The title is the decision, as one sentence.
- Take the date and the decider from the conversation or issue that settled it, quoting the decider where the words exist.
- Give every observation the date it was made.
- Link the record from its `CLAUDE.md` rule as ` Record: [NNNN](docs/architectural-decision-records/NNNN-slug.md)`.
- A decision ships in the same PR as its record.

## Supersede a record

A new record that reverses an old one says `Supersedes NNNN` in its status line. The old record changes its status line to `Superseded by NNNN` and nothing else.

## Index

| Record | Decision | Date | Status |
|---|---|---|---|
| [0001](0001-the-chart-goes-through-yggdrasils-modules.md) | The chart is checked, pushed and released by yggdrasil's modules, with the `appVersion` in `Chart.yaml` | 2026-11-12 | Accepted. Its PR check superseded by 0005 |
| [0002](0002-a-canary-is-promoted-on-scripted-checks-alone.md) | A canary is promoted on scripted checks alone, never on live traffic | 2026-11-12 | Accepted |
| [0003](0003-one-database-login-per-service.md) | Each service connects to the database as its own login, from a Secret made by hand | 2026-11-12 | Accepted |
| [0004](0004-only-the-gateway-reaches-the-services.md) | Only the ingress gateway reaches web, api and admin, and only the services reach the database | 2026-11-12 | Accepted |
| [0005](0005-the-charts-checks-are-helm-unittest-suites.md) | The chart's checks are helm-unittest suites, run by yggdrasil's chart module | 2026-11-13 | Accepted. Supersedes 0001's PR check |
