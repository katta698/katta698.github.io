
(async function () {
  const $ = (id) => document.getElementById(id);
  const priClass = { must: "pri-must", want: "pri-want", backup: "pri-backup" };

  function fmtCountdown(ms) {
    if (ms <= 0) return "Confirm live status on AWS";
    const s = Math.floor(ms / 1000);
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    return d + "d " + h + "h " + m + "m";
  }

  try {
    const meta = await (await fetch("./data/meta.json", { cache: "no-store" })).json();
    $("verified").textContent = "Verified " + ((meta.trust && meta.trust.verified_at) || "—");
    if (meta.sources) {
      if (meta.sources.catalog) $("link-catalog").href = meta.sources.catalog;
      if (meta.sources.hub) $("link-hub").href = meta.sources.hub;
      if (meta.sources.faqs) $("link-faq").href = meta.sources.faqs;
    }
    const chips = $("event-chips");
    const ev = meta.event || {};
    [ev.dates, ev.city, (ev.venues || []).length ? ev.venues.length + " venues" : null]
      .filter(Boolean)
      .forEach(function (t) {
        const el = document.createElement("span");
        el.className = "chip";
        el.textContent = t;
        chips.appendChild(el);
      });

    const res = meta.reservation || {};
    $("res-status").textContent = res.status || "";
    $("res-note").textContent = (res.target_note || "") + (res.opens_label ? " · " + res.opens_label : "");
    const target = res.target_iso ? new Date(res.target_iso) : null;
    const tick = function () {
      if (!target || isNaN(target.getTime())) {
        $("countdown").textContent = "TBD";
        return;
      }
      $("countdown").textContent = fmtCountdown(target.getTime() - Date.now());
    };
    tick();
    setInterval(tick, 30000);
  } catch (e) {
    $("verified").textContent = "Meta failed to load";
  }

  try {
    const list = await (await fetch("./data/shortlist.json", { cache: "no-store" })).json();
    $("shortlist-meta").textContent = "Updated " + (list.updated_at || "—");
    const body = $("shortlist-body");
    body.innerHTML = "";
    const sessions = list.sessions || [];
    if (!sessions.length) {
      body.innerHTML = '<tr><td colspan="7"><div class="empty">No sessions yet. Add rows to data/shortlist.json from the AWS catalog.</div></td></tr>';
      return;
    }
    sessions.forEach(function (s) {
      const tr = document.createElement("tr");
      const pri = (s.priority || "want").toLowerCase();
      tr.innerHTML =
        '<td><span class="pri ' + (priClass[pri] || "pri-want") + '">' + pri + "</span></td>" +
        "<td><code>" + (s.id || "") + "</code></td>" +
        "<td><strong>" + (s.title || "") + "</strong>" +
          (s.notes ? '<div class="muted" style="margin-top:4px">' + s.notes + "</div>" : "") +
          (s.catalog_url ? '<div style="margin-top:6px"><a href="' + s.catalog_url + '" target="_blank" rel="noopener">Open on AWS</a></div>' : "") +
        "</td>" +
        "<td>" + [s.day, s.time_pt].filter(Boolean).join(" · ") +
          (s.venue ? '<div class="muted">' + s.venue + "</div>" : "") + "</td>" +
        "<td>" + (s.lane || "—") + "</td>" +
        "<td>" + (s.owner || "—") + "</td>" +
        "<td>" + (s.reserve ? "Yes" : "No") + "</td>";
      body.appendChild(tr);
    });
  } catch (e) {
    $("shortlist-body").innerHTML = '<tr><td colspan="7" class="muted pad">Shortlist failed to load.</td></tr>';
  }
})();
