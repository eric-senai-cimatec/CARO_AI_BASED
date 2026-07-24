from abc import ABC, abstractmethod
from pptx.slide import Slide


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, slide: Slide, content: dict) -> None:
        ...
