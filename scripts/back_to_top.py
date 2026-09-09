#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The back-to-top arrow, for the Intelligence pages.

    from back_to_top import TOP_HTML, TOP_CSS

The same control the blog index carries: a round button, bottom-left, that
fades in past 400px of scroll and returns to the top smoothly.

These are the longest pages on the site -- the status page runs to a 90-day
timeline, a region grid, a disclosure chart and twenty-four write-ups, and
What's New scrolls through hundreds of announcements. They are exactly where
a reader ends up a long way from the navigation, and they were the two pages
without the control.

Why the CSS is copied
---------------------
.back-top lives in blog.css, which the status page does not load. Its three
tokens (--orange, --ink, --shadow-md) are not defined on these pages, and an
undefined custom property invalidates the whole declaration rather than
falling back -- so a straight copy yields a button with no background, no
text colour and no shadow, which is a transparent circle that happens to be
clickable. That failure has now happened five times in this repo, twice in
code I wrote to avoid it, so every var() here carries a literal.

The fallbacks are the values blog.css resolves to, so the button looks the
same wherever it appears.
"""

TOP_HTML = ('<button class="back-top" id="back-top" '
            'aria-label="Back to top">&#8593;</button>')

TOP_CSS = """
/* Back to top. Copied from blog.css because the status page does not load it,
   with a literal fallback on every var() -- --orange, --ink and --shadow-md
   are undefined here, and an undefined token takes the whole declaration with
   it rather than falling back. */
.back-top{position:fixed;bottom:1.5rem;left:1.5rem;right:auto;
  width:40px;height:40px;border-radius:50%;
  background:var(--orange, var(--acc, #C4A484));
  color:var(--ink, #1D2322);
  border:none;cursor:pointer;display:flex;align-items:center;
  justify-content:center;opacity:0;transform:translateY(8px);
  transition:opacity .2s, transform .2s;
  box-shadow:var(--shadow-md, 0 4px 16px rgba(0,0,0,.28));
  font-size:1rem;line-height:1;z-index:200;
  pointer-events:none}
.back-top.show{opacity:1;transform:translateY(0);pointer-events:auto}
.back-top:hover,.back-top:focus-visible{filter:brightness(1.06)}
@media (prefers-reduced-motion:reduce){
  .back-top{transition:none}
}
"""

# Identical behaviour to blog.js: appear past 400px, smooth scroll home.
#
# pointer-events is toggled with the class rather than left on, because the
# button sits at opacity 0 and still swallowed clicks in the bottom-left
# corner of the page when hidden.
TOP_JS = """
<script>
(function(){
  var btn=document.getElementById('back-top');
  if(!btn) return;
  function check(){
    var y=window.scrollY||document.documentElement.scrollTop||0;
    btn.classList.toggle('show', y>400);
  }
  window.addEventListener('scroll',check,{passive:true});
  check();
  btn.addEventListener('click',function(){
    var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({top:0,behavior:reduce?'auto':'smooth'});
  });
})();
</script>"""
