/**
 * Information-request form rules, migrated from the Milestone 1 static
 * site (uis/public-website/validation.js).
 *
 * Messages, option values, and the 500-character comment limit are
 * carried over verbatim from BRIEFING.md /
 * docs/company-context/01-web-fundamentals.md — the migration changes the
 * runtime, not the contract. These functions are pure so the rules can be
 * tested without a DOM.
 */

export const COMMENTS_LIMIT = 500;

export const MESSAGES = {
  companyName: "Company name must have at least 2 characters",
  contactPerson: "Enter first and last name of contact",
  corporateEmail: "Enter a valid corporate email (example: name@company.com)",
  phone: "Phone must include country code (example: +1 213 555 0147)",
  companyWebsite: "If you include website, it must be a valid URL",
  mainOperatingCountry: "Select main operating country",
  productType: "Select the type of product you handle",
  monthlyShippingVolume: "Select estimated monthly volume",
  servicesOfInterest: "Select at least one service of interest",
  currentThreePL:
    "Indicate if you currently work with another logistics provider",
  privacyPolicy: "You must accept the privacy policy to continue",
} as const;

export const LOW_VOLUME_WARNING =
  "For volumes under 100 monthly shipments, our services might not be the most efficient solution. Are you sure you want to continue?";

export const OPTIONS = {
  mainOperatingCountry: ["United States", "Spain", "Both", "Other"],
  productType: ["Fashion", "Electronics", "Cosmetics", "Food", "Other"],
  monthlyShippingVolume: ["0-100", "101-500", "501-2000", "2000+", "Not sure"],
  servicesOfInterest: ["Warehousing", "Last mile", "Reverse logistics"],
  currentThreePL: ["Yes", "No", "Evaluating options"],
} as const;

export interface ApplicationValues {
  companyName: string;
  contactPerson: string;
  corporateEmail: string;
  phone: string;
  companyWebsite: string;
  mainOperatingCountry: string;
  productType: string;
  monthlyShippingVolume: string;
  servicesOfInterest: string[];
  currentThreePL: string;
  comments: string;
  privacyPolicy: boolean;
}

export type FieldName = keyof ApplicationValues;

export const FIELDS: FieldName[] = [
  "companyName",
  "contactPerson",
  "corporateEmail",
  "phone",
  "companyWebsite",
  "mainOperatingCountry",
  "productType",
  "monthlyShippingVolume",
  "servicesOfInterest",
  "currentThreePL",
  "comments",
  "privacyPolicy",
];

export const emptyApplication: ApplicationValues = {
  companyName: "",
  contactPerson: "",
  corporateEmail: "",
  phone: "",
  companyWebsite: "",
  mainOperatingCountry: "",
  productType: "",
  monthlyShippingVolume: "",
  servicesOfInterest: [],
  currentThreePL: "",
  comments: "",
  privacyPolicy: false,
};

function trim(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function commentsError(value: unknown): string {
  const length = typeof value === "string" ? value.length : 0;
  if (length <= COMMENTS_LIMIT) return "";
  return `Comments cannot exceed 500 characters (${COMMENTS_LIMIT - length} remaining)`;
}

function inOptions(name: keyof typeof OPTIONS, value: unknown): boolean {
  return (OPTIONS[name] as readonly string[]).indexOf(String(value)) >= 0;
}

/** The briefing's error message for one field, or "" when it is valid. */
export function validateField(name: FieldName, value: unknown): string {
  switch (name) {
    case "companyName":
      return trim(value).length >= 2 ? "" : MESSAGES.companyName;
    case "contactPerson":
      return trim(value).split(/\s+/).filter(Boolean).length >= 2
        ? ""
        : MESSAGES.contactPerson;
    case "corporateEmail":
      return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(trim(value))
        ? ""
        : MESSAGES.corporateEmail;
    case "phone":
      return /^\+\d{1,3}[\s-]?\d[\d\s-]{5,}$/.test(trim(value))
        ? ""
        : MESSAGES.phone;
    case "companyWebsite": {
      const url = trim(value);
      if (!url) return "";
      if (!/^https?:\/\//i.test(url)) return MESSAGES.companyWebsite;
      try {
        new URL(url);
        return "";
      } catch {
        return MESSAGES.companyWebsite;
      }
    }
    case "mainOperatingCountry":
    case "productType":
    case "monthlyShippingVolume":
    case "currentThreePL":
      return inOptions(name, value) ? "" : MESSAGES[name];
    case "servicesOfInterest":
      return Array.isArray(value) &&
        value.some((service) => inOptions("servicesOfInterest", service))
        ? ""
        : MESSAGES.servicesOfInterest;
    case "comments":
      return commentsError(value);
    case "privacyPolicy":
      return value === true ? "" : MESSAGES.privacyPolicy;
    default:
      return "";
  }
}

export interface ValidationOutcome {
  valid: boolean;
  errors: Partial<Record<FieldName, string>>;
}

/** Validates every field; returns { valid, errors: { field: message } }. */
export function validateForm(values: ApplicationValues): ValidationOutcome {
  const errors: Partial<Record<FieldName, string>> = {};
  for (const name of FIELDS) {
    const message = validateField(name, values[name]);
    if (message) errors[name] = message;
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

/** Briefing restriction: warn end-consumer-sized senders, but do not block. */
export function lowVolumeWarning(values: ApplicationValues): string {
  return values.monthlyShippingVolume === "0-100" && Boolean(values.productType)
    ? LOW_VOLUME_WARNING
    : "";
}

export function commentsRemaining(value: string): number {
  return COMMENTS_LIMIT - (typeof value === "string" ? value.length : 0);
}
