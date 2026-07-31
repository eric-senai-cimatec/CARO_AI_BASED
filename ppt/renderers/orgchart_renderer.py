from pptx.slide import Slide

from ppt.renderers.base import BaseRenderer
from ppt.renderers.orgchart.models import OrgChart
from ppt.renderers.orgchart.layout import TreeLayout
from ppt.renderers.orgchart.rendering import OrgChartRenderer as _Renderer
from ppt.renderers.orgchart.utils import Dimensions, ColorPalette


class OrgChartRenderer(BaseRenderer):
    def render(self, slide: Slide, content: dict) -> None:
        if not content:
            return

        chart = OrgChart.from_json(content)
        if not chart.root:
            return

        prs = slide.part.package.presentation_part.presentation
        sw = prs.slide_width
        sh = prs.slide_height

        dims = Dimensions(
            slide_width=float(sw),
            slide_height=float(sh),
            margin_left=30.0,
            margin_right=30.0,
            margin_top=50.0,
            margin_bottom=20.0,
        )

        layout = TreeLayout(dims)
        layout.layout(chart)

        renderer = _Renderer(slide, dims)
        renderer.render(chart)
