(() => {
  "use strict";

  const form = document.getElementById("search-form");
  const searchButton = document.getElementById("search-button");
  const formError = document.getElementById("form-error");

  const progressCard = document.getElementById("progress-card");
  const progressSteps = Array.from(document.querySelectorAll("#progress-steps li"));

  const resultsSection = document.getElementById("results-section");
  const summaryCard = document.getElementById("summary-card");
  const sourcesPanel = document.getElementById("sources-panel");
  const resultsToolbar = document.getElementById("results-toolbar");
  const sortSelect = document.getElementById("sort-select");
  const resultsGrid = document.getElementById("results-grid");
  const noResultsBlock = document.getElementById("no-results");
  const noResultsSuggestions = document.getElementById("no-results-suggestions");

  const NOT_VERIFIED = "Not verified";
  const NOT_PUBLIC = "Not publicly available";

  let currentResults = [];
  let progressTimer = null;

  function show(el) {
    el.hidden = false;
  }
  function hide(el) {
    el.hidden = true;
  }

  function formatMoney(value) {
    if (value === null || value === undefined) return null;
    return "₹" + Number(value).toLocaleString("en-IN");
  }

  function formatTimestamp(iso) {
    if (!iso) return NOT_VERIFIED;
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function collectFormData() {
    const data = new FormData(form);
    const payload = {
      area: (data.get("area") || "").trim(),
      property_type: data.get("property_type"),
      bhk: data.get("bhk"),
      furnishing: data.get("furnishing"),
      parking: data.get("parking"),
      lift: data.get("lift"),
      water: data.get("water"),
      brokerage: data.get("brokerage"),
      food_preference: data.get("food_preference"),
    };
    const minRent = data.get("min_rent");
    const maxRent = data.get("max_rent");
    if (minRent) payload.min_rent = parseInt(minRent, 10);
    if (maxRent) payload.max_rent = parseInt(maxRent, 10);
    return payload;
  }

  function validate(payload) {
    if (!payload.area) {
      return "Please enter an area or locality to search.";
    }
    if (payload.min_rent != null && payload.max_rent != null && payload.min_rent > payload.max_rent) {
      return "Minimum rent cannot be greater than maximum rent.";
    }
    return null;
  }

  const PROGRESS_SEQUENCE = ["queries", "search", "check", "normalize", "dedupe", "rank"];

  function resetProgress() {
    progressSteps.forEach((li) => {
      li.classList.remove("active", "done");
      li.querySelector(".marker").textContent = "○";
    });
  }

  function startProgressAnimation() {
    resetProgress();
    show(progressCard);
    let index = 0;

    function tick() {
      if (index > 0) {
        const prev = progressSteps[index - 1];
        prev.classList.remove("active");
        prev.classList.add("done");
        prev.querySelector(".marker").textContent = "✓";
      }
      if (index < progressSteps.length) {
        const current = progressSteps[index];
        current.classList.add("active");
        current.querySelector(".marker").textContent = "⟳";
        index += 1;
        progressTimer = setTimeout(tick, 550);
      }
    }
    tick();
  }

  function finishProgressAnimation() {
    if (progressTimer) clearTimeout(progressTimer);
    progressSteps.forEach((li) => {
      li.classList.remove("active");
      li.classList.add("done");
      li.querySelector(".marker").textContent = "✓";
    });
    setTimeout(() => hide(progressCard), 300);
  }

  function renderSummary(response) {
    const req = response.request;
    const rentLine =
      req.min_rent != null || req.max_rent != null
        ? `₹${req.min_rent != null ? req.min_rent.toLocaleString("en-IN") : "0"} – ₹${
            req.max_rent != null ? req.max_rent.toLocaleString("en-IN") : "no limit"
          }`
        : "Any";
    const bhkLine = req.bhk === "any" ? "Any" : `${req.bhk} BHK`;

    summaryCard.innerHTML = `
      <h2>Live Property Search</h2>
      <p class="summary-line"><strong>Area:</strong> ${escapeHtml(req.area)}</p>
      <p class="summary-line"><strong>Rent:</strong> ${rentLine}</p>
      <p class="summary-line"><strong>BHK:</strong> ${bhkLine}</p>
      <p class="summary-line"><strong>Search completed:</strong> ${formatTimestamp(response.searched_at)}</p>
      <div class="summary-stats">
        <div><strong>${response.statistics.sources_searched}</strong>Sources searched</div>
        <div><strong>${response.statistics.listings_discovered}</strong>Listings discovered</div>
        <div><strong>${response.statistics.after_filtering}</strong>After filtering</div>
        <div><strong>${response.statistics.after_deduplication}</strong>After deduplication</div>
      </div>
    `;
  }

  function renderSources(sources) {
    const rows = sources
      .map((s) => {
        let icon = "✓";
        let cls = "icon-ok";
        if (s.state === "unavailable") {
          icon = "✗";
          cls = "icon-bad";
        } else if (s.state === "degraded") {
          icon = "⚠";
          cls = "icon-warn";
        }
        const msg = s.message ? `<span class="source-msg"> — ${escapeHtml(s.message)}</span>` : "";
        return `<div class="source-row"><span class="${cls}">${icon}</span><span>${escapeHtml(s.name)}</span>${msg}</div>`;
      })
      .join("");
    sourcesPanel.innerHTML = `<h3>Search Sources</h3>${rows}`;
  }

  function humanize(value) {
    if (!value) return null;
    return String(value).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function propertyCard(record) {
    const title = record.bhk && record.bhk !== "any" ? `${record.bhk} BHK ${humanize(record.property_type) || "Property"}` : humanize(record.property_type) || "Property";
    const locality = record.locality || record.address || NOT_PUBLIC;
    const rentDisplay = record.monthly_rent != null ? `${formatMoney(record.monthly_rent)} / month` : `${NOT_VERIFIED} / month`;

    const tags = [];
    if (record.parking === "covered") tags.push("Covered Parking");
    else if (record.parking === "open") tags.push("Open Parking");
    if (record.lift === "available") tags.push("Lift");
    if (record.water_supply === "reliable") tags.push("Water Supply");
    if (record.owner_or_agent === "owner") tags.push("Owner Listed");
    if (record.brokerage === "none") tags.push("No Brokerage");
    if (record.food_preference === "vegetarian") tags.push("Vegetarian");
    if (record.food_preference === "non_vegetarian") tags.push("Non-Vegetarian OK");

    const sourcesLine = record.merged_sources && record.merged_sources.length > 1
      ? record.merged_sources.join(" + ")
      : record.source;

    const photosLink = record.photo_url
      ? `<a href="${escapeAttr(record.photo_url)}" target="_blank" rel="noopener">View Photos</a>`
      : "";

    const card = document.createElement("div");
    card.className = "property-card";
    card.innerHTML = `
      <div class="card-top">
        <span class="priority-badge priority-${record.priority || "C"}">${record.priority || "C"}</span>
        <span class="card-title">${escapeHtml(title)}</span>
        <span class="card-score">Match Score: ${record.match_score != null ? Math.round(record.match_score) : "N/A"}/100</span>
      </div>
      <div class="card-locality">${escapeHtml(locality)}</div>
      <div class="card-rent">${rentDisplay}</div>
      <div class="card-meta">
        <span>${record.size_sqft != null ? record.size_sqft + " sq ft" : NOT_VERIFIED}</span>
        <span>${humanize(record.furnishing) || NOT_VERIFIED}</span>
      </div>
      <div class="card-tags">${tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
      <div class="card-financials">
        Deposit: ${record.security_deposit != null ? formatMoney(record.security_deposit) : NOT_VERIFIED}
        &nbsp;·&nbsp;
        Maintenance: ${record.maintenance != null ? formatMoney(record.maintenance) : NOT_VERIFIED}
      </div>
      <div class="card-checked">Last checked: ${formatTimestamp(record.last_checked)}</div>
      <div class="card-source">Source: ${escapeHtml(sourcesLine)}</div>
      <div class="card-actions">
        <a class="primary" href="${escapeAttr(record.listing_url)}" target="_blank" rel="noopener">Open Listing</a>
        ${photosLink}
      </div>
    `;
    return card;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(str) {
    return escapeHtml(str);
  }

  const SORTERS = {
    best_match: (a, b) => (b.match_score || 0) - (a.match_score || 0),
    lowest_rent: (a, b) => (a.monthly_rent ?? Infinity) - (b.monthly_rent ?? Infinity),
    highest_bhk: (a, b) => (parseInt(b.bhk, 10) || 0) - (parseInt(a.bhk, 10) || 0),
    location: (a, b) => (b.match_score || 0) - (a.match_score || 0),
    recent: (a, b) => new Date(b.updated_date || b.listed_date || 0) - new Date(a.updated_date || a.listed_date || 0),
    owner: (a, b) => (b.owner_or_agent === "owner") - (a.owner_or_agent === "owner"),
    complete: (a, b) => (b.source_confidence || 0) - (a.source_confidence || 0),
  };

  function renderResults() {
    const sorter = SORTERS[sortSelect.value] || SORTERS.best_match;
    const sorted = [...currentResults].sort(sorter);
    resultsGrid.innerHTML = "";
    sorted.forEach((record) => resultsGrid.appendChild(propertyCard(record)));
  }

  function renderNoResults(suggestions) {
    noResultsSuggestions.innerHTML = (suggestions || [])
      .map((s) => `<li>${escapeHtml(s)}</li>`)
      .join("");
    show(noResultsBlock);
  }

  async function runSearch(payload) {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Search failed (${response.status})`);
    }
    return response.json();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hide(formError);
    formError.textContent = "";

    const payload = collectFormData();
    const validationError = validate(payload);
    if (validationError) {
      formError.textContent = validationError;
      show(formError);
      return;
    }

    searchButton.disabled = true;
    hide(resultsSection);
    hide(noResultsBlock);
    hide(resultsToolbar);
    startProgressAnimation();

    try {
      const response = await runSearch(payload);
      finishProgressAnimation();

      currentResults = response.results || [];
      renderSummary(response);
      renderSources(response.sources || []);
      show(resultsSection);

      if (currentResults.length === 0) {
        hide(resultsToolbar);
        resultsGrid.innerHTML = "";
        renderNoResults(response.no_results_suggestions);
      } else {
        hide(noResultsBlock);
        show(resultsToolbar);
        renderResults();
      }
    } catch (err) {
      finishProgressAnimation();
      formError.textContent = "Something went wrong while searching: " + err.message;
      show(formError);
    } finally {
      searchButton.disabled = false;
    }
  });

  sortSelect.addEventListener("change", renderResults);
})();
