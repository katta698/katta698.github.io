/* Post-incident write-ups: open one in a dialog, on demand.
 *
 * The store is ~312 KB because it holds the vendors' full published text, so
 * it is NOT embedded in the page. Cards are rendered at build time from the
 * index; the first card opened fetches the store once and every later one is
 * served from memory.
 *
 * Nothing here paraphrases. The dialog shows the vendor's own words, their own
 * section headings where they publish them, and a link to the original. If a
 * field is missing it stays missing and says so -- an outage write-up is
 * exactly the place where a confident-sounding filler sentence would do the
 * most damage.
 */
(function () {
  'use strict';

  var store = null;      // the parsed JSON, once fetched
  var pending = null;    // the in-flight promise, so a double click fetches once
  var dlg = document.getElementById('pm-dialog');
  if (!dlg) return;

  var body = dlg.querySelector('.pm-body');
  var lastFocus = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Vendor prose arrives as plain text with blank lines between paragraphs.
  // Rendering it into a single block loses that structure and makes a 4,000
  // word summary unreadable, which is the same as not publishing it.
  function paras(t) {
    return String(t || '').split(/\n{2,}/)
      .map(function (p) { return p.trim(); })
      .filter(Boolean)
      .map(function (p) { return '<p>' + esc(p).replace(/\n/g, '<br>') + '</p>'; })
      .join('');
  }

  function load() {
    if (store) return Promise.resolve(store);
    if (pending) return pending;
    pending = fetch('/intelligence/postmortems.json', { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) { store = j; return j; });
    return pending;
  }

  function render(rec) {
    var head =
      '<p class="pm-meta"><span class="chip ' + esc(rec.cloud) + '">' +
      esc((rec.cloud === 'gcp' ? 'Google Cloud' : rec.cloud).toUpperCase()) +
      '</span>' +
      (rec.date ? '<span class="pm-date">' + esc(rec.date) + '</span>'
                : '<span class="pm-date pm-none">date not stated in the summary</span>') +
      '</p>' +
      '<h3 id="pm-title">' + esc(rec.title) + '</h3>';

    var main;
    if (rec.sections && rec.sections.length) {
      main = rec.sections.map(function (s) {
        return '<section class="pm-sec"><h4>' + esc(s.heading) + '</h4>' +
               paras(s.text) + '</section>';
      }).join('');
    } else {
      // AWS publishes narrative summaries with no headings at all. Inventing
      // some here would imply a structure AWS did not write, so the prose is
      // shown as prose and the difference is stated plainly.
      main = '<p class="pm-shape">Published as a narrative summary. ' +
             'AWS does not break these into sections, so this is the text as ' +
             'written.</p>' + paras(rec.body);
    }

    var vendor = rec.cloud === 'aws' ? 'AWS'
               : rec.cloud === 'azure' ? 'Microsoft' : 'Google';
    var foot =
      '<p class="pm-src">Quoted in full from ' + esc(vendor) + '’s own ' +
      'published write-up. Nothing on this page is summarised or rewritten. ' +
      '<a href="' + esc(rec.url) + '" target="_blank" rel="noopener">' +
      'Read it on ' + esc(vendor) + '’s site →</a></p>';

    body.innerHTML = head + main + foot;
    body.scrollTop = 0;
  }

  function open(id) {
    lastFocus = document.activeElement;
    body.innerHTML = '<p class="pm-loading">Loading the write-up…</p>';
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');

    load().then(function (j) {
      var rec = (j.postmortems || []).filter(function (r) {
        return r.cloud + ':' + r.id === id;
      })[0];
      if (!rec) throw new Error('not found');
      render(rec);
    }).catch(function (err) {
      // Say what failed. A blank dialog reads as "there is nothing here",
      // which is a different and wrong claim.
      body.innerHTML = '<p class="pm-loading">Could not load this write-up (' +
        esc(err.message) + '). It is still on the vendor’s own site.</p>';
    });
  }

  function close() {
    if (typeof dlg.close === 'function' && dlg.open) dlg.close();
    else dlg.removeAttribute('open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener('click', function (ev) {
    var card = ev.target.closest ? ev.target.closest('[data-pm]') : null;
    if (card) {
      ev.preventDefault();
      open(card.getAttribute('data-pm'));
      return;
    }
    if (ev.target.hasAttribute && ev.target.hasAttribute('data-pm-close')) close();
    // Clicking the backdrop closes: the dialog element itself is the backdrop,
    // so a click landing on it rather than on its content means outside.
    if (ev.target === dlg) close();
  });

  dlg.addEventListener('cancel', function () { close(); });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && dlg.open) close();
  });

  /* "Did you know?" -- rotate through the quoted lines.
   *
   * The card renders server-side with one line already in it, so it reads
   * fine with no JavaScript at all; this only adds the rotation. Each line is
   * the vendor's own first sentence from the section THEY labelled as the
   * cause, so cycling never changes whose words these are. */
  var dyk = document.getElementById('dyk');
  var dykData = document.getElementById('dyk-data');
  if (dyk && dykData) {
    var hooks = [];
    try { hooks = JSON.parse(dykData.textContent) || []; } catch (e) { hooks = []; }

    function paint(i) {
      var h = hooks[i];
      if (!h) return;
      dyk.setAttribute('data-i', i);
      dyk.querySelector('.dyk-q').textContent = h.q;
      var chip = dyk.querySelector('.chip');
      chip.className = 'chip ' + h.cloud;
      chip.textContent = h.cloud === 'gcp' ? 'Google Cloud'
                       : h.cloud === 'aws' ? 'AWS' : 'Azure';
      dyk.querySelector('.dyk-d').textContent = h.date || 'date not stated';
      dyk.querySelector('.dyk-t').textContent = h.title;
      dyk.querySelector('.dyk-more').setAttribute('data-pm', h.id);
    }

    dyk.addEventListener('click', function (ev) {
      if (!ev.target.classList.contains('dyk-next')) return;
      var i = (parseInt(dyk.getAttribute('data-i'), 10) || 0) + 1;
      paint(i % hooks.length);
    });
  }
})();
