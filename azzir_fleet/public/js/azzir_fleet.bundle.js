// Copyright (c) 2026, Azzir and contributors
// Single desk-wide bundle for all globally-included Azzir Fleet scripts.
//
// Bundling gives this a content-hashed filename on every build, so browsers and
// the desk service worker can't serve a stale copy across devices (the reason
// the raw /assets/*.js includes showed up inconsistently after deploys).

import "./azzir_compat";
import "./azzir_alias";
import "./azzir_stock";
import "./azzir_vat";
import "./azzir_tax";
