/**
 * Milestone 1 form rules, re-asserted after the migration to Next.js.
 *
 * These are the same cases the static site shipped in
 * uis/public-website/tests/validation.test.js. They are kept so the
 * migration cannot quietly change a message, an option value, or the
 * 500-character comment limit the briefing fixes.
 */
import assert from "node:assert/strict";
import test from "node:test";
import {
  COMMENTS_LIMIT,
  LOW_VOLUME_WARNING,
  MESSAGES,
  commentsRemaining,
  emptyApplication,
  lowVolumeWarning,
  validateField,
  validateForm,
  type ApplicationValues,
} from "../lib/applicationValidation.js";

const complete: ApplicationValues = {
  companyName: "Northwind Retail",
  contactPerson: "Ana Torres",
  corporateEmail: "ana@northwind.com",
  phone: "+1 213 555 0147",
  companyWebsite: "https://northwind.com",
  mainOperatingCountry: "United States",
  productType: "Fashion",
  monthlyShippingVolume: "501-2000",
  servicesOfInterest: ["Warehousing"],
  currentThreePL: "No",
  comments: "",
  privacyPolicy: true,
};

test("a complete request passes", () => {
  assert.deepEqual(validateForm(complete), { valid: true, errors: {} });
});

test("an empty request reports every required field with the briefing message", () => {
  const { valid, errors } = validateForm(emptyApplication);
  assert.equal(valid, false);
  for (const field of [
    "companyName",
    "contactPerson",
    "corporateEmail",
    "phone",
    "mainOperatingCountry",
    "productType",
    "monthlyShippingVolume",
    "servicesOfInterest",
    "currentThreePL",
    "privacyPolicy",
  ] as const) {
    assert.equal(errors[field], MESSAGES[field]);
  }
  // The two optional fields must not be reported.
  assert.equal(errors.companyWebsite, undefined);
  assert.equal(errors.comments, undefined);
});

test("company name needs at least 2 characters", () => {
  assert.equal(validateField("companyName", "A"), MESSAGES.companyName);
  assert.equal(validateField("companyName", "AB"), "");
  assert.equal(validateField("companyName", "  AB  "), "");
});

test("contact person needs first and last name", () => {
  assert.equal(validateField("contactPerson", "Ana"), MESSAGES.contactPerson);
  assert.equal(validateField("contactPerson", "Ana Torres"), "");
});

test("email needs @ and a domain", () => {
  assert.equal(
    validateField("corporateEmail", "ana@northwind"),
    MESSAGES.corporateEmail,
  );
  assert.equal(validateField("corporateEmail", "ana@northwind.com"), "");
});

test("phone must start with + and a country code", () => {
  assert.equal(validateField("phone", "213 555 0147"), MESSAGES.phone);
  assert.equal(validateField("phone", "+1 213 555 0147"), "");
  assert.equal(validateField("phone", "+34 976 123 456"), "");
});

test("website is optional but must be http(s) when given", () => {
  assert.equal(validateField("companyWebsite", ""), "");
  assert.equal(
    validateField("companyWebsite", "northwind.com"),
    MESSAGES.companyWebsite,
  );
  assert.equal(validateField("companyWebsite", "https://northwind.com"), "");
});

test("selects accept only the briefing's option values", () => {
  assert.equal(validateField("mainOperatingCountry", "France"), MESSAGES.mainOperatingCountry);
  assert.equal(validateField("mainOperatingCountry", "Both"), "");
  assert.equal(validateField("productType", "Furniture"), MESSAGES.productType);
  assert.equal(validateField("productType", "Cosmetics"), "");
  assert.equal(validateField("monthlyShippingVolume", "many"), MESSAGES.monthlyShippingVolume);
  assert.equal(validateField("monthlyShippingVolume", "2000+"), "");
  assert.equal(validateField("currentThreePL", "maybe"), MESSAGES.currentThreePL);
  assert.equal(validateField("currentThreePL", "Evaluating options"), "");
});

test("at least one service of interest is required", () => {
  assert.equal(
    validateField("servicesOfInterest", []),
    MESSAGES.servicesOfInterest,
  );
  assert.equal(
    validateField("servicesOfInterest", ["Nothing"]),
    MESSAGES.servicesOfInterest,
  );
  assert.equal(validateField("servicesOfInterest", ["Last mile"]), "");
});

test("comments are limited to 500 characters with a remaining count", () => {
  assert.equal(validateField("comments", "x".repeat(COMMENTS_LIMIT)), "");
  assert.equal(commentsRemaining("x".repeat(100)), 400);
  const tooLong = "x".repeat(COMMENTS_LIMIT + 3);
  assert.equal(
    validateField("comments", tooLong),
    "Comments cannot exceed 500 characters (-3 remaining)",
  );
  assert.equal(commentsRemaining(tooLong), -3);
});

test("low volume warns without blocking submission", () => {
  const lowVolume: ApplicationValues = {
    ...complete,
    monthlyShippingVolume: "0-100",
  };
  assert.equal(lowVolumeWarning(lowVolume), LOW_VOLUME_WARNING);
  // A warning is not an error: the request still validates.
  assert.equal(validateForm(lowVolume).valid, true);
  assert.equal(lowVolumeWarning(complete), "");
});
