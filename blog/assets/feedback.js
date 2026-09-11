/* The feedback star, in one place.
 *
 * This behaviour used to exist as three near-identical copies -- one inline in
 * index.html, one emitted by sync_blog.py into every post, one in
 * feedback_star.py for the Intelligence pages -- and they had drifted. Escape
 * closed the modal on the three Intelligence pages and did nothing on the
 * portfolio or the blog. Tapping the backdrop closed it on the blog and the
 * status page but not on the portfolio. The background scrolled behind it
 * everywhere except the portfolio.
 *
 * So the same widget answered the same gesture three different ways depending
 * on which page you were on, which is the thing the nav work spent weeks
 * fixing. Copies drift; there is no version of this that stays in step by
 * being carefully maintained in three files.
 *
 * The markup stays inline on each page -- it is identical, and inlining it
 * avoids a flash of nothing where the button belongs. Only the behaviour is
 * shared, and it attaches to whatever markup it finds.
 */
(function () {
  'use strict';
  var FORM_ID = 'xzdqqvqd';

  var btn = document.getElementById('fb-btn');
  var overlay = document.getElementById('fb-overlay');
  if (!btn || !overlay) return;

  var modal = document.getElementById('fb-modal') ||
              overlay.querySelector('.fb-modal');
  var stars = overlay.querySelectorAll('.fb-star');
  var rating = 0;
  var opener = null;

  // Announced as a dialog rather than an anonymous group. Set here rather than
  // in the markup so all 239 pages gain it from one change.
  if (modal) {
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    var title = modal.querySelector('.fb-title');
    if (title) {
      if (!title.id) title.id = 'fb-title';
      modal.setAttribute('aria-labelledby', title.id);
    } else {
      modal.setAttribute('aria-label', 'Give feedback');
    }
  }

  function focusables() {
    return overlay.querySelectorAll(
      'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
  }

  function open() {
    opener = document.activeElement;
    overlay.classList.add('open');
    // The page behind a modal should not scroll. It did on every page but the
    // portfolio, so a thumb on the backdrop moved the article instead.
    document.body.style.overflow = 'hidden';
    if (modal) {
      // Focus the panel, not the first star: focusing a star paints a ring on
      // it and reads as though a rating is already chosen.
      modal.setAttribute('tabindex', '-1');
      modal.focus({ preventScroll: true });
    }
  }

  function close() {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
    // Send focus back where it came from, or it lands at the top of the page
    // and a keyboard reader has to walk down again.
    if (opener && opener.focus) opener.focus({ preventScroll: true });
    opener = null;
  }

  function isOpen() {
    return overlay.classList.contains('open');
  }

  btn.addEventListener('click', open);
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) close();
  });
  var skip = document.getElementById('fb-skip') || overlay.querySelector('.fb-skip');
  if (skip) skip.addEventListener('click', close);

  document.addEventListener('keydown', function (e) {
    if (!isOpen()) return;
    if (e.key === 'Escape') {
      close();
      return;
    }
    // Keep Tab inside the dialog while it is open. Without this, tabbing runs
    // off into the page behind, which is still there and still clickable.
    if (e.key !== 'Tab') return;
    var f = focusables();
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  Array.prototype.forEach.call(stars, function (s) {
    s.addEventListener('click', function () {
      rating = parseInt(s.getAttribute('data-v'), 10);
      Array.prototype.forEach.call(stars, function (x) {
        var on = parseInt(x.getAttribute('data-v'), 10) <= rating;
        x.classList.toggle('on', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
  });

  var send = document.getElementById('fb-send') || overlay.querySelector('.fb-send');
  if (send) {
    send.addEventListener('click', function () {
      var box = document.getElementById('fb-text') ||
                overlay.querySelector('.fb-textarea');
      var msg = box ? box.value : '';
      // Which page the report came from, so they can be told apart. Read off
      // the markup rather than baked into this file, which is shared.
      var page = overlay.getAttribute('data-page') || location.pathname;
      fetch('https://formspree.io/f/' + FORM_ID, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating: rating, message: msg, page: page })
      }).catch(function () { /* saying thank you does not depend on the POST */ });
      if (modal) {
        modal.innerHTML = '<div class="fb-thanks"><span>&#10003;</span>' +
          '<strong>Thanks for your feedback!</strong><p>It means a lot.</p></div>';
      }
      setTimeout(close, 2000);
    });
  }
})();
