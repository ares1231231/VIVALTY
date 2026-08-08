/**
 * GA4 + Google Ads consent mode — loads only after cookie consent ("all").
 * Conversion events: sign_up, generate_lead (importable in Google Ads from GA4).
 */
(function () {
  const CONSENT_KEY = "vivalty_cookie_consent";
  const SCRIPT_ID = "vivalty-gtag-js";

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

  function gtag() {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(arguments);
  }

  function ensureGtagFn() {
    if (typeof window.gtag !== "function") {
      window.gtag = gtag;
    }
  }

  function loadGtagScript(measurementId, adsId, onLoad) {
    if (document.getElementById(SCRIPT_ID)) {
      onLoad();
      return;
    }
    const s = document.createElement("script");
    s.id = SCRIPT_ID;
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    s.onload = onLoad;
    s.onerror = onLoad;
    document.head.appendChild(s);
  }

  let initialized = false;
  let queue = [];

  function grantConsentAndConfigure(cfg) {
    ensureGtagFn();
    window.gtag("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
    });
    window.gtag("js", new Date());
    window.gtag("config", cfg.ga4Id, { send_page_view: true });
    if (cfg.adsId) {
      window.gtag("config", cfg.adsId);
    }
    initialized = true;
    queue.forEach((item) => fireEvent(item.name, item.params));
    queue = [];
  }

  function fireEvent(name, params) {
    if (!initialized || typeof window.gtag !== "function") {
      queue.push({ name, params: params || {} });
      return;
    }
    window.gtag("event", name, params || {});
  }

  function maybeInit() {
    const cfg = readConfig();
    if (!cfg || !cfg.ga4Id) return;
    if (!hasAnalyticsConsent()) return;

    loadGtagScript(cfg.ga4Id, cfg.adsId || "", () => {
      grantConsentAndConfigure(cfg);
      (cfg.pending || []).forEach((item) => {
        fireEvent(item.name, item.params);
      });
    });
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
    maybeInit();
    scanPendingMarkers(document);
  });

  document.addEventListener("vivalty:cookie-consent", (e) => {
    if (e.detail?.value === "all") maybeInit();
  });

  document.addEventListener("htmx:afterSettle", (e) => {
    const root = e.detail?.elt || document;
    scanPendingMarkers(root);
  });
})();
