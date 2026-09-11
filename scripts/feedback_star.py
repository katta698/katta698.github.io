#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The floating star feedback button: the markup here, the behaviour shared.

    from feedback_star import star_html, STAR_CSS

star_html() returns the button and the modal for one page. What the modal
DOES lives in blog/assets/feedback.js, loaded by all 239 pages that carry it.

That split is the point. The behaviour used to be inlined alongside the markup
in four separate places -- index.html, intelligence/index.html, sync_blog.py's
post template, and here -- and four copies of anything drift. These had:

    Escape closed it     on the 3 Intelligence pages, not on portfolio or blog
    backdrop closed it   on blog and status, not on portfolio
    scroll locked        on portfolio only

So the same modal answered the same gesture three different ways depending on
which page you were standing on, and on the portfolio it could only be
dismissed by finding the Skip button. Every copy worked; they simply did not
agree, and nothing about looking at a page would tell you.

check_feedback.py asserts they still agree.

Why the CSS is copied rather than linked
----------------------------------------
The rules live in index.html and blog.css. The Intelligence status page loads
neither -- it has its own stylesheet -- so pulling blog.css in for one widget
would drag a whole design system onto a page that already has one.

Every var() below carries a literal fallback, and that is not caution for its
own sake. The original rules depend on eight tokens (--accent-gold, --bg-dark,
--border-dark, --icon-border, --surface, --text, --text-light, --fb-star), and
the Intelligence pages define almost none of them. An undefined custom
property invalidates the whole declaration silently, so copied as-is this
would have produced a button with no background and a modal with no surface --
which is precisely how the correction card I wrote last shipped at 1.23:1, and
the fifth time this exact trap has been sprung in this repo.

The fallbacks are the values the portfolio actually resolves to, so a page
that defines the tokens looks identical to one that does not.
"""

FORM_ID = "xzdqqvqd"

_STAR = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
         "viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.9' "
         "stroke-linejoin='round' stroke-linecap='round'%3E%3Cpolygon "
         "points='12 2.8 14.95 9.05 21.6 9.95 16.75 14.5 17.95 21.2 12 18 "
         "6.05 21.2 7.25 14.5 2.4 9.95 9.05 9.05'/%3E%3C/svg%3E\")")


def star_html(page_id):
    """The button and the overlay for one page. The behaviour is shared.

    The markup stays inline -- it is small, it is identical everywhere, and
    inlining avoids a gap where the button belongs while a script loads. The
    behaviour used to be inlined with it, in four separate copies, and they
    drifted: Escape closed the modal on three pages and did nothing on the
    other two, the backdrop closed it on some, and the page behind it scrolled
    on most. One file now answers all of that for every page.
    """
    return """
<!-- Feedback: the site's own star widget. Behaviour: /blog/assets/feedback.js?v=5f3acc71 -->
<button class="fb-btn" id="fb-btn" aria-label="Give feedback" title="Give feedback">&#9733;</button>
<div class="fb-overlay" id="fb-overlay" data-page="%s">
  <div class="fb-modal" id="fb-modal">
    <div class="fb-title">How was your experience?</div>
    <div class="fb-sub">Your feedback helps improve this site.</div>
    <div class="fb-stars" id="fb-stars">
      <button class="fb-star" data-v="1" aria-label="1 star">&#9733;</button>
      <button class="fb-star" data-v="2" aria-label="2 stars">&#9733;</button>
      <button class="fb-star" data-v="3" aria-label="3 stars">&#9733;</button>
      <button class="fb-star" data-v="4" aria-label="4 stars">&#9733;</button>
      <button class="fb-star" data-v="5" aria-label="5 stars">&#9733;</button>
    </div>
    <div class="fb-labels"><span>Poor</span><span>Excellent</span></div>
    <textarea class="fb-textarea" id="fb-text" placeholder="Any thoughts? (optional)"></textarea>
    <div class="fb-footer">
      <button class="fb-skip" id="fb-skip">Skip</button>
      <button class="fb-send" id="fb-send">Send feedback</button>
    </div>
  </div>
</div>
<script src="/blog/assets/feedback.js?v=5f3acc71" defer></script>""" % page_id


STAR_CSS = """
/* Feedback star. Copied from the portfolio with every var() given a literal
   fallback -- the Intelligence pages define almost none of the eight tokens
   these rules originally relied on, and an undefined property takes the whole
   declaration with it. */
.fb-btn{--fb-star:%s;
  position:fixed;right:14px;top:50%%;transform:translateY(-50%%);z-index:900;
  width:40px;height:40px;border-radius:11px;
  background:var(--surface, var(--card, #1E2422));
  color:var(--text, var(--tx, #EDEBE6));
  border:1px solid var(--icon-border, var(--bd, rgba(128,128,128,.32)));
  box-shadow:0 2px 10px rgba(0,0,0,.28);
  display:flex;align-items:center;justify-content:center;cursor:pointer;
  font-size:0;transition:border-color .2s,color .2s,background .2s}
.fb-btn::before{content:'';width:19px;height:19px;background:currentColor;
  -webkit-mask:var(--fb-star) center / contain no-repeat;
  mask:var(--fb-star) center / contain no-repeat}
.fb-btn:hover,.fb-btn:focus-visible{
  border-color:var(--accent-gold, #C4A484);color:var(--accent-gold, #C4A484);
  box-shadow:0 3px 14px rgba(0,0,0,.34)}
/* Above the nav, not under it. The portfolio's header is fixed at
   z-index 1000, so at 901 the nav painted on top of an open modal and
   stayed clickable through the dimmed backdrop -- a tap meant for
   'close' hit a nav link instead. Everywhere else the nav is 100, so
   this showed on exactly one page. */
.fb-overlay{display:none;position:fixed;inset:0;z-index:1200;
  background:rgba(0,0,0,.55);align-items:flex-end;justify-content:flex-start;
  padding:1.75rem}
.fb-overlay.open{display:flex}
.fb-modal{background:var(--bg-dark, #1D2322);
  border:1px solid rgba(196,164,132,.25);border-radius:16px;padding:1.5rem;
  width:300px;max-width:100%%;color:var(--text-light, #EDEBE6)}
.fb-title{color:var(--text-light, #EDEBE6);font-size:15px;font-weight:600;
  margin-bottom:.35rem}
.fb-sub{color:#A7B0B4;font-size:12px;margin-bottom:1.25rem}
.fb-stars{display:flex;gap:8px;margin-bottom:.5rem}
.fb-star{width:42px;height:42px;border-radius:50%%;
  border:1.5px solid rgba(196,164,132,.3);background:transparent;
  display:flex;align-items:center;justify-content:center;cursor:pointer;
  color:#A7B0B4;font-size:18px;line-height:1}
.fb-star.on{border-color:var(--accent-gold, #C4A484);
  color:var(--accent-gold, #C4A484);background:rgba(196,164,132,.1)}
.fb-labels{display:flex;justify-content:space-between;font-size:11px;
  color:#A7B0B4;margin-bottom:1rem}
.fb-textarea{width:100%%;box-sizing:border-box;
  background:var(--border-dark, #2A312F);
  border:1px solid rgba(196,164,132,.2);border-radius:8px;
  color:var(--text-light, #EDEBE6);font-size:13px;padding:.6rem .7rem;
  font-family:inherit;margin-bottom:1rem;min-height:70px}
.fb-textarea::placeholder{color:#A7B0B4}
.fb-textarea:focus{outline:none;border-color:rgba(196,164,132,.5)}
.fb-footer{display:flex;justify-content:space-between;align-items:center}
.fb-skip{background:transparent;border:none;color:#A7B0B4;font-size:13px;
  cursor:pointer}
.fb-send{background:var(--accent-gold, #C4A484);color:#1D2322;border:none;
  border-radius:8px;padding:.45rem 1.1rem;font-size:13px;font-weight:700;
  cursor:pointer}
.fb-send:hover{background:#B09173}
.fb-thanks{text-align:center;padding:1rem 0;
  color:var(--text-light, #EDEBE6);font-size:14px}
.fb-thanks span{display:block;color:var(--accent-gold, #C4A484);font-size:28px;
  margin-bottom:.5rem}
.fb-thanks p{color:#A7B0B4;font-size:13px;margin-top:.35rem}
/* A 44px thumb target without a 44px block of paint.
   The button is drawn at 34px on a phone, which already clears the 24px
   WCAG 2.5.8 floor, and growing it would put more opaque square over the
   body text it floats above. So the touch area is extended past the edge
   instead: invisible, costs no layout, and nothing moves. */
.fb-btn::after{content:'';position:absolute;top:50%%;left:50%%;
  transform:translate(-50%%,-50%%);width:44px;height:44px}
@media (max-width:640px){
  .fb-btn{width:34px;height:34px;border-radius:10px;position:fixed}
  .fb-btn::before{width:16px;height:16px}
  .fb-overlay{padding:.75rem}
  .fb-modal{width:100%%}
}
""" % _STAR
