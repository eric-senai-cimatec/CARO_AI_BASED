from pptx.slide import Slide
from ppt.renderers.base import BaseRenderer


class TableRenderer(BaseRenderer):
    def render(self, slide: Slide, content: dict) -> None:
        pass
