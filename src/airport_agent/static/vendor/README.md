# Vendored browser libraries

Copied unchanged from the npm registry, so the page makes no third-party request at runtime and
there is no build step. To update one: download the new tarball from the registry, check its
`integrity` value, copy the same file here, and update this table.

| File | Library | Version | From (npm tarball) | License | SHA-256 of the file |
|---|---|---|---|---|---|
| `marked.umd.js` | [marked](https://github.com/markedjs/marked): Markdown to HTML | 18.1.0 | `marked-18.1.0.tgz`, `lib/marked.umd.js` (already minified) | MIT (`LICENSE-marked.txt`) | `f424dcb508fdf93e0137a970cfce8f3207ea2e3f37eca5f7556a52875683632a` |
| `purify.min.js` | [DOMPurify](https://github.com/cure53/DOMPurify): HTML sanitiser | 3.4.16 | `dompurify-3.4.16.tgz`, `dist/purify.min.js` | Apache-2.0 or MPL-2.0; used under Apache-2.0 (`LICENSE-dompurify.txt`) | `2c90a9b46d6463f26038a29b686e82bc91de01fdac9d5229e7cfe3b360134ea2` |

Model text is untrusted: the page always passes `marked`'s output through `DOMPurify` before it
is shown (`render()` in `../app.js`).
