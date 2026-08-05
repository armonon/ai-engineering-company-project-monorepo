const form = document.querySelector("#request-form");
const comments = document.querySelector("#comments");
const counter = document.querySelector("#comments-count");

const setError = (fieldId, message) => {
  const error = document.querySelector(`#${fieldId}-error`);
  if (error) error.textContent = message;
};

const clearErrors = () => {
  document.querySelectorAll(".field-error").forEach((element) => {
    element.textContent = "";
  });
  document.querySelector("#form-status").textContent = "";
};

comments.addEventListener("input", () => {
  counter.textContent = `${comments.value.length} / 500`;
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearErrors();
  const data = new FormData(form);
  let valid = true;

  const company = String(data.get("company") ?? "").trim();
  if (company.length < 2) {
    setError("company", "Company name must have at least 2 characters");
    valid = false;
  }

  const contactPerson = String(data.get("contactPerson") ?? "").trim();
  if (contactPerson.split(/\s+/).filter(Boolean).length < 2) {
    setError("contact-person", "Enter first and last name of contact");
    valid = false;
  }

  const email = String(data.get("email") ?? "").trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setError("email", "Enter a valid corporate email (example: name@company.com)");
    valid = false;
  }

  const phone = String(data.get("phone") ?? "").trim();
  if (!/^\+\d{1,3}[\s-][\d\s()-]{6,}$/.test(phone)) {
    setError("phone", "Phone must include country code (example: +52 81 1234 5678)");
    valid = false;
  }

  const website = String(data.get("website") ?? "").trim();
  if (website && !/^https?:\/\/.+/i.test(website)) {
    setError("website", "If you include website, it must be a valid URL");
    valid = false;
  }

  if (!data.get("country")) {
    setError("country", "Select main operating country");
    valid = false;
  }
  if (!data.get("productType")) {
    setError("product-type", "Select the main product type");
    valid = false;
  }
  if (!data.get("volume")) {
    setError("volume", "Select estimated monthly shipping volume");
    valid = false;
  }
  if (data.getAll("services").length === 0) {
    setError("services", "Select at least one service of interest");
    valid = false;
  }
  if (!data.get("provider")) {
    setError("provider", "Select your current 3PL situation");
    valid = false;
  }
  if (comments.value.length > 500) {
    setError("comments", "Comments cannot exceed 500 characters");
    valid = false;
  }
  if (!data.get("privacy")) {
    setError("privacy", "You must accept the privacy policy");
    valid = false;
  }

  if (valid) {
    const status = document.querySelector("#form-status");
    status.textContent = "Thank you. The TrackFlow Commercial team will contact you soon.";
    status.className = "mt-4 text-center font-semibold text-teal-700";
    form.reset();
    counter.textContent = "0 / 500";
  } else {
    document.querySelector(".field-error:not(:empty)")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
});
