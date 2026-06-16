from collections.abc import Generator
from typing import Any
import base64

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.utils.logger_utils import get_logger
from tools.utils.file_utils import get_meta_data
from tools.utils.mimetype_utils import MimeType


class FileUploadTool(Tool):
    logger = get_logger(__name__)

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        html_file = tool_parameters.get("html_file")
        output_filename = tool_parameters.get("output_filename")
        
        if not html_file:
            yield self.create_text_message("Failed to upload HTML file: html_file is required")
            return

        try:
            # 处理文件数据：可能是文件路径、base64字符串、字节或字典
            if isinstance(html_file, str):
                # 如果是字符串，可能是文件路径或base64编码的内容
                # 先尝试作为base64解码
                try:
                    result_file_bytes = base64.b64decode(html_file)
                except Exception:
                    # 如果不是base64，尝试读取文件路径
                    try:
                        with open(html_file, 'rb') as f:
                            result_file_bytes = f.read()
                    except Exception:
                        # 如果都不是，当作HTML内容直接编码
                        result_file_bytes = html_file.encode("utf-8")
            elif isinstance(html_file, bytes):
                result_file_bytes = html_file
            elif isinstance(html_file, dict):
                # 如果是字典，可能包含文件数据
                file_data = html_file.get("data") or html_file.get("content") or html_file.get("file")
                if isinstance(file_data, str):
                    try:
                        result_file_bytes = base64.b64decode(file_data)
                    except Exception:
                        result_file_bytes = file_data.encode("utf-8")
                elif isinstance(file_data, bytes):
                    result_file_bytes = file_data
                else:
                    yield self.create_text_message(f"Failed to upload HTML file: unsupported file data format")
                    return
            else:
                yield self.create_text_message(f"Failed to upload HTML file: unsupported file type: {type(html_file)}")
                return
            
        except Exception as e:
            self.logger.exception("Failed to convert file")
            yield self.create_text_message(f"Failed to upload HTML file, error: {str(e)}")
            return

        yield self.create_blob_message(
            blob=result_file_bytes,
            meta=get_meta_data(
                mime_type=MimeType.HTML,
                output_filename=output_filename,
            ),
        )
        return

