from abc import ABC, abstractmethod
from typing import Dict

class AudioParserBase(ABC):
    @abstractmethod
    def get_audio_info(self, url: str) -> Dict[str, str]:
        """
        输入音频页面链接，返回包含音频直链和元信息的字典。
        必须由子类实现。

        :param url: 音频页面链接
        :return: dict，包含至少以下字段：
            - audio_url: str，音频直链
            - title: str，标题
            - description: str，简介（可选，若无则为空字符串）
        """
        pass 