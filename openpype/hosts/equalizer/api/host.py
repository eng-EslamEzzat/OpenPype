"""
3dequalizer host implementation.

note:
    3dequalizer Release 5 uses Python 2.7
"""

import json
import os
import re

from attr import asdict
from attr.exceptions import NotAnAttrsClassError
import pyblish.api
import tde4  # noqa: F401
from qtpy import QtCore, QtWidgets

from openpype.host import HostBase, ILoadHost, IPublishHost, IWorkfileHost
from openpype.hosts.equalizer import EQUALIZER_HOST_DIR
from openpype.pipeline import (
    register_creator_plugin_path,
    register_loader_plugin_path,
    legacy_io
)

CONTEXT_REGEX = re.compile(
    r"AYON_CONTEXT::(?P<context>.*?)::AYON_CONTEXT_END",
    re.DOTALL)
PLUGINS_DIR = os.path.join(EQUALIZER_HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")


class EqualizerHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
    name = "equalizer"
    _instance = None

    def __new__(cls):
        if not hasattr(cls, "_instance") or not cls._instance:
            cls._instance = super(EqualizerHost, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self._qapp = None
        super(EqualizerHost, self).__init__()

    def workfile_has_unsaved_changes(self):
        """Return the state of the current workfile.

        3DEqualizer returns state as 1 or zero, so we need to invert it.

        Returns:
            bool: True if the current workfile has unsaved changes.
        """
        return not bool(tde4.isProjectUpToDate())

    def get_workfile_extensions(self):
        return [".3de"]

    def save_workfile(self, filepath=None):
        result = tde4.saveProject(filepath)
        if not bool(result):
            raise RuntimeError("Failed to save workfile %s."%filepath)

        return filepath

    def open_workfile(self, filepath):
        result = tde4.loadProject(filepath)
        if not bool(result):
            raise RuntimeError("Failed to open workfile %s."%filepath)

        return filepath

    def get_current_workfile(self):
        current_filepath = tde4.getProjectPath()
        if not current_filepath:
            return None

        return current_filepath


    def get_overscan(self):
        context = self.get_context_data()
        if "overscan" in context:
            return context.get("overscan", {})
        return {}

    def set_overscan(self, overscan_width, overscan_height):
        context_data = self.get_context_data()
        overscan = self.get_overscan()
        if not overscan:
            overscan = {
                "width": overscan_width,
                "height": overscan_height
            }
        else:
            overscan["width"] = overscan_width
            overscan["height"] = overscan_height

        context_data["overscan"] = overscan
        self.update_context_data(context_data, changes={})

    def get_containers(self):
        context = self.get_context_data()
        if context:
            return context.get("containers", [])
        return []

    def add_container(self, container):
        context_data = self.get_context_data()
        containers = self.get_containers()

        for _container in containers:
            if _container["name"] == container.name and _container["namespace"] == container.namespace:  # noqa: E501
                containers.remove(_container)
                break

        try:
            containers.append(asdict(container))
        except NotAnAttrsClassError:
            print("not an attrs class")
            containers.append(container)

        context_data["containers"] = containers
        self.update_context_data(context_data, changes={})

    def get_context_data(self):
        """Get context data from the current workfile.

        3Dequalizer doesn't have any custom node or other
        place to store metadata, so we store context data in
        the project notes encoded as JSON and wrapped in a
        special guard string `AYON_CONTEXT::...::AYON_CONTEXT_END`.

        Returns:
            dict: Context data.
        """

        # sourcery skip: use-named-expression
        m = re.search(CONTEXT_REGEX, tde4.getProjectNotes())
        try:
            context = json.loads(m.groupdict()["context"]) if m else {}
        except ValueError:
            self.log.debug("context data is not valid json")
            context = {}

        return context

    def update_context_data(self, data, changes):
        """Update context data in the current workfile.

        Serialize context data as json and store it in the
        project notes. If the context data is not found, create
        a placeholder there. See `get_context_data` for more info.

        Args:
            data (dict): Context data.
            changes (dict): Changes to the context data.

        Raises:
            RuntimeError: If the context data is not found.
        """
        m = re.search(CONTEXT_REGEX, tde4.getProjectNotes())
        if not m:
            # context data not found, create empty placeholder
            tde4.setProjectNotes("AYON_CONTEXT::::AYON_CONTEXT_END")

        original_data = self.get_context_data()

        updated_data = original_data.copy()
        updated_data.update(data)
        update_str = json.dumps(updated_data or {}, indent=4)

        tde4.setProjectNotes(
            re.sub(
                CONTEXT_REGEX,
                "AYON_CONTEXT::%s::AYON_CONTEXT_END"%update_str,
                tde4.getProjectNotes()
            )
        )
        tde4.updateGUI()

    def install(self):
        if not QtCore.QCoreApplication.instance():
            app = QtWidgets.QApplication([])
            self._qapp = app
            self._qapp.setQuitOnLastWindowClosed(False)

        pyblish.api.register_plugin_path(PUBLISH_PATH)
        pyblish.api.register_host("equalizer")

        register_loader_plugin_path(LOAD_PATH)
        register_creator_plugin_path(CREATE_PATH)

        # heartbeat_interval = os.getenv("AYON_TDE4_HEARTBEAT_INTERVAL") or 500
        # tde4.setTimerCallbackFunction(
        #     "EqualizerHost._timer", int(heartbeat_interval))


    def _set_project(self):
        workdir = legacy_io.Session["AVALON_WORKDIR"]
        if os.path.exists(workdir):
            projects = []
            workdir_files = os.listdir(workdir)
            if len(workdir_files) > 0:
                for f in os.listdir(workdir):
                    if legacy_io.Session["AVALON_ASSET"] in f:
                        projects.append(f)
                projects.sort()
                tde4.loadProject(os.path.join(workdir, projects[-1]))


    @staticmethod
    def _timer():
        QtWidgets.QApplication.instance().processEvents(
            QtCore.QEventLoop.AllEvents)

    @classmethod
    def get_host(cls):
        return cls._instance

    def get_main_window(self):
        return self._qapp.activeWindow()
