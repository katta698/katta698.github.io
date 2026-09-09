#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The floating star feedback button, for pages that do not load blog.css.

    from feedback_star import star_html, STAR_CSS

The widget itself is the site's own: the same markup, the same Formspree form,
the same five-star modal that the portfolio and blog index already carry. Only
the `page` field differs, so reports can be told apart.

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
    """The button, the overlay and the behaviour, for one page."""
    return """
<!-- Feedback: the site's own star widget. -->
<button class="fb-btn" id="fb-btn" aria-label="Give feedback" title="Give feedback">&#9733;</button>
<div class="fb-overlay" id="fb-overlay">
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
<script>
(function(){
  var FORM_ID='%s', PAGE='%s', rating=0;
  var btn=document.getElementById('fb-btn'), overlay=document.getElementById('fb-overlay');
  if(!btn||!overlay) return;
  var stars=document.querySelectorAll('.fb-star');
  btn.addEventListener('click',function(){overlay.classList.add('open');});
  overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.classList.remove('open');});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')overlay.classList.remove('open');});
  document.getElementById('fb-skip').addEventListener('click',function(){overlay.classList.remove('open');});
  Array.prototype.forEach.call(stars,function(s){
    s.addEventListener('click',function(){
      rating=parseInt(s.getAttribute('data-v'),10);
      Array.prototype.forEach.call(stars,function(x){
        x.classList.toggle('on',parseInt(x.getAttribute('data-v'),10)<=rating);});
    });
  });
  document.getElementById('fb-send').addEventListener('click',function(){
    var msg=document.getElementById('fb-text').value;
    fetch('https://formspree.io/f/'+FORM_ID,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({rating:rating,message:msg,page:PAGE})});
    document.getElementById('fb-modal').innerHTML='<div class="fb-thanks"><span>&#10003;</span><strong>Thanks for your feedback!</strong><p>It means a lot.</p></div>';
    setTimeout(function(){overlay.classList.remove('open');},2000);
  });
})();
</script>""" % (FORM_ID, page_id)


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
.fb-overlay{display:none;position:fixed;inset:0;z-index:901;
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
@media (max-width:640px){
  .fb-btn{width:34px;height:34px;border-radius:10px}
  .fb-btn::before{width:16px;height:16px}
  .fb-overlay{padding:.75rem}
  .fb-modal{width:100%%}
}
""" % _STAR
