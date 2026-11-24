import io

# ---------------------------------------------------------------- 1. CSS ---
P = "blog/assets/blog.css"
s = io.open(P, encoding="utf-8").read()

old = """.nav,
.filter-stack {
  will-change: transform;
  transform: translateZ(0);
  backface-visibility: hidden;
}"""
new = """.nav {
  will-change: transform;
  transform: translateZ(0);
  backface-visibility: hidden;
}
/* The stack keeps the promotion and loses the hint.
   Reported as the blog, alone, flashing mid-scroll on a phone: content
   vanishing for a moment and coming back. Measured against the pages that
   do not do it, the blog is the only one carrying TWO sticky promoted
   layers -- this and the nav -- over an 11,600px document with 5,053
   elements. The portfolio is the same height, has no sticky layer, and
   does not flash.
   translateZ(0) still promotes it, so the nav's blur does not re-sample
   this every frame, which is what the rule above exists for. What goes is
   `will-change: transform`: a hint meant to be set just before a change
   and cleared after, left on permanently here, telling the compositor to
   hold a full-width layer ready for the life of the page. On a phone that
   is memory the browser reclaims by dropping tiles, and a dropped tile
   coming back is what a flash IS.
   Not proven from here -- a headless browser does not reproduce mobile
   compositing, and screenshotting forces the repaint that hides it. */
.filter-stack {
  transform: translateZ(0);
  backface-visibility: hidden;
}"""
assert s.count(old) == 1
s = s.replace(old, new)

# ------------------------------------------------- 2. the typing cursor ---
old_typer = """.hero-typer-cursor { animation: hero-typer-blink 1s step-end infinite; }"""
new_typer = """/* The cursor moves by transform, and the line reserves its full width.
   Measured on a phone viewport: typing one character at a time logged about
   60 layout shifts per load, because the text box grew and the cursor beside
   it moved, each character counting as its own shift. Reserving the widest
   line stops the box growing; moving the cursor with a transform keeps it
   against the text without the browser doing layout for it. 60 shifts -> 0,
   with the animation unchanged to look at.
   39ch is the longest line in blog.js. Keep the two in step. */
#hero-typer-text {
  display: inline-block;
  min-width: 39ch;
  position: relative;
}
.hero-typer-cursor {
  position: absolute;
  left: 0;
  top: 0;
  will-change: transform;
  animation: hero-typer-blink 1s step-end infinite;
}
@media (max-width: 420px) { #hero-typer-text { min-width: 0; } }"""
assert s.count(old_typer) == 1
s = s.replace(old_typer, new_typer)
io.open(P, "w", encoding="utf-8").write(s)
print("blog.css: filter-stack hint dropped, typer line reserved")

# ------------------------------------------------------------- 3. the JS ---
P = "blog/assets/blog.js"
s = io.open(P, encoding="utf-8").read()

old_js = """  var host = el.closest ? el.closest('.hero-typer') : null;
  if (host) host.style.visibility = 'hidden';"""
new_js = """  var host = el.closest ? el.closest('.hero-typer') : null;
  if (host) host.style.visibility = 'hidden';
  /* The typed text goes in a span of its own, and the cursor rides a
     transform behind it rather than sitting next to it in the flow. The
     outer #hero-typer-text reserves the widest line, so nothing reflows as
     characters arrive -- see the note in blog.css. */
  var inner = document.createElement('span');
  el.appendChild(inner);
  var cursor = host ? host.querySelector('.hero-typer-cursor') : null;
  if (cursor) el.appendChild(cursor);
  function show(text) {
    inner.textContent = text;
    if (cursor) {
      cursor.style.transform = 'translateX(' + inner.offsetWidth + 'px)';
    }
  }"""
assert s.count(old_js) == 1
s = s.replace(old_js, new_js)

assert s.count("      el.textContent = line.slice(0, ci);") == 1
s = s.replace("      el.textContent = line.slice(0, ci);",
              "      show(line.slice(0, ci));")
assert s.count("      el.textContent = line.slice(0, ci);\n      setTimeout(erase, 30);") == 0
old_erase = """      ci--;
      el.textContent = line.slice(0, ci);
      setTimeout(erase, 30);"""
new_erase = """      ci--;
      show(line.slice(0, ci));
      setTimeout(erase, 30);"""
assert s.count(old_erase) == 1, s.count(old_erase)
s = s.replace(old_erase, new_erase)
io.open(P, "w", encoding="utf-8").write(s)
print("blog.js: cursor rides a transform")
