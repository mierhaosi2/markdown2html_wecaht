from collections.abc import Generator
from typing import Any
import os

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.utils.param_utils import get_md_text
from tools.utils.logger_utils import get_logger
from tools.utils.md_utils import MarkdownUtils
from tools.utils.file_utils import get_meta_data
from tools.utils.mimetype_utils import MimeType



class Markdown2htmlTool(Tool):
    logger = get_logger(__name__)

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        md_text = get_md_text(tool_parameters, is_strip_wrapper=True)
        html_header = tool_parameters.get("output_filename")
        prompt_word = tool_parameters.get("prompt_word")
        username = (tool_parameters.get("username") or "").strip()
        intro_text = (tool_parameters.get("intro_text") or "").strip()

        # 拼接头部前言到 md_text 最前面
        preface_parts = []
        if username:
            preface_parts.append(f"@{username}")
        if intro_text:
            preface_parts.append(intro_text)
        if preface_parts:
            md_text = "\n".join(preface_parts) + "\n\n" + md_text

        html_text = md_text
        is_html = "<!doctype html" in html_text.lower() or "<html" in html_text.lower()
        try:
            html_str = html_text if is_html else MarkdownUtils.convert_markdown_to_html(
                md_text, html_header, prompt_word
            )
            result_file_bytes = html_str.encode("utf-8")
            
        except Exception as e:
            self.logger.exception("Failed to convert file")
            yield self.create_text_message(f"Failed to convert markdown text to HTML file, error: {str(e)}")
            return

        yield self.create_blob_message(
            blob=result_file_bytes,
            meta=get_meta_data(
                mime_type=MimeType.HTML,
                output_filename=tool_parameters.get("output_filename"),
            ),
        )
        return
