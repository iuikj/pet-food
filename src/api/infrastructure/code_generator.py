"""
验证码生成器实现
"""
import random
import string

from src.api.infrastructure.interfaces import ICodeGenerator


class NumericCodeGenerator(ICodeGenerator):
    """数字验证码生成器"""

    def generate(self, length: int = 6) -> str:
        """生成数字验证码"""
        return ''.join(random.choices(string.digits, k=length))


class AlphanumericCodeGenerator(ICodeGenerator):
    """字母数字验证码生成器"""

    def generate(self, length: int = 6) -> str:
        """生成字母数字验证码（排除易混淆字符）"""
        # 排除易混淆的字符：0, 1, I, l, O, o
        chars = string.digits + string.ascii_letters
        exclude = {'0', '1', 'I', 'l', 'O', 'o'}
        safe_chars = ''.join(c for c in chars if c not in exclude)
        return ''.join(random.choices(safe_chars, k=length))
