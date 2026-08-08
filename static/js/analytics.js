/**
 * GA4 conversions + consent updates (gtag.js is loaded from analytics.html).
 * Conversion events: sign_up, generate_lead (importable in Google Ads from GA4).
 */
(function () {
  const CONSENT_KEY = "vivalty_cookie_consent";

  function readConfig() {
    const el = document.getElementById("vivalty-analytics-config");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (_) {
      return null;
    }
  }

  function hasAnalyticsConsent() {
    return localStorage.getItem(CONSENT_KEY) === "all";
  }

  let consentGranted = false;
  let queue = [];

  function grantConsentStorage() {
    if (consentGranted || typeof window.gtag !== "function") return;
    window.gtag("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
    });
    consentGranted = true;
    queue.forEach((item) => {
      window.gtag("event", item.name, item.params);
      if (item.name === "sign_up") ackSignUpSent();
    });
    queue = [];
  }

  function fireEvent(name, params) {
    const payload = params || {};
    if (!consentGranted || typeof window.gtag !== "function") {
      queue.push({ name, params: payload });
      return;
    }
    window.gtag("event", name, payload);
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function ackSignUpSent() {
    const url = document.querySelector("[data-vivalty-analytics-ack-sign-up]");
    if (!url) return;
    fetch(url.getAttribute("data-vivalty-analytics-ack-sign-up"), {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
    }).catch(() => {});
  }

  function flushPendingFromConfig(cfg) {
    if (!cfg?.pending?.length) return;
    cfg.pending.forEach((item) => {
      if (!consentGranted) {
        fireEvent(item.name, item.params);
        return;
      }
      fireEvent(item.name, item.params);
      if (item.name === "sign_up") ackSignUpSent();
    });
  }

  function syncConsentState() {
    if (!hasAnalyticsConsent()) return;
    grantConsentStorage();
    flushPendingFromConfig(readConfig());
  }

  function trackFromElement(el) {
    const name = el.getAttribute("data-vivalty-analytics-event");
    if (!name) return;
    let params = {};
    const raw = el.getAttribute("data-vivalty-analytics-params");
    if (raw) {
      try {
        params = JSON.parse(raw);
      } catch (_) {
        /* ignore */
      }
    }
    fireEvent(name, params);
  }

  function scanPendingMarkers(root) {
    root.querySelectorAll("[data-vivalty-analytics-event]").forEach((el) => {
      if (el.getAttribute("data-vivalty-analytics-fired") === "1") return;
      el.setAttribute("data-vivalty-analytics-fired", "1");
      trackFromElement(el);
    });
  }

  window.VivaltyAnalytics = { track: fireEvent };

  document.addEventListener("DOMContentLoaded", () => {
    syncConsentState();
    scanPendingMarkers(document);
  });

  document.addEventListener("vivalty:cookie-consent", (e) => {
    if (e.detail?.value === "all") syncConsentState();
  });

  document.addEventListener("htmx:afterSettle", (e) => {
    const root = e.detail?.elt || document;
    scanPendingMarkers(root);
  });
})();
