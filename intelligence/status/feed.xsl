<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
<xsl:output method="html" encoding="utf-8" indent="yes"/>
<xsl:template match="/">
<html lang="en">
  <xsl:attribute name="data-palette"><xsl:value-of
    select="/atom:feed/@data-palette"/></xsl:attribute>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title><xsl:value-of select="atom:feed/atom:title"/></title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&amp;family=Playfair+Display:wght@600&amp;family=DM+Mono:wght@400&amp;display=swap" rel="stylesheet"/>
  <!-- The site's own stylesheet, not a copy of its colours. That is what makes
       the ground, the type and the weekday palette the same here as on the
       page this was linked from; a second set of hex values would drift from
       the first the day either changed. -->
  <link rel="stylesheet" href="/intelligence/status/status.css"/>
  <style>
    .wrap{max-width:44rem;margin:0 auto;padding:2.25rem 1.25rem 4rem}
    h1{font-family:var(--serif);font-size:1.5rem;margin:0 0 .4rem}
    .sub{color:var(--mut);font-size:.92rem;margin:0 0 1.5rem}
    .note{background:var(--card);border:1px solid var(--bd);
      border-radius:12px;padding:1rem 1.1rem;margin:0 0 2rem;font-size:.92rem}
    .note strong{color:var(--acc)}
    .note code{background:rgba(128,128,128,.16);padding:.1rem .35rem;
      border-radius:4px;font-family:var(--mono);font-size:.86em}
    article{border-top:1px solid var(--bd);padding:1.1rem 0}
    h2{font-size:1rem;margin:0 0 .3rem;font-weight:600;font-family:var(--sans)}
    h2 a{color:var(--tx);text-decoration:none}
    h2 a:hover{color:var(--acc)}
    .meta{color:var(--mut);font-size:.8rem;margin:0 0 .45rem;
      font-family:var(--mono)}
    .open{color:var(--red);font-weight:600}
    p.body{margin:0;color:var(--tx);opacity:.88;font-size:.92rem}
    a{color:var(--acc)}
  </style>
</head>
<body><div class="wrap">
  <h1><xsl:value-of select="atom:feed/atom:title"/></h1>
  <p class="sub"><xsl:value-of select="atom:feed/atom:subtitle"/></p>
  <div class="note">
    <strong>This is a feed, not a page.</strong> Copy this page's address into
    a feed reader, or into Slack with
    <code>/feed subscribe &lt;address&gt;</code>, and you will be told when a
    cloud breaks and again when it clears. No sign-up, no email address, and
    nothing to unsubscribe from &#8212; you are not on a list, because there is
    no list. <a href="/intelligence/status/">Back to the status page</a>.
  </div>
  <xsl:for-each select="atom:feed/atom:entry">
    <article>
      <h2>
        <a><xsl:attribute name="href"><xsl:value-of
           select="atom:link/@href"/></xsl:attribute>
          <xsl:value-of select="atom:title"/></a>
      </h2>
      <p class="meta">
        <xsl:if test="atom:category[@term='open']">
          <span class="open">Open now</span><xsl:text> &#183; </xsl:text>
        </xsl:if>
        <xsl:value-of select="atom:updated"/>
      </p>
      <p class="body"><xsl:value-of select="atom:summary"/></p>
    </article>
  </xsl:for-each>
</div></body>
</html>
</xsl:template>
</xsl:stylesheet>
