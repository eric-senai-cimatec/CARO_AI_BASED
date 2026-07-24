from pathlib import Path
from pptx.slide import Slide
from ppt.renderers.base import BaseRenderer


class ImageRenderer(BaseRenderer):
    def render(self, slide: Slide, content: dict) -> None:
        path = content.get("path", "") if content else ""
        if not path:
            return
        image = Path(path)
        if not image.exists():
            return
        prs = slide.part.package.presentation_part.presentation
        sw = prs.slide_width
        sh = prs.slide_height
        ml = int(sw * 0.08)
        mt = int(sh * 0.15)
        iw = int(sw * 0.84)
        ih = int(sh * 0.60)
        try:
            slide.shapes.add_picture(str(image), ml, mt, iw, ih)
        except Exception:
            pass
