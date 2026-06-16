import re
import os
import markdown
from bs4 import BeautifulSoup

CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')
# 正则表达式组合：平假名 + 片假名 + 日文汉字
JAPANESE_CHAR_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')

_CSS_PATH = os.path.join(os.path.dirname(__file__), "style.css")


def _load_css() -> str:
    with open(_CSS_PATH, "r", encoding="utf-8") as f:
        return f"<style>\n{f.read()}\n</style>"


_DATA_SOURCE_PATTERN = re.compile(r'^数据来源', re.MULTILINE)


def _extract_data_source(soup: BeautifulSoup) -> str:
    """
    从 soup 顶层节点中找出以「数据来源」开头的 <p>，将其从树中移除，
    返回这些节点的 HTML 字符串（用于独立渲染）。
    """
    matched = []
    for node in list(soup.children):
        if getattr(node, "name", None) == "p" and _DATA_SOURCE_PATTERN.match(node.get_text(strip=True)):
            matched.append(str(node))
            node.decompose()
    return "".join(matched)


def _detect_split_tag(top_nodes: list) -> str:
    """
    自动检测用于分段的标签层级：
    有 h1 → 用 h1；无 h1 有 h2 → 用 h2；无 h2 有 h3 → 用 h3；否则返回 p（不分段）。
    """
    names = {getattr(n, "name", None) for n in top_nodes}
    for tag in ("h1", "h2", "h3"):
        if tag in names:
            return tag
    return "p"


def _is_footer_section(nodes: list, split_tag: str) -> bool:
    """
    判断一组节点是否为尾注：
    不含比 split_tag 低一级的标题 / ul / ol / table，且纯文本 < 200 字符。
    """
    lower_headings = {"h1": ("h2", "h3"), "h2": ("h3",), "h3": (), "p": ()}.get(split_tag, ())
    for node in nodes:
        if getattr(node, "name", None) in (*lower_headings, "ul", "ol", "table"):
            return False
    text = "".join(n.get_text() for n in nodes).strip()
    return len(text) < 200


def _wrap_sections(soup: BeautifulSoup) -> str:
    """
    自动按最高可用标题层级（h1 > h2 > h3）将顶层节点分组，
    无标题时整体包一个 section-body，不按 p 拆分。
      - section-preface : 第一个分隔标签之前的内容
      - section-body    : 每个分隔标签及其下属内容
      - section-footer  : 最后一组若判定为尾注则改为 footer
    """
    top_nodes = list(soup.children)
    split_tag = _detect_split_tag(top_nodes)

    # 无标题时：含 @mention 的首段单独作 preface，其余整体包成 section-body
    if split_tag == "p":
        first = top_nodes[0] if top_nodes else None
        has_mention = (
            first is not None
            and getattr(first,"name",None) == "p"
            and first.find(class_="mention") is not None
        )

        if has_mention and len(top_nodes) > 1:
            preface_html = str(first)
            body_html = "".join(str(n) for n in top_nodes[1:])
            return (
                f'<section class="section-preface">\n{preface_html}\n</section>\n'
                f'<section class="section-body">\n{body_html}\n</section>'
            )
        inner = "".join(str(n) for n in top_nodes)
        return f'<section class="section-body">\n{inner}\n</section>'


    groups: list[dict] = []
    current: list = []

    for node in top_nodes:
        if getattr(node, "name", None) == split_tag:
            if current:
                groups.append({"nodes": current})
            current = [node]
        else:
            current.append(node)

    if current:
        groups.append({"nodes": current})

    # 标注每组的 section 类型
    for i, group in enumerate(groups):
        first = group["nodes"][0]
        is_split_group = getattr(first, "name", None) == split_tag

        if i == 0 and not is_split_group:
            group["cls"] = "preface"
        elif i == len(groups) - 1 and is_split_group and _is_footer_section(group["nodes"][1:], split_tag):
            group["cls"] = "footer"
        else:
            group["cls"] = "body" if is_split_group else "preface"

    html_parts = []
    for group in groups:
        inner = "".join(str(n) for n in group["nodes"])
        html_parts.append(f'<section class="section-{group["cls"]}">\n{inner}\n</section>')

    return "\n".join(html_parts)


class MarkdownUtils:

    @classmethod
    def convert_markdown_to_html(cls, md_text: str, html_header: str, prompt_word: str) -> str:
        body_html = markdown.markdown(md_text, extensions=["extra", "sane_lists", "nl2br"])
        soup = BeautifulSoup(body_html, "html.parser")

        # 遍历所有 <li>，处理换行和 '- '
        for li in soup.find_all("li"):
            text = li.get_text("\n", strip=True)

            lines = []
            for part in text.splitlines():
                part = part.strip()
                if not part:
                    continue
                subparts = [p.strip() for p in re.split(r'\s*-\s+', part) if p.strip()]
                lines.extend(subparts)

            li.clear()
            for i, line in enumerate(lines):
                li.append(line)
                if i < len(lines) - 1:
                    li.append(soup.new_tag("br"))

        # 把段落里的 @用户名 包成 <span class="mention">
        _MENTION_RE = re.compile(r'(@[\w\u4e00-\u9fff]+)')
        for p in soup.find_all("p"):
            new_contents = []
            for child in list(p.children):
                if isinstance(child, str) and _MENTION_RE.search(child):
                    parts = _MENTION_RE.split(child)
                    for part in parts:
                        if _MENTION_RE.fullmatch(part):
                            span = soup.new_tag("span", attrs={"class": "mention"})
                            span.string = part
                            new_contents.append(span)
                        else:
                            new_contents.append(part)
                else:
                    new_contents.append(child)
            p.clear()
            for item in new_contents:
                p.append(item)

        # 给每个 table 包一层可滚动的 wrapper
        for table in soup.find_all("table"):
            wrapper = soup.new_tag("div", attrs={"class": "table-wrapper"})
            table.wrap(wrapper)

        data_source_html = _extract_data_source(soup)
        sectioned_html = _wrap_sections(soup)
        global_css = _load_css()
        prompt_html = f'<div class="prompt-word">{prompt_word}</div>' if prompt_word else ""
        data_source_block = (
            f'<div class="data-source">{data_source_html}</div>'
            if data_source_html else ""
        )

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,minimum-scale=1.0,user-scalable=no,viewport-fit=cover">
    <title>{html_header}</title>
    {global_css}
</head>
<body>
    <div class="container">
        {sectioned_html}
        {data_source_block}
    </div>
    {prompt_html}
    <script>
    (function () {{
        // 图片横竖版自适应
        function applyImageClass(img) {{
            if (img.naturalWidth >= img.naturalHeight) {{
                img.classList.add('img-landscape');
            }} else {{
                img.classList.add('img-portrait');
            }}
        }}
        document.querySelectorAll('img').forEach(function (img) {{
            if (img.complete && img.naturalWidth > 0) {{
                applyImageClass(img);
            }} else {{
                img.addEventListener('load', function () {{ applyImageClass(img); }});
            }}
        }});
    }})();
    </script>
</body>
</html>"""

    @classmethod
    def get_html_url(html_text: str):
        return f"""
            {html_text}
        """
    
    @staticmethod
    def strip_markdown_wrapper(md_text: str) -> str:
        md_text = md_text.strip()
        wrapper = "```"

        if not (md_text.startswith(wrapper) and md_text.endswith(wrapper)):
            return md_text

        # Remove the outer wrappers
        content = md_text[len(wrapper):-len(wrapper)]

        # Find the first newline to see if there's a language identifier
        # Note: We are looking for escaped newline `\n` because this function
        # is called before newline normalization in param_utils.py.
        try:
            first_newline_index = content.index('\n')
            # The part before the newline is the potential language identifier
            lang_identifier = content[:first_newline_index].strip()
            
            # A simple heuristic: if the first line is a single word without spaces, it's a language.
            if ' ' not in lang_identifier and len(lang_identifier) < 20:
                # The real content starts after the newline
                return content[first_newline_index + len('\n'):]
            else:
                # It's not a language identifier, so it's part of the content
                return content
        except ValueError:
            # No newline found, so no language identifier
            return content

    @staticmethod
    def contains_chinese(md_text: str) -> bool:
        return bool(CHINESE_CHAR_PATTERN.search(md_text))

    @ staticmethod
    def contains_japanese(md_text: str) -> bool:
        return bool(JAPANESE_CHAR_PATTERN.search(md_text))

if __name__ == '__main__':
    MarkdownUtils.convert_markdown_to_html('美股交易费用主要包括以下几项：\n\n1. 佣金 \n- 费用：成交金额的0.15%，最低20美元/单 \n- 收费方：复星国际证券\n\n2. 平台使用费 \n- 费用：豁免（不收取） \n- 收费方：复星国际证券\n\n3. 其他费用 \n- 美国证监征费：根据美国证监会最新标准收取，最低0.01美元，无上限 \n- 美国金融业监管局交易活动费（仅卖出时收取）：每股$0.000166美元（最低$0.01美元，最高$8.3美元）\n\n4. 其他服务相关收费 \n- 代收股息费：现金股息的1.50%（最低$6美元，最高$70美元） \n- 代履行投票服务：每个申请150美元 \n- 股息税：一般为现金股息的30%，最终比例以具体股票注册地税率为准 \n- 其他企业行动：$25美元，另加中介服务费用\n\n所有费用通常以美元结算。详细费用以当日结单或月结单为准，实际收取如有变更，以最新公告为准','13',123)
