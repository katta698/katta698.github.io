<?xml version="1.0" encoding="utf-8"?>
<!--
  The blog feed, made readable in a browser.

  Clicking a feed link used to land on "This XML file does not appear to have
  any style information associated with it" followed by a wall of tags. That is
  what a reader sees when they follow a link that says "blog" in the footer,
  and it reads as a broken page rather than as a feed.

  Feed readers ignore this entirely, parsing the XML underneath, so one file
  serves software and people. The incident feeds have the same treatment
  in intelligence/status/feed.xsl.
-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="utf-8" indent="yes"/>
<xsl:template match="/">
<html lang="en">
  <xsl:attribute name="data-palette"><xsl:value-of
    select="/rss/@data-palette"/></xsl:attribute>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title><xsl:value-of select="rss/channel/title"/></title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&amp;family=Playfair+Display:wght@600&amp;family=DM+Mono:wght@400&amp;display=swap" rel="stylesheet"/>
  <!-- The site's own stylesheet, not a copy of its colours, so the ground, the
       type and the weekday palette match the page this was linked from. A
       second set of hex values would drift from the first the day either
       changed. -->
  <link rel="stylesheet" href="/intelligence/status/status.css"/>
  <style>
    .wrap{max-width:44rem;margin:0 auto;padding:2.25rem 1.25rem 4rem}
    h1{font-family:var(--serif);font-size:1.5rem;margin:0 0 .4rem}
    .sub{color:var(--mut);font-size:.92rem;margin:0 0 1.5rem}
    .note{background:var(--card);border:1px solid var(--bd);
      border-radius:12px;padding:1rem 1.1rem;margin:0 0 2rem;font-size:.92rem}
    .note strong{color:var(--acc)}
    article{border-top:1px solid var(--bd);padding:1.1rem 0}
    h2{font-size:1rem;margin:0 0 .3rem;font-weight:600;font-family:var(--sans)}
    h2 a{color:var(--tx);text-decoration:none}
    h2 a:hover{color:var(--acc)}
    .meta{color:var(--mut);font-size:.8rem;margin:0 0 .45rem;font-family:var(--mono)}
    p.body{margin:0;color:var(--tx);opacity:.88;font-size:.92rem}
    a{color:var(--acc)}
  </style>
</head>
<body><div class="wrap">
  <h1><xsl:value-of select="rss/channel/title"/></h1>
  <p class="sub"><xsl:value-of select="rss/channel/description"/></p>
  <div class="note">
    <strong>This is a feed, not a page.</strong> Copy this page's address into
    a feed reader and every new post arrives there — no sign-up, no email
    address, nothing to unsubscribe from. Or just
    <a href="/blog/">read the blog</a>.
  </div>
  <xsl:for-each select="rss/channel/item">
    <article>
      <h2>
        <a><xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
          <xsl:value-of select="title"/></a>
      </h2>
      <p class="meta"><xsl:value-of select="pubDate"/></p>
      <p class="body"><xsl:value-of select="description"/></p>
    </article>
  </xsl:for-each>
</div></body>
</html>
</xsl:template>
</xsl:stylesheet>
