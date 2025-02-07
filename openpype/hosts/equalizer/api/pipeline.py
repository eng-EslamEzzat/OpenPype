
import attr
from openpype.pipeline import AVALON_CONTAINER_ID
import contextlib
import tde4

@attr.s
class Container(object):
    name = attr.ib(default=None)
    id = attr.ib(init=False, default=AVALON_CONTAINER_ID)
    namespace = attr.ib(default="")
    loader = attr.ib(default=None)
    representation = attr.ib(default=None)


@contextlib.contextmanager
def maintained_model_selection():
    """Maintain model selection during context."""

    point_groups = tde4.getPGroupList()
    point_group = next(
        (
            pg for pg in point_groups
            if tde4.getPGroupType(pg) == "CAMERA"
        ), None
    )
    selected_models = tde4.get3DModelList(point_group, 1)\
        if point_group else []
    try:
        yield
    finally:
        if point_group:
            # 3 restore model selection
            for model in tde4.get3DModelList(point_group, 0):
                if model in selected_models:
                    tde4.set3DModelSelectionFlag(point_group, model, 1)
                else:
                    tde4.set3DModelSelectionFlag(point_group, model, 0)
