#!/usr/bin/env python3
"""md2html.py — render a Markdown doc with ```mermaid fences to a standalone HTML for tools/html2pdf.sh.

Deliberately tiny (no dependencies): headings, paragraphs, bullet lists, pipe tables, fenced code,
blockquotes, inline code, bold, italics, links.  ```mermaid fences become <pre class="mermaid"> and the
page loads mermaid from a CDN, so headless Chrome renders the diagrams before printing (give it a
--virtual-time-budget; see docs/RVMS_MECHANICS.md "Rendering").

usage: md2html.py IN.md OUT.html [--title "..."]
"""
import html, re, sys

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

CSS = """
:root{--fg:#1b1f23;--mute:#5b6570;--rule:#d9dee3;--code:#f4f6f8;--accent:#0b5fa5}
body{font:11pt/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--fg);max-width:1000px;margin:0 auto;padding:24px 28px}
h1{font-size:22pt;margin:.2em 0 .3em;letter-spacing:-.01em} h2{font-size:15pt;margin:1.6em 0 .4em;border-bottom:1px solid var(--rule);padding-bottom:.2em}
h3{font-size:12pt;margin:1.2em 0 .3em} p{margin:.45em 0} ul{margin:.3em 0 .6em 1.3em;padding:0} li{margin:.15em 0}
code{font:9.5pt/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:.05em .3em;border-radius:3px}
pre{background:var(--code);padding:.6em .8em;border-radius:4px;overflow-x:auto;font-size:9pt;line-height:1.35} pre code{background:none;padding:0}
pre.mermaid{background:#fff;border:1px solid var(--rule);text-align:center;padding:.6em .4em;page-break-inside:avoid}
pre.mermaid svg{max-width:100%;max-height:245mm;height:auto}
table{border-collapse:collapse;margin:.5em 0 .9em;font-size:9.6pt;width:100%} th,td{border:1px solid var(--rule);padding:.32em .5em;vertical-align:top;text-align:left}
th{background:var(--code)} blockquote{margin:.6em 0;padding:.3em .9em;border-left:3px solid var(--accent);color:var(--mute)}
.meta{color:var(--mute);font-size:9.5pt} hr{border:0;border-top:1px solid var(--rule);margin:1.4em 0}
@page{size:A4;margin:16mm 14mm} @media print{h2{page-break-after:avoid} table,pre.mermaid{page-break-inside:avoid}}
"""

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: "<code>"+m.group(1)+"</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s

def convert(md):
    out=[]; lines=md.splitlines(); i=0
    def flush_para(buf):
        if buf: out.append("<p>"+inline(" ".join(buf))+"</p>"); buf.clear()
    para=[]
    while i < len(lines):
        ln=lines[i]
        if ln.startswith("```"):
            flush_para(para); lang=ln[3:].strip(); i+=1; body=[]
            while i < len(lines) and not lines[i].startswith("```"): body.append(lines[i]); i+=1
            i+=1
            if lang=="mermaid": out.append('<pre class="mermaid">\n'+html.escape("\n".join(body), quote=False)+"\n</pre>")
            else: out.append("<pre><code>"+html.escape("\n".join(body))+"</code></pre>")
            continue
        m=re.match(r"^(#{1,4})\s+(.*)", ln)
        if m: flush_para(para); n=len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); i+=1; continue
        if ln.strip()=="---": flush_para(para); out.append("<hr>"); i+=1; continue
        if ln.startswith("|"):
            flush_para(para); rows=[]
            while i < len(lines) and lines[i].startswith("|"): rows.append(lines[i]); i+=1
            cells=lambda r:[c.strip() for c in r.strip().strip("|").split("|")]
            hdr=cells(rows[0]); body=[cells(r) for r in rows[2:]] if len(rows)>1 and re.match(r"^\|[\s:\-|]+\|$", rows[1].strip()) else [cells(r) for r in rows[1:]]
            t=["<table><thead><tr>"+"".join(f"<th>{inline(c)}</th>" for c in hdr)+"</tr></thead><tbody>"]
            for r in body: t.append("<tr>"+"".join(f"<td>{inline(c)}</td>" for c in r)+"</tr>")
            t.append("</tbody></table>"); out.append("".join(t)); continue
        if re.match(r"^\s*[-*]\s+", ln):
            flush_para(para); items=[]
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item=re.sub(r"^\s*[-*]\s+","",lines[i]); i+=1
                while i < len(lines) and lines[i].startswith("  ") and not re.match(r"^\s*[-*]\s+", lines[i]): item+=" "+lines[i].strip(); i+=1
                items.append(item)
            out.append("<ul>"+"".join(f"<li>{inline(x)}</li>" for x in items)+"</ul>"); continue
        if ln.startswith(">"):
            flush_para(para); q=[]
            while i < len(lines) and lines[i].startswith(">"): q.append(lines[i][1:].strip()); i+=1
            out.append("<blockquote>"+inline(" ".join(q))+"</blockquote>"); continue
        if ln.strip()=="": flush_para(para); i+=1; continue
        para.append(ln.strip()); i+=1
    flush_para(para)
    return "\n".join(out)

def main():
    src, dst = sys.argv[1], sys.argv[2]
    title = sys.argv[sys.argv.index("--title")+1] if "--title" in sys.argv else "Document"
    body = convert(open(src, encoding="utf-8").read())
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style>
<script src="{MERMAID}"></script>
<script>mermaid.initialize({{startOnLoad:true,theme:'neutral',securityLevel:'loose',flowchart:{{useMaxWidth:true,htmlLabels:true}},sequence:{{useMaxWidth:true}},gantt:{{useMaxWidth:true}}}});</script>
</head><body>
{body}
</body></html>"""
    open(dst, "w", encoding="utf-8").write(page)
    print(f"md2html: wrote {dst}")

if __name__ == "__main__":
    main()
