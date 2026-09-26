# -*- coding: utf-8 -*-
"""The followers' tracks, generated rather than hand-typed.

One robot became four: the model he works with, and the three agents it
runs. Each trails a little further back and stands a little shorter, so
the chain reads as a hierarchy without a word of explanation -- him, then
what he uses, then what that uses.

Each one needs its own keyframes rather than the leader's with a delay.
A delay walks a follower into the one in front while everybody is stood
still at AWS, and gives it no way to cross to the other side when the
line turns round.
"""

# The stops moved inward (20/50/80% rather than 13/47/84) to leave the
# tail of the chain somewhere to stand. At the old spacing the last two
# agents were off the faded end of the road for a third of the loop.
AZURE, AWS, GCP = 39.0, 112.0, 186.0

# name, pixels behind the man, height in px, seconds per step, hop delay %
FOLLOWERS = [
    ("f1", 15.0, 19.0, 0.48, 1.3),   # the model he works with
    ("f2", 26.0, 13.0, 0.40, 2.1),   # and the three agents it runs
    ("f3", 35.5, 11.0, 0.36, 2.8),
    ("f4", 44.5,  9.5, 0.33, 3.5),
]


def track(name, back):
    """Behind him whichever way he is facing, and crossing over at each end
    while he is stood still."""
    return """@keyframes trek-%s {
  0%%, 2%% { transform: translateX(%.0fpx); }
  20%% { transform: translateX(%.0fpx); }
  28%% { transform: translateX(%.0fpx); }
  46%% { transform: translateX(%.0fpx); }
  49%% { transform: translateX(%.0fpx); }
  56%% { transform: translateX(%.0fpx); }
  70%% { transform: translateX(%.0fpx); }
  78%% { transform: translateX(%.0fpx); }
  96%% { transform: translateX(%.0fpx); }
  100%% { transform: translateX(%.0fpx); }
}""" % (name, AZURE - back, AWS - back, AWS - back, GCP - back,
        GCP - back * 0.25, GCP + back, AWS + back, AWS + back,
        AZURE + back, AZURE - back)


def hop(name, delay):
    """Up after him, not with him -- the line catches the jump one by one."""
    a, b = 21.0 + delay, 71.0 + delay
    return """@keyframes hop-%s {
  0%%, %.1f%% { transform: translateY(0); }
  %.1f%% { transform: translateY(-5px); }
  %.1f%%, %.1f%% { transform: translateY(0); }
  %.1f%% { transform: translateY(-5px); }
  %.1f%%, 100%% { transform: translateY(0); }
}""" % (name, a, a + 1.8, a + 3.6, b, b + 1.8, b + 3.6)


def css():
    out = []
    for name, back, h, step, delay in FOLLOWERS:
        w = round(h * 11.0 / 19.0, 1)
        out.append(".%s { top: %.0fpx; width: %.1fpx; }" % (name, 21 - h, w))
        out.append(".%s .bot { width: %.1fpx; height: %.1fpx; }" % (name, w, h))
        out.append("@media (prefers-reduced-motion: no-preference) {")
        out.append("  .%s { animation: trek-%s 26s linear infinite; }" % (name, name))
        out.append("  .%s > span { animation: hop-%s 26s ease-out infinite; }"
                   % (name, name))
        out.append("  .%s .bot { animation: face 26s steps(1) infinite; }" % name)
        # The four poses are held by four delays a quarter of a cycle
        # apart. Change the duration and keep the delays and they no
        # longer divide it -- at some instants two poses show, at others
        # NONE, and the follower vanishes while still animating. Both
        # have to scale together.
        out.append("  .%s .bot > g { animation-duration: %.3fs; }" % (name, step))
        for i in range(4):
            out.append("  .%s .bot .r%d { animation-delay: %.3fs; }"
                       % (name, i, step * i / 4.0))
        out.append("}")
        out.append("@media (prefers-reduced-motion: reduce) {")
        out.append("  .%s { transform: translateX(%.0fpx); }" % (name, AWS - back))
        out.append("}")
        out.append(track(name, back))
        out.append(hop(name, delay))
    return "\n".join(out)


def markup(sprite):
    return "\n      ".join(
        '<div class="follow %s">%s<span>%s</span></div>'
        % (n, puff_markup(n), sprite)
        for n, _, _, _, _ in FOLLOWERS)


# What each one puffs out and lets go of ----------------------------------
#
# The model names rise off the big robot, the tool names off the small ones.
# One at a time across the whole chain, roughly every six seconds, each
# visible for about two and a half -- five per cent of the cycle. Any more
# and it is a tag cloud walking down a road.
#
# The rise is capped at 7px. There are only 9px between the road and the
# job title, the man's own box already uses 10 of them mid-jump, and at
# 8px a label's top landed 1px inside the title at 360 wide -- measured,
# not guessed, because one pixel is not something you see in a
# screenshot.
# The big robot is the model, so it breathes out MODELS. The three small
# ones are agents, so they breathe out the things that run on top.
#
# Worth saying plainly: this is prominence as of a knowledge cutoff, not a
# measured ranking of worldwide use -- nobody publishes that. It is also
# the part of the card that dates fastest, so it is one list in one file.
PUFFS = [
    ("f1", ["Claude", "ChatGPT", "Gemini", "Grok",
            "Llama", "DeepSeek", "Mistral"]),
    ("f2", ["Claude Code", "Codex", "Cursor"]),
    ("f3", ["Copilot", "Kiro", "Antigravity"]),
    ("f4", ["Devin", "Windsurf", "Amazon Q"]),
]
PUFF_CYCLE = 42.0          # not a multiple of the 26s walk, so the two
                           # never fall into step and start looking canned
PUFF_DUTY = 4.0            # per cent of the cycle a name is on screen


def puff_css():
    # The -50% is inside every keyframe on purpose. transform is one
    # property: a keyframe setting translateY REPLACES the translateX that
    # was centring the label, and the name drifts half its own width off
    # the robot it belongs to.
    d = PUFF_DUTY
    out = ["""@keyframes puff {
  0%% { opacity: 0; transform: translate(-50%%, 2px); }
  %.2f%% { opacity: .95; transform: translate(-50%%, -1px); }
  %.2f%% { opacity: .95; transform: translate(-50%%, -4px); }
  %.2f%% { opacity: 0; transform: translate(-50%%, -7px); }
  100%% { opacity: 0; transform: translate(-50%%, -7px); }
}""" % (d * 0.16, d * 0.62, d),
".puff { position: absolute; left: 50%; bottom: 100%; margin-bottom: -2px;",
"        width: 0; pointer-events: none; }",
".puff b { position: absolute; left: 0; bottom: 0; opacity: 0;",
"          transform: translate(-50%, 0); white-space: nowrap;",
"          font-family: inherit; font-size: 6.4px; font-weight: 700;",
"          font-style: normal; line-height: 1; letter-spacing: .06em;",
"          text-transform: none; color: var(--muted); }",
"@media (prefers-reduced-motion: no-preference) {"]
    slot = 0
    total = sum(len(n) for _, n in PUFFS)
    step = PUFF_CYCLE / total
    for name, words in PUFFS:
        for i in range(len(words)):
            out.append("  .%s .puff b:nth-child(%d) { animation: puff %.0fs "
                       "ease-out %.2fs infinite; }"
                       % (name, i + 1, PUFF_CYCLE, 1.5 + slot * step))
            slot += 1
    out.append("}")
    return "\n".join(out)


def puff_markup(name):
    for n, words in PUFFS:
        if n == name:
            return ('<i class="puff">%s</i>'
                    % "".join("<b>%s</b>" % w for w in words))
    return ""
