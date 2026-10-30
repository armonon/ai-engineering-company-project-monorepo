/**
 * TrackFlow information-request form validation (Milestone 1).
 *
 * Field names, option values, and error messages are taken verbatim from
 * BRIEFING.md / docs/company-context/01-web-fundamentals.md. The pure
 * functions are exported for Node tests; the DOM wiring only runs in a
 * browser.
 */
(function (root) {
  "use strict";

  var COMMENTS_LIMIT = 500;

  var MESSAGES = {
    companyName: "Company name must have at least 2 characters",
    contactPerson: "Enter first and last name of contact",
    corporateEmail: "Enter a valid corporate email (example: name@company.com)",
    phone: "Phone must include country code (example: +1 213 555 0147)",
    companyWebsite: "If you include website, it must be a valid URL",
    mainOperatingCountry: "Select main operating country",
    productType: "Select the type of product you handle",
    monthlyShippingVolume: "Select estimated monthly volume",
    servicesOfInterest: "Select at least one service of interest",
    currentThreePL: "Indicate if you currently work with another logistics provider",
    privacyPolicy: "You must accept the privacy policy to continue",
  };

  var LOW_VOLUME_WARNING =
    "For volumes under 100 monthly shipments, our services might not be the most efficient solution. Are you sure you want to continue?";

  var OPTIONS = {
    mainOperatingCountry: ["United States", "Spain", "Both", "Other"],
    productType: ["Fashion", "Electronics", "Cosmetics", "Food", "Other"],
    monthlyShippingVolume: ["0-100", "101-500", "501-2000", "2000+", "Not sure"],
    servicesOfInterest: ["Warehousing", "Last mile", "Reverse logistics"],
    currentThreePL: ["Yes", "No", "Evaluating options"],
  };

  function trim(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function commentsError(value) {
    var length = typeof value === "string" ? value.length : 0;
    if (length <= COMMENTS_LIMIT) return "";
    return (
      "Comments cannot exceed 500 characters (" +
      (COMMENTS_LIMIT - length) +
      " remaining)"
    );
  }

  /** Returns the briefing's error message for one field, or "" when valid. */
  function validateField(name, value) {
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
        var url = trim(value);
        if (!url) return "";
        if (!/^https?:\/\//i.test(url)) return MESSAGES.companyWebsite;
        try {
          new URL(url);
          return "";
        } catch (error) {
          return MESSAGES.companyWebsite;
        }
      }
      case "mainOperatingCountry":
      case "productType":
      case "monthlyShippingVolume":
      case "currentThreePL":
        return OPTIONS[name].indexOf(value) >= 0 ? "" : MESSAGES[name];
      case "servicesOfInterest":
        return Array.isArray(value) &&
          value.some(function (service) {
            return OPTIONS.servicesOfInterest.indexOf(service) >= 0;
          })
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

  var FIELDS = [
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

  /** Validates every field; returns { valid, errors: { field: message } }. */
  function validateForm(values) {
    var errors = {};
    FIELDS.forEach(function (name) {
      var message = validateField(name, values[name]);
      if (message) errors[name] = message;
    });
    return { valid: Object.keys(errors).length === 0, errors: errors };
  }

  /** Briefing restriction: warn end-consumer-sized senders, but do not block. */
  function lowVolumeWarning(values) {
    return values.monthlyShippingVolume === "0-100" && Boolean(values.productType)
      ? LOW_VOLUME_WARNING
      : "";
  }

  function commentsRemaining(value) {
    return COMMENTS_LIMIT - (typeof value === "string" ? value.length : 0);
  }

  var api = {
    COMMENTS_LIMIT: COMMENTS_LIMIT,
    FIELDS: FIELDS,
    MESSAGES: MESSAGES,
    OPTIONS: OPTIONS,
    LOW_VOLUME_WARNING: LOW_VOLUME_WARNING,
    validateField: validateField,
    validateForm: validateForm,
    lowVolumeWarning: lowVolumeWarning,
    commentsRemaining: commentsRemaining,
  };

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (typeof document === "undefined") return;

  // ---------------------------------------------------------------- DOM --
  function readValues(form) {
    var data = new FormData(form);
    return {
      companyName: data.get("companyName") || "",
      contactPerson: data.get("contactPerson") || "",
      corporateEmail: data.get("corporateEmail") || "",
      phone: data.get("phone") || "",
      companyWebsite: data.get("companyWebsite") || "",
      mainOperatingCountry: data.get("mainOperatingCountry") || "",
      productType: data.get("productType") || "",
      monthlyShippingVolume: data.get("monthlyShippingVolume") || "",
      servicesOfInterest: data.getAll("servicesOfInterest"),
      currentThreePL: data.get("currentThreePL") || "",
      comments: data.get("comments") || "",
      privacyPolicy: data.get("privacyPolicy") === "accepted",
    };
  }

  function showError(form, name, message) {
    var error = document.getElementById(name + "-error");
    var controls = form.querySelectorAll('[name="' + name + '"]');
    if (error) error.textContent = message;
    controls.forEach(function (control) {
      var valid = !message && control.value !== "";
      control.setAttribute("aria-invalid", message ? "true" : "false");
      control.classList.toggle("border-red-600", Boolean(message));
      control.classList.toggle("border-emerald-600", valid);
      control.classList.toggle("border-slate-400", !message && !valid);
    });
  }

  function updateHints(form, values) {
    var counter = document.getElementById("comments-counter");
    if (counter) {
      counter.textContent = commentsRemaining(values.comments) + " characters remaining";
    }
    var warning = document.getElementById("volume-warning");
    if (warning) {
      var text = lowVolumeWarning(values);
      warning.textContent = text;
      warning.hidden = !text;
    }
  }

  function init() {
    var form = document.getElementById("information-request");
    if (!form) return;
    var success = document.getElementById("form-success");
    var touched = {};

    function check(name) {
      var values = readValues(form);
      showError(form, name, validateField(name, values[name]));
      updateHints(form, values);
    }

    form.addEventListener("focusout", function (event) {
      var name = event.target && event.target.name;
      if (!name) return;
      touched[name] = true;
      check(name);
    });

    form.addEventListener("input", function (event) {
      var name = event.target && event.target.name;
      if (!name) return;
      updateHints(form, readValues(form));
      if (touched[name] || name === "comments") check(name);
    });

    form.addEventListener("change", function (event) {
      var name = event.target && event.target.name;
      if (name) {
        touched[name] = true;
        check(name);
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var values = readValues(form);
      var result = validateForm(values);
      FIELDS.forEach(function (name) {
        touched[name] = true;
        showError(form, name, result.errors[name] || "");
      });
      updateHints(form, values);
      if (!result.valid) {
        var first = form.querySelector('[aria-invalid="true"]');
        if (first) first.focus();
        return;
      }
      form.hidden = true;
      success.hidden = false;
      success.focus();
    });

    form.addEventListener("reset", function () {
      touched = {};
      window.setTimeout(function () {
        FIELDS.forEach(function (name) {
          showError(form, name, "");
        });
        updateHints(form, readValues(form));
      });
    });

    updateHints(form, readValues(form));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(this);
