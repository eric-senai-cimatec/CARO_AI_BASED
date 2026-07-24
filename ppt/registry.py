from ppt.renderers.base import BaseRenderer
from ppt.renderers.bullet_renderer import BulletRenderer
from ppt.renderers.workflow_renderer import WorkflowRenderer
from ppt.renderers.timeline_renderer import TimelineRenderer
from ppt.renderers.orgchart_renderer import OrgChartRenderer
from ppt.renderers.gantt_renderer import GanttRenderer
from ppt.renderers.table_renderer import TableRenderer
from ppt.renderers.image_renderer import ImageRenderer


RENDERERS: dict[str, BaseRenderer] = {
    "bullet": BulletRenderer(),
    "workflow": WorkflowRenderer(),
    "timeline": TimelineRenderer(),
    "orgchart": OrgChartRenderer(),
    "gantt": GanttRenderer(),
    "table": TableRenderer(),
    "image": ImageRenderer(),
}


def get(layout: str) -> BaseRenderer:
    return RENDERERS.get(layout, RENDERERS["bullet"])
