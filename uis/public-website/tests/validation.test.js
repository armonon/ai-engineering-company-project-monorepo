const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

const {
  FIELDS,
  OPTIONS,
  LOW_VOLUME_WARNING,
  validateField,
  validateForm,
  lowVolumeWarning,
  commentsRemaining,
} = require("../validation.js");

const root = join(__dirname, "..");
const VALID = {
  companyName: "ModaViva",
  contactPerson: "Ana Whitfield",
  corporateEmail: "ana@modaviva.com",
  phone: "+1 213 555 0147",
  companyWebsite: "https://modaviva.com",
  mainOperatingCountry: "Spain",
  productType: "Fashion",
  monthlyShippingVolume: "501-2000",
  servicesOfInterest: ["Warehousing", "Reverse logistics"],
  currentThreePL: "Evaluating options",
  comments: "",
  privacyPolicy: true,
};

test("a complete request passes", () => {
  assert.deepEqual(validateForm(VALID), { valid: true, errors: {} });
});

test("an empty request reports every required field with the briefing message", () => {
  const { valid, errors } = validateForm({});
  assert.equal(valid, false);
  assert.deepEqual(errors, {
    companyName: "Company name must have at least 2 characters",
    contactPerson: "Enter first and last name of contact",
    corporateEmail: "Enter a valid corporate email (example: name@company.com)",
    phone: "Phone must include country code (example: +1 213 555 0147)",
    mainOperatingCountry: "Select main operating country",
    productType: "Select the type of product you handle",
    monthlyShippingVolume: "Select estimated monthly volume",
    servicesOfInterest: "Select at least one service of interest",
    currentThreePL: "Indicate if you currently work with another logistics provider",
    privacyPolicy: "You must accept the privacy policy to continue",
  });
});

test("company name needs at least 2 characters", () => {
  assert.notEqual(validateField("companyName", "A"), "");
  assert.equal(validateField("companyName", "AB"), "");
});

test("contact person needs first and last name", () => {
  assert.notEqual(validateField("contactPerson", "Ana"), "");
  assert.equal(validateField("contactPerson", "Ana Whitfield"), "");
});

test("email needs @ and a domain", () => {
  assert.notEqual(validateField("corporateEmail", "ana@"), "");
  assert.notEqual(validateField("corporateEmail", "ana.modaviva.com"), "");
  assert.equal(validateField("corporateEmail", "ana@modaviva.com"), "");
});

test("phone must start with + and a country code", () => {
  assert.notEqual(validateField("phone", "213 555 0147"), "");
  assert.equal(validateField("phone", "+1 213 555 0147"), "");
  assert.equal(validateField("phone", "+34 976 123 456"), "");
});

test("website is optional but must be http(s) when given", () => {
  assert.equal(validateField("companyWebsite", ""), "");
  assert.notEqual(validateField("companyWebsite", "modaviva.com"), "");
  assert.equal(validateField("companyWebsite", "http://modaviva.com"), "");
});

test("selects accept only the briefing's option values", () => {
  assert.deepEqual(OPTIONS.mainOperatingCountry, ["United States", "Spain", "Both", "Other"]);
  assert.deepEqual(OPTIONS.monthlyShippingVolume, ["0-100", "101-500", "501-2000", "2000+", "Not sure"]);
  assert.notEqual(validateField("mainOperatingCountry", "Mexico"), "");
});

test("comments are limited to 500 characters with a remaining count", () => {
  assert.equal(validateField("comments", "x".repeat(500)), "");
  assert.equal(
    validateField("comments", "x".repeat(503)),
    "Comments cannot exceed 500 characters (-3 remaining)",
  );
  assert.equal(commentsRemaining("x".repeat(120)), 380);
});

test("low volume warns without blocking submission", () => {
  const lowVolume = { ...VALID, monthlyShippingVolume: "0-100" };
  assert.equal(lowVolumeWarning(lowVolume), LOW_VOLUME_WARNING);
  assert.equal(validateForm(lowVolume).valid, true);
  assert.equal(lowVolumeWarning(VALID), "");
});

test("application.html has a labelled control for every briefing field", () => {
  const html = readFileSync(join(root, "application.html"), "utf8");
  for (const field of FIELDS) {
    assert.match(html, new RegExp(`name="${field}"`), field);
    assert.match(html, new RegExp(`id="${field}-error"`), `${field} error slot`);
  }
  for (const id of ["companyName", "contactPerson", "corporateEmail", "phone", "companyWebsite",
    "mainOperatingCountry", "productType", "monthlyShippingVolume", "comments"]) {
    assert.match(html, new RegExp(`<label for="${id}"`), `${id} label`);
  }
  assert.match(html, /type="reset"/);
  assert.match(html, /Thank you for your interest in TrackFlow!/);
});

test("index.html follows the briefing's content and Schema.org markup", () => {
  const html = readFileSync(join(root, "index.html"), "utf8");
  for (const text of [
    "Logistics that scales with your e-commerce",
    "Warehouse in Los Angeles",
    "Carriers: UPS, FedEx, DHL",
    "Carriers: MRW, SEUR, DHL",
    "comercial@trackflow.com",
    "+1 213 555 0147",
    "+34 976 123 456",
    "© 2025 TrackFlow. All rights reserved.",
  ]) {
    assert.ok(html.includes(text), text);
  }
  const schema = JSON.parse(html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1]);
  assert.equal(schema["@type"], "Organization");
  assert.deepEqual(schema.address.map((a) => a.addressLocality), ["Los Angeles", "Zaragoza"]);
  assert.ok(!/Mexico|Monterrey/.test(html));
});
