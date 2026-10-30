# `public-website` — TrackFlow public website (Milestone 1)

Static landing page and information-request form built from the official
Milestone 1 briefing ([`docs/company-context/01-web-fundamentals.md`](../../docs/company-context/01-web-fundamentals.md);
company facts in the root [`BRIEFING.md`](../../BRIEFING.md)).

| File | Purpose |
|---|---|
| `index.html` | Landing page: Header, Hero, Services, Coverage, Why TrackFlow, Contact, Footer — in the briefing's order — with the required Schema.org `Organization` markup |
| `application.html` | Information-request form with every briefing field, grouped with `<fieldset>`/`<legend>` |
| `validation.js` | Real-time (blur/change) and submit validation with the briefing's exact error messages, 500-character counter, low-volume warning, success message, and clear-form reset |
| `tailwind.css` | Tailwind CSS v4 utilities compiled from `src/input.css` (no hand-written CSS) |

## Run (Codespaces-compatible)

From the repository root:

```bash
npx --yes http-server@14.1.1 uis/public-website -p 3000 -a 0.0.0.0 -c-1
```

Then open port 3000 (in Codespaces, set the forwarded port's visibility to
**Public** for PageSpeed Insights).

## Develop

```bash
npm run build:css --workspace @trackflow/public-website   # regenerate tailwind.css after changing classes
npm run test --workspace @trackflow/public-website        # validation + content tests
```

Base language: English. The form targets e-commerce companies outsourcing
logistics, not end consumers tracking a parcel.
