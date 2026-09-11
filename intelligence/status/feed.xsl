<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
<xsl:output method="html" encoding="utf-8" indent="yes"/>
<xsl:template match="/">
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title><xsl:value-of select="atom:feed/atom:title"/></title>
  <style>
    :root{color-scheme:dark}
    body{margin:0;background:#14100F;color:#EDEBE6;
      font:16px/1.65 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
    .wrap{max-width:44rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
    h1{font-size:1.5rem;margin:0 0 .4rem;font-weight:600}
    .sub{color:#9C9A94;font-size:.92rem;margin:0 0 1.5rem}
    .note{background:#1E1A19;border:1px solid rgba(196,164,132,.28);
      border-radius:12px;padding:1rem 1.1rem;margin:0 0 2rem;font-size:.92rem}
    .note strong{color:#C4A484}
    .note code{background:rgba(255,255,255,.06);padding:.1rem .35rem;
      border-radius:4px;font-size:.86em}
    article{border-top:1px solid rgba(255,255,255,.09);padding:1.1rem 0}
    h2{font-size:1rem;margin:0 0 .3rem;font-weight:600}
    h2 a{color:#EDEBE6;text-decoration:none}
    h2 a:hover{color:#C4A484}
    .meta{color:#9C9A94;font-size:.8rem;margin:0 0 .45rem}
    .open{color:#E0A458;font-weight:600}
    p.body{margin:0;color:#C8C5BE;font-size:.92rem}
    a{color:#C4A484}
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
    nothing to unsubscribe from — you are not on a list, because there is no
    list. <a href="/intelligence/status/">Back to the status page</a>.
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
          <span class="open">Open now</span><xsl:text> · </xsl:text>
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
