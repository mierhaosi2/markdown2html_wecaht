import re
import markdown
from bs4 import BeautifulSoup

CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')
# 正则表达式组合：平假名 + 片假名 + 日文汉字
JAPANESE_CHAR_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')


class MarkdownUtils:
    CSS_GLOBAL_STYLE = """
    <style>
        /* Reset */
        body, h1, h2, h3, h4, h5, h6, p, blockquote, pre, code, table, th, td, ul, ol {
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 16px;
            line-height: 1.75;
            color: #2c2c2c;
            background-color: #f9f9f9;
            padding: 1em;
            word-break: break-word;
        }

        /* Headings */
        h1 { font-size: 2em; margin: 1em 0 0.5em; font-weight: 600; }
        h2 { font-size: 1.75em; margin: 1em 0 0.5em; font-weight: 600; }
        h3 { font-size: 1.5em; margin: 1em 0 0.5em; font-weight: 600; }
        h4, h5, h6 { font-size: 1.25em; margin: 1em 0 0.5em; font-weight: 500; }

        /* Paragraphs & Lists */
        p, ul, ol {
            margin: 0.8em 0;
        }

        ul, ol {
            padding-left: 2em;
        }

        blockquote {
            border-left: 4px solid #d0d0d0;
            padding-left: 1em;
            margin: 1em 0;
            color: #555;
            background-color: #f0f0f0;
        }

        /* Tables */
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }

        th, td {
            border: 1px solid #ccc;
            padding: 0.5em;
            text-align: left;
        }

        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }

        /* Images */
        img {
          display: block;
          max-width: 90vw;
          max-height: 80vh;
          height: auto;
          margin: 1em auto;
          border-radius: 4px;
          clear: both;
        }
        
        /* 当屏幕宽度小于 1080px：取消 block 和居中，让图片靠左 */
        @media (min-width: 1081px) {
            img {
                margin-left: 0 !important;
                margin-right: auto !important;
              }
        }


        /* Code & Pre */
        pre {
            background-color: #f4f4f4;
            padding: 1em;
            overflow: auto;
            border-radius: 6px;
            font-size: 14px;
            line-height: 1.5;
            margin: 1em 0;
        }

        code {
            background-color: #f2f2f2;
            padding: 0.2em 0.4em;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 14px;
        }

        /* Links */
        a {
            color: #007bff;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* Responsive */
        @media (max-width: 768px) {
            body {
                font-size: 15px;
                padding: 0.8em;
            }

            pre {
                font-size: 13px;
            }

            h1 { font-size: 1.6em; }
            h2 { font-size: 1.4em; }
            h3 { font-size: 1.25em; }
        }
    </style>
    """

    @classmethod
    def convert_markdown_to_html(cls, md_text: str, html_header: str, prompt_word: str) -> str:
        body_html = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
        soup = BeautifulSoup(body_html, "html.parser")

        # 遍历所有 <li>，处理换行和 '- '
        for li in soup.find_all("li"):
            text = li.get_text("\n", strip=True)

            # 1. 先按换行拆分
            lines = []
            for part in text.splitlines():
                part = part.strip()
                if not part:
                    continue
                # 2. 再按行内的 '- ' 拆分
                subparts = [p.strip() for p in re.split(r'\s*-\s+', part) if p.strip()]
                lines.extend(subparts)

            # 清空 <li> 并插入新的 <br> 分行
            li.clear()
            for i, line in enumerate(lines):
                li.append(line)
                if i < len(lines) - 1:
                    li.append(soup.new_tag("br"))

        global_css = cls.CSS_GLOBAL_STYLE

        print(soup)
        return f""" 
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,minimum-scale=1.0,user-scalable=no,viewport-fit=cover">
            <title>{html_header}</title>
            {global_css}
        </head>
        <body>
            {body_html}
            <div style="font-size:15px;color:#f80;">
                {prompt_word}
            </div>
        </body>
        </html>
        """

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
