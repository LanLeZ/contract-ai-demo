"""
文档解析模块
支持PDF、DOCX、Markdown格式的文件解析
"""
import os
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile


class DocumentParser:
    """文档解析器"""
    
    def __init__(self):
        """初始化解析器"""
        pass
    
    def parse(self, file_path: str, file_type: Optional[str] = None) -> str:
        """
        解析文件，返回纯文本
        Args:
            file_path: 文件路径
            file_type: 文件类型（pdf/docx/md），如果为None则自动检测
        Returns:
            解析后的文本内容
        """
        if file_type is None:
            file_type = self._detect_file_type(file_path)
        
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            return self._parse_pdf(file_path)
        elif file_type == 'docx':
            return self._parse_docx(file_path)
        elif file_type in ['md', 'markdown']:
            return self._parse_markdown(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
    
    def parse_uploaded_file(self, file: UploadFile) -> Tuple[str, str]:
        """
        解析上传的文件
        Args:
            file: FastAPI UploadFile对象
        Returns:
            (文本内容, 文件类型)
        """
        # 检测文件类型
        file_type = self._detect_file_type_from_filename(file.filename)
        
        # 保存临时文件
        temp_path = None
        try:
            # 创建临时文件
            import tempfile
            suffix = Path(file.filename).suffix if file.filename else ''
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                temp_path = tmp_file.name
                # 写入文件内容
                content = file.file.read()
                tmp_file.write(content)
            
            # 解析文件
            text = self.parse(temp_path, file_type)
            return text, file_type
        finally:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _detect_file_type(self, file_path: str) -> str:
        """根据文件扩展名检测文件类型"""
        ext = Path(file_path).suffix.lower()
        if ext == '.pdf':
            return 'pdf'
        elif ext == '.docx':
            return 'docx'
        elif ext in ['.md', '.markdown']:
            return 'md'
        else:
            raise ValueError(f"无法识别的文件类型: {ext}")
    
    def _detect_file_type_from_filename(self, filename: Optional[str]) -> str:
        """从文件名检测文件类型"""
        if not filename:
            raise ValueError("文件名不能为空")
        return self._detect_file_type(filename)
    
    def _parse_pdf(self, file_path: str) -> str:
        """解析PDF文件"""
        try:
            import PyPDF2
        except ImportError:
            try:
                import pdfplumber
                # 使用pdfplumber解析
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text.strip()
            except ImportError:
                raise ImportError("请安装PDF解析库: pip install PyPDF2 或 pip install pdfplumber")
        
        # 使用PyPDF2解析
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            # 如果PyPDF2失败，尝试pdfplumber
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text.strip()
            except ImportError:
                raise Exception(f"PDF解析失败: {str(e)}")
    
    def _parse_docx(self, file_path: str) -> str:
        """解析DOCX文件"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装python-docx: pip install python-docx")
        
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"DOCX解析失败: {str(e)}")
    
    def _parse_markdown(self, file_path: str) -> str:
        """解析Markdown文件（直接读取文本）"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as file:
                    return file.read()
            except Exception as e:
                raise Exception(f"Markdown文件读取失败: {str(e)}")
        except Exception as e:
            raise Exception(f"Markdown文件读取失败: {str(e)}")


