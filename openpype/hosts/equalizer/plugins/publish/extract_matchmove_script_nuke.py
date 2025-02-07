# -*- coding: utf-8 -*-
"""Extract project for Nuke.

Because original extractor script is intermingled with UI, we had to resort
to this hacky solution. This is monkey-patching 3DEqualizer UI to silence it
during the export. Advantage is that it is still using "vanilla" built-in
export script, so it should be more compatible with future versions of the
software.

TODO: This can be refactored even better, split to multiple methods, etc.

"""
import os
from mock import patch
import six
import pyblish.api
import tde4  # noqa: F401
from openpype.lib import import_filepath
import types
from openpype.pipeline import OptionalPyblishPluginMixin
from openpype.pipeline import publish


class ExtractMatchmoveScriptNuke(publish.Extractor,
                                 OptionalPyblishPluginMixin):
    """Extract Nuke script for matchmove.

    Unfortunately built-in export script from 3DEqualizer is bound to its UI,
    and it is not possible to call it directly from Python. Because of that,
    we are executing the script in the same way as artist would do it, but
    we are patching the UI to silence it and to avoid any user interaction.

    TODO: Utilize attributes defined in ExtractScriptBase
    """

    label = "Extract Nuke Script"
    families = ["matchmove"]
    hosts = ["equalizer"]

    order = pyblish.api.ExtractorOrder

    def process(self, instance = pyblish.api.Instance):

        if not self.is_active(instance.data):
            return

        cam = tde4.getCurrentCamera()
        frame0 = tde4.getCameraFrameOffset(cam)
        frame0 -= 1

        staging_dir = self.staging_dir(instance)
        file_path = os.path.join(staging_dir, "nuke_export.nk")

        # these patched methods are used to silence 3DEqualizer UI:
        def patched_getWidgetValue(requester, key):  # noqa: N802
            """Return value for given key in widget."""
            if key == "file_browser":
                return file_path
            elif key == "startframe_field":
                return tde4.getCameraFrameOffset(cam)
            return ""

        # This is simulating artist clicking on "OK" button
        # in the export dialog.
        def patched_postCustomRequester(*args, **kwargs):  # noqa: N802
            return 1

        # This is silencing success/error message after the script
        # is exported.
        def patched_postQuestionRequester(*args, **kwargs):  # noqa: N802
            return None

        # import maya export script from 3DEqualizer
        exporter_path = os.path.join(instance.data["tde4_path"], "sys_data", "py_scripts", "export_nuke.py")  # noqa: E501
        module = types.ModuleType("export_nuke")
        module.__file__ = exporter_path
        self.log.debug("Patching 3dequalizer requester objects ...")

        with patch("tde4.getWidgetValue", patched_getWidgetValue), \
             patch("tde4.postCustomRequester", patched_postCustomRequester), \
             patch("tde4.postQuestionRequester", patched_postQuestionRequester):  # noqa: E501
            with open(exporter_path, 'r') as f:
                script = f.read()
                if not "import tde4" in script:
                    script = "import tde4\n" + script
            six.exec_(script, module.__dict__)
            self.log.debug("Importing {}".format(exporter_path))

        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': "nk",
            'ext': "nk",
            'files': "nuke_export.nk",
            "stagingDir": staging_dir,
        }
        self.log.debug("output: {}".format(file_path))
        instance.data["representations"].append(representation)
