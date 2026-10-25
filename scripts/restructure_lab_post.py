#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Move a lab post from the pre-2026-10-25 structure to the Master Standard.

    python scripts/restructure_lab_post.py --check posts/week-09-container-apps.html
    python scripts/restructure_lab_post.py --spec specs/week-09.py

Why a tool and not nine hand-rewrites
-------------------------------------
The Master Standard reorders and renames sections, merges three of them, and
adds two that did not exist. Almost none of that requires new prose: the
measured evidence, the figures and the engineering notes are already right, and
the standard says plainly not to rewrite accurate material unnecessarily.

So this MOVES existing sections and only asks the caller for what is genuinely
missing -- the Lab Overview facts, Prerequisites, a services table, figure
captions. Everything else is carried across byte-for-byte, which is the only
way to restructure nine published posts without quietly changing a number.

What it will not do
-------------------
It will not invent a section. If a spec omits `prerequisites`, the post comes
out without one and `--check` keeps reporting it missing. A tool that fills
gaps with plausible text is worse than no tool.
"""
import argparse
import html
import importlib.util
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NL = chr(10)

# Target order, with the id and the heading each section carries.
TARGET = [
    ("overview",        "Lab Overview"),
    ("services",        "Cloud Services and Concepts"),
    ("architecture",    "Architecture and Workflow"),
    ("prereqs",         "Prerequisites"),
    ("build",           "Implementation"),
    ("validation",      "Validation and Evidence"),
    ("seccost",         "Security and Cost"),
    ("troubleshooting", "Troubleshooting and Lessons"),
    ("cleanup",         "Cleanup and Key Takeaways"),
]

# How the old headings map onto the new sections. Order matters: first match
# wins, so the more specific patterns come first.
INBOUND = [
    (r"^Lab Overview",                      "overview"),
    (r"^Why\b",                             "overview"),
    (r"^Cloud Services",                    "services"),
    (r"^What You Need to Know",             "services"),
    (r"^Architecture",                      "architecture"),
    (r"^Prerequisites",                     "prereqs"),
    (r"^(Step-by-Step )?Implementation",    "build"),
    (r"^How We Built It",                   "build"),
    (r"^Validation",                        "validation"),
    (r"^How It'?s Tested",                  "validation"),
    (r"^Testing",                           "validation"),
    # Earlier weeks gave the evidence section a name of its own rather than a
    # generic one. These are validation sections and have to map, or the tool
    # refuses the post rather than silently dropping measured evidence.
    (r"^The Proof",                         "validation"),
    (r"^What Compliance Actually Reported", "validation"),
    (r"^What Was Measured",                 "validation"),
    (r"^The Evidence",                      "validation"),
    (r"^Security and Cost",                 "seccost"),
    (r"^Security",                          "seccost"),
    (r"^Cost",                              "seccost"),
    (r"^Troubleshooting",                   "troubleshooting"),
    (r"^Challenges",                        "troubleshooting"),
    (r"^Cleanup",                           "cleanup"),
    (r"^Key Takeaways",                     "cleanup"),
    (r"^Takeaways",                         "cleanup"),
    (r"^References",                        "cleanup"),
]

# Within section 9, these keep their own h3 and must appear in this order.
CLEANUP_ORDER = ["cleanup-body", "takeaways", "references"]


def plain(frag):
    return html.unescape(re.sub(r"<[^>]+>", "", frag)).strip()


def classify(heading):
    for pat, sid in INBOUND:
        if re.search(pat, heading):
            return sid
    return None


def split_post(text):
    """-> (frontmatter, preamble, {sid: [(orig_heading, html_body), ...]}, tail)"""
    fm_end = 0
    if text.startswith("---"):
        m = re.search(r"^---\s*$", text[3:], re.M)
        if m:
            fm_end = 3 + m.end()
    fm, rest = text[:fm_end], text[fm_end:]

    start = rest.find('<div id="jk-post">')
    if start < 0:
        raise SystemExit("no <div id=\"jk-post\"> wrapper")
    head = rest[:start + len('<div id="jk-post">')]
    body = rest[start + len('<div id="jk-post">'):]

    # Drop the table of contents; it is regenerated.
    #
    # This anchors on </ol></div>, the TOC's own closing pair, and nothing
    # else. An earlier version accepted any </div></div>, which was fine until
    # wrap_tables started emitting exactly that after every table: on a second
    # parse the strip ran from the TOC to the first wrapped table and swallowed
    # every section in between, so --check reported a well-formed post as
    # having no sections at all.
    body = re.sub(r'<div class="toc">.*?</ol>\s*</div>\s*', "", body, flags=re.S)

    parts = re.split(r'(<h2[^>]*>.*?</h2>)', body, flags=re.S)
    preamble = parts[0]
    sections = {}
    unmapped = []
    for i in range(1, len(parts), 2):
        heading = plain(parts[i])
        content = parts[i + 1] if i + 1 < len(parts) else ""
        sid = classify(heading)
        if sid is None:
            unmapped.append(heading)
            continue
        sections.setdefault(sid, []).append((heading, content))

    tail = ""
    m = re.search(r"(</div>\s*)$", body)
    if m:
        tail = m.group(1)
        if sections:
            last_sid = classify(plain(parts[-2])) if len(parts) > 2 else None
            if last_sid and sections.get(last_sid):
                h, c = sections[last_sid][-1]
                sections[last_sid][-1] = (h, c[:m.start()] if m.start() < len(c) else c)
    return fm, head, preamble, sections, unmapped, tail or (NL + "</div>" + NL)


def wrap_tables(frag):
    """Every table gets a scroll container. Inline styles are stripped on
    sync-built pages; class="table-scroll" is the wrapper that survives."""
    out, pos = [], 0
    for m in re.finditer(r"<table[\s>]", frag):
        before = frag[max(0, m.start() - 300):m.start()]
        if "table-scroll" in before or "overflow-x" in before:
            continue
        out.append(frag[pos:m.start()])
        out.append('<div class="table-scroll">' + NL)
        close = frag.find("</table>", m.start())
        if close < 0:
            out.append(frag[m.start():])
            pos = len(frag)
            break
        out.append(frag[m.start():close + len("</table>")])
        out.append(NL + "</div>")
        pos = close + len("</table>")
    out.append(frag[pos:])
    return "".join(out)


def _has_caption(frag, pos):
    """Is THIS figure captioned? Not the next one.

    A fixed lookahead window runs past the end of one figure and finds the
    FOLLOWING figure's <figcaption>, which reports an uncaptioned image as
    captioned. week-08's 01-hcp-workspace.png was missed exactly that way.
    So the window ends at the next <img or the closing </figure>, whichever
    comes first.
    """
    window = frag[pos:pos + 800]
    i = window.find("<img")
    if i >= 0:
        window = window[:i]
    j = window.find("</figure>")
    if j >= 0:
        window = window[:j + len("</figure>")]
    return "<figcaption" in window


def add_captions(frag, captions, prereq=()):
    """Give an uncaptioned figure a caption. A screenshot without one is not
    evidence of anything -- the standard asks what the image PROVES."""
    added = []
    for name, text in (captions or {}).items():
        for m in re.finditer(r"<img [^>]*?>", frag):
            tag = m.group(0)
            if name not in tag:
                continue
            if _has_caption(frag, m.end()):
                break                       # already captioned
            # Wrap the <p><img></p> or bare <img> in a figure with a caption.
            para = re.search(r"<p>\s*" + re.escape(tag) + r"\s*</p>", frag)
            block = para.group(0) if para else tag
            # A figure showing state that exists BEFORE the deploy must say
            # so, or check_figure_order reads it as showing live state too
            # early. Wrapping a bare <img> to add a caption silently drops
            # that marking -- it blocked a push for weeks 07, 08 and 09.
            attr = " data-prereq" if any(k in name for k in prereq) else ""
            fig = ('<figure class="screenshot"' + attr + ">" + NL + "  " + tag + NL +
                   "  <figcaption>" + text + "</figcaption>" + NL + "</figure>")
            frag = frag.replace(block, fig, 1)
            added.append(name)
            break
    return frag, added


def build(fm, head, preamble, sections, spec, tail):
    sid_order = [s for s, _ in TARGET]
    out = [fm, head, preamble.rstrip() + NL]

    # Regenerated table of contents, in target order, listing only what exists.
    present = [(sid, title) for sid, title in TARGET
               if spec.get(sid) or spec.get(sid + "_after") or sections.get(sid)]
    toc = ['<div class="toc">', '  <h2>&#128203; In This Post</h2>', "  <ol>"]
    for sid, title in present:
        toc.append('    <li><a href="#%s">%s</a></li>' % (sid, title))
    toc += ["  </ol>", "</div>", ""]
    out.append(NL.join(toc) + NL)

    for sid, title in TARGET:
        inbound = sections.get(sid, [])
        injected = spec.get(sid)
        if not inbound and not injected and not spec.get(sid + "_after"):
            continue
        out.append(NL + '<h2 id="%s">%s</h2>' % (sid, title) + NL)
        if injected:
            out.append(injected.rstrip() + NL)
        for idx, (orig, content) in enumerate(inbound):
            # A merged section keeps its old heading as an h3 so the reader can
            # still see the seam -- Security and Cost were two sections, and
            # pretending otherwise loses the distinction the standard wants.
            if len(inbound) > 1 or (injected and content.strip()):
                sub = spec.get("subheads", {}).get(orig, orig)
                if sub:
                    out.append("<h3>%s</h3>" % sub + NL)
            out.append(content.strip() + NL)
        # Some additions belong AFTER the carried-over prose, not before it.
        # The Lab Overview's facts table reads badly above the paragraph that
        # states the problem, and the existing paragraph is not ours to rewrite.
        after = spec.get(sid + "_after")
        if after:
            out.append(after.rstrip() + NL)

    out.append(tail if tail.strip() else NL + "</div>" + NL)
    return "".join(out)


def check(path):
    text = open(path, "rb").read().decode("utf-8", "replace").replace("\r\n", NL)
    fm, head, pre, sections, unmapped, tail = split_post(text)
    print("  %s" % os.path.basename(path))
    for sid, title in TARGET:
        got = sections.get(sid)
        mark = "have" if got else "MISSING"
        src = (" <- " + ", ".join(h for h, _ in got)) if got else ""
        print("    %-16s %-8s%s" % (sid, mark, src))
    if unmapped:
        print("    UNMAPPED headings: %s" % ", ".join(unmapped))
    body = text[text.find('<div id="jk-post">'):]
    imgs = re.findall(r"<img [^>]*?>", body)
    nocap = []
    for m in re.finditer(r"<img [^>]*?>", body):
        if not _has_caption(body, m.end()):
            src = re.search(r'src="([^"]+)"', m.group(0))
            nocap.append(src.group(1).split("/")[-1] if src else "?")
    print("    figures %d, uncaptioned %d%s"
          % (len(imgs), len(nocap), (": " + ", ".join(nocap)) if nocap else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="POST")
    ap.add_argument("--spec", metavar="SPEC_PY")
    a = ap.parse_args()

    if a.check:
        check(a.check)
        return
    if not a.spec:
        ap.error("need --check or --spec")

    spec_path = os.path.abspath(a.spec)
    sp = importlib.util.spec_from_file_location("spec", spec_path)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    spec = mod.SPEC
    post = spec["post"]

    raw = open(post, "rb").read().decode("utf-8")
    term = "\r\n" if "\r\n" in raw else NL
    text = raw.replace("\r\n", NL)

    fm, head, pre, sections, unmapped, tail = split_post(text)
    if unmapped:
        raise SystemExit("refusing to run: unmapped heading(s) %s -- add a "
                         "pattern to INBOUND rather than losing a section"
                         % unmapped)

    result = build(fm, head, pre, sections, spec, tail)
    result, added = add_captions(result, spec.get("captions"),
                                 spec.get("prereq", ("hcp-workspace",
                                                     "terraform-layout")))

    # Targeted replacements, for the places where carrying prose across is not
    # enough -- chiefly a two-column "What / Measured" table becoming the
    # standard's Test / Expected / Actual / Status. Every pair must match, or
    # the run aborts: a silently skipped edit leaves a post half-converted,
    # which is the one outcome worse than not running at all.
    for old, new in spec.get("edits", []):
        if old not in result:
            raise SystemExit("refusing to write: edit did not match:%s  %s..."
                             % (NL, old.strip()[:90].replace(NL, " ")))
        result = result.replace(old, new, 1)

    result = wrap_tables(result)

    # Safety net: the restructure must not drop measured content.
    def words(x):
        t = html.unescape(re.sub(r"<[^>]+>", " ", x))
        return len([w for w in t.split() if re.search(r"[A-Za-z0-9]", w)])
    before, after = words(text), words(result)
    sids = dict(TARGET)
    injected = sum(words(v) for k, v in spec.items()
                   if isinstance(v, str)
                   and (k in sids or k[:-6] in sids and k.endswith("_after")))
    edited = sum(words(o) for o, _n in spec.get("edits", []))
    lost = before - (after - injected) - edited
    if lost > 40:
        raise SystemExit("refusing to write: %d words of existing content went "
                         "missing (before %d, after %d, injected ~%d)"
                         % (lost, before, after, injected))

    tmp = post + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(result.replace(NL, term))
    os.replace(tmp, post)
    print("  %s: restructured (%d -> %d words, captions added: %s)"
          % (os.path.basename(post), before, after,
             ", ".join(added) if added else "none"))


if __name__ == "__main__":
    main()
