#!/usr/bin/env node

const EXIT = Object.freeze({
  OK: 0,
  READ_FAILURE: 1,
  API_REFUSAL: 2,
  WRITE_UNKNOWN: 3,
  USAGE: 64,
});

const WRITE_COMMANDS = new Set(["inbound", "outbound"]);

function fail(message, code = EXIT.USAGE) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

function parseArgs(argv) {
  const [command, ...rest] = argv;
  const options = {};

  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index];
    if (!item.startsWith("--")) {
      fail(`Unexpected argument: ${item}`);
    }
    const key = item.slice(2);
    if (key === "confirmed") {
      options.confirmed = true;
      continue;
    }
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--")) {
      fail(`Missing value for --${key}`);
    }
    options[key] = value;
    index += 1;
  }

  return { command, options };
}

function required(options, key) {
  const value = options[key];
  if (typeof value !== "string" || value.trim() === "") {
    fail(`Missing required option --${key}`);
  }
  return value.trim();
}

function positiveInteger(value, label) {
  if (!/^\d+$/.test(value)) {
    fail(`${label} must be a positive integer.`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    fail(`${label} must be a positive integer.`);
  }
  return parsed;
}

function warehouse(value) {
  if (!new Set(["LA", "ZGZ"]).has(value)) {
    fail("warehouse must be LA or ZGZ.");
  }
  return value;
}

function configuration() {
  const baseUrl = process.env.TRACKFLOW_API_ORIGIN?.trim().replace(/\/+$/, "");
  const email = process.env.TRACKFLOW_API_EMAIL?.trim();
  const password = process.env.TRACKFLOW_API_PASSWORD;

  if (!baseUrl || !email || !password) {
    fail(
      "Missing TRACKFLOW_API_ORIGIN, TRACKFLOW_API_EMAIL, or " +
        "TRACKFLOW_API_PASSWORD in the private workspace environment.",
      EXIT.READ_FAILURE,
    );
  }

  let parsed;
  try {
    parsed = new URL(baseUrl);
  } catch {
    fail("TRACKFLOW_API_ORIGIN must be an absolute HTTP(S) URL.", EXIT.READ_FAILURE);
  }
  if (!new Set(["http:", "https:"]).has(parsed.protocol)) {
    fail("TRACKFLOW_API_ORIGIN must use HTTP or HTTPS.", EXIT.READ_FAILURE);
  }

  return { baseUrl, email, password };
}

async function fetchJson(url, init, { isWrite = false } = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...init,
      signal: AbortSignal.timeout(15_000),
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    if (isWrite) {
      fail(
        `WRITE_OUTCOME_UNKNOWN: ${reason}. DO NOT RETRY. Inspect the movement feed.`,
        EXIT.WRITE_UNKNOWN,
      );
    }
    fail(`READ_FAILED: ${reason}`, EXIT.READ_FAILURE);
  }

  const text = await response.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { detail: text || "The API returned an empty non-JSON response." };
  }

  if (!response.ok) {
    process.stderr.write(`API_ERROR status=${response.status}\n`);
    process.stderr.write(`${JSON.stringify(body, null, 2)}\n`);
    process.exit(isWrite ? EXIT.API_REFUSAL : EXIT.READ_FAILURE);
  }

  return body;
}

async function authenticate(config) {
  const body = await fetchJson(`${config.baseUrl}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: config.email, password: config.password }),
  });

  if (!body || typeof body.access_token !== "string" || !body.access_token) {
    fail("Authentication succeeded without a usable access token.", EXIT.READ_FAILURE);
  }
  return body.access_token;
}

function authHeaders(token, json = false) {
  return {
    authorization: `Bearer ${token}`,
    ...(json ? { "content-type": "application/json" } : {}),
  };
}

async function apiGet(config, token, path) {
  return fetchJson(`${config.baseUrl}${path}`, {
    headers: authHeaders(token),
  });
}

async function exactSku(config, token, options) {
  const id = positiveInteger(required(options, "sku-id"), "sku-id");
  const code = required(options, "sku-code");
  const expectedWarehouse = warehouse(required(options, "warehouse"));
  const product = await apiGet(config, token, `/inventory/products/${id}`);

  if (product.sku !== code) {
    fail(
      `SKU validation failed: id ${id} is ${product.sku}, not ${code}. No write sent.`,
    );
  }
  if (product.warehouse !== expectedWarehouse) {
    fail(
      `Warehouse validation failed: ${code} belongs to ${product.warehouse}, ` +
        `not ${expectedWarehouse}. No write sent.`,
    );
  }
  return { id, code, warehouse: expectedWarehouse, product };
}

function printJson(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (!command) {
    fail("Command required: products, product, movements, inbound, or outbound.");
  }
  if (!new Set(["products", "product", "movements", "inbound", "outbound"]).has(command)) {
    fail(`Unknown command: ${command}`);
  }
  if (WRITE_COMMANDS.has(command) && options.confirmed !== true) {
    fail("Write blocked: --confirmed is required after a separate explicit approval.");
  }

  const config = configuration();
  const token = await authenticate(config);

  if (command === "products") {
    const query = new URLSearchParams();
    if (options.warehouse) query.set("warehouse", warehouse(options.warehouse));
    const suffix = query.size ? `?${query}` : "";
    let products = await apiGet(config, token, `/inventory/products${suffix}`);
    if (options.query) {
      const needle = options.query.trim().toLowerCase();
      products = products.filter((product) =>
        [product.sku, product.name, product.client_name, product.category]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(needle)),
      );
    }
    printJson(products);
    return;
  }

  if (command === "product") {
    const id = positiveInteger(required(options, "id"), "id");
    printJson(await apiGet(config, token, `/inventory/products/${id}`));
    return;
  }

  if (command === "movements") {
    const query = new URLSearchParams();
    if (options.warehouse) query.set("warehouse", warehouse(options.warehouse));
    if (options["movement-type"]) {
      const movementType = options["movement-type"];
      if (!new Set(["entry", "exit"]).has(movementType)) {
        fail("movement-type must be entry or exit.");
      }
      query.set("movement_type", movementType);
    }
    const suffix = query.size ? `?${query}` : "";
    printJson(await apiGet(config, token, `/inventory/orders${suffix}`));
    return;
  }

  const sku = await exactSku(config, token, options);
  const quantity = positiveInteger(required(options, "quantity"), "quantity");

  if (command === "inbound") {
    const reference = required(options, "reference");
    const result = await fetchJson(
      `${config.baseUrl}/inventory/orders/inbound`,
      {
        method: "POST",
        headers: authHeaders(token, true),
        body: JSON.stringify({
          sku_id: sku.id,
          quantity,
          reference,
          warehouse: sku.warehouse,
        }),
      },
      { isWrite: true },
    );
    printJson(result);
    return;
  }

  const exitType = required(options, "exit-type");
  if (!new Set(["dispatch", "loss"]).has(exitType)) {
    fail("exit-type must be dispatch or loss.");
  }
  const tracking = options["tracking-number"]?.trim() || null;
  if (exitType === "dispatch" && !tracking) {
    fail("tracking-number is required for a dispatch.");
  }
  if (exitType === "loss" && tracking) {
    fail("tracking-number must be omitted for a loss.");
  }

  const result = await fetchJson(
    `${config.baseUrl}/inventory/orders/outbound`,
    {
      method: "POST",
      headers: authHeaders(token, true),
      body: JSON.stringify({
        sku_id: sku.id,
        quantity,
        exit_type: exitType,
        tracking_number: tracking,
        warehouse: sku.warehouse,
      }),
    },
    { isWrite: true },
  );
  printJson(result);
}

await main();
