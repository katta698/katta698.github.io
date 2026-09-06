"""Repair double-encoded UTF-8 in post sources.

Six of the early Architecture Series sources (#1, #2, #3, #4, #6, #7) hold
text that was written as UTF-8, read back as cp1252, and written out as UTF-8
again -- so an em dash became three characters. The published pages under
blog/ were generated before that happened and are clean, which is why nobody
saw it: the corruption is only in the source. Rebuilding one of those posts
would push the mojibake onto a live page.

Whole-file repair does not work, because the same files also contain real em
dashes that cp1252 encodes to bytes UTF-8 cannot decode. So this repairs only
the runs that round-trip: a run is replaced only when encoding it as cp1252
and decoding as UTF-8 succeeds and the result is shorter. Anything else is
left alone and reported, because a partial repair that silently mangles one
character is worse than no repair.

Usage:  python scripts/fix_mojibake.py [--apply] [path ...]
Without --apply it reports and changes nothing.
"""

import glob
import io
import re
import sys

# Lead bytes of a UTF-8 sequence as they appear once misread through cp1252,
# followed by one to three continuation characters from the cp1252 upper page.
RUN = re.compile(
    u"[ÂÃâ]"
    u"[-ÿ–—‘-„€ˆ˜™"
    u"ŒœŠšŸŽžƒ"
    u"†‡…‰‹›]{1,3}"
)


def repair(text):
    """Return (repaired_text, n_fixed, unrepairable_runs)."""
    fixed = [0]
    left = []

    def sub(m):
        # The run is matched greedily, so a three-character sequence followed
        # by the lead of the next one comes back as a four-character match
        # that does not round-trip. Repair the longest prefix that does, and
        # hand the remainder back for the next pass.
        s = m.group(0)
        for cut in range(len(s), 1, -1):
            head, tail = s[:cut], s[cut:]
            try:
                out = head.encode("cp1252").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if len(out) < len(head):
                fixed[0] += 1
                return out + tail
        left.append(s)
        return s

    # Repairing a prefix can expose the run that followed it, so iterate to a
    # fixed point rather than assuming one pass is enough.
    prev = None
    while prev != text:
        prev = text
        del left[:]
        text = RUN.sub(sub, text)
    return text, fixed[0], left


def main(argv):
    apply_ = "--apply" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        paths = sorted(glob.glob("posts/arch-*.html"))

    total = 0
    for path in paths:
        text = io.open(path, encoding="utf-8").read()
        out, n, left = repair(text)
        if not n and not left:
            continue
        total += n
        name = path.replace("\\", "/").split("/")[-1]
        print("%-50s %3d repaired%s" % (
            name, n, ", %d left alone" % len(left) if left else ""))
        for s in sorted(set(left)):
            print("      unrepairable: %r" % s)
        if apply_ and n:
            io.open(path, "w", encoding="utf-8", newline="").write(out)

    print("\n%d sequence(s) %s" % (total, "repaired" if apply_ else "would be repaired"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
