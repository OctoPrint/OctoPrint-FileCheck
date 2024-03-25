__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 The OctoPrint Project - Released under terms of the AGPLv3 License"

import os
import re
import threading
from collections import defaultdict

# noinspection PyCompatibility
from concurrent.futures import ThreadPoolExecutor

import flask
import octoprint.access.permissions
import octoprint.events
import octoprint.plugin
import sarge
from flask_babel import gettext
from octoprint.access import ADMIN_GROUP, USER_GROUP
from octoprint.filemanager import get_file_type

CHECKS = {
    "travel_speed": {
        "pattern": "{travel_speed}",
    },
    "leaked_api_key": {
        "pattern": r";\s+printhost_apikey\s+=\s+\S+",
        "regex": True,
    },
}


class FileCheckPlugin(
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.SimpleApiPlugin,
):
    def __init__(self):
        self._executor = ThreadPoolExecutor()

        self._native_grep_available = True

        self._full_check_lock = threading.RLock()
        self._check_result = {}

    def initialize(self):
        try:
            sarge.run(["grep", "-q", "--version"])
        except Exception as exc:
            if "Command not found" in str(exc):
                self._native_grep_available = False
        self._logger.info(f"Native grep available: {self._native_grep_available}")

    ##~~ AssetPlugin API

    def get_assets(self):
        return {
            "js": [
                "js/file_check.js",
            ],
            "clientjs": [
                "clientjs/file_check.js",
            ],
        }

    ##~~ EventHandlerPlugin API

    def on_event(self, event, payload):
        if event == octoprint.events.Events.FILE_ADDED:
            self._executor.submit(
                self._validate_file, payload["storage"], payload["path"], payload["type"]
            )

        elif event == octoprint.events.Events.FILE_SELECTED:
            file_type = get_file_type(payload["name"])
            self._executor.submit(
                self._validate_file, payload["origin"], payload["path"], file_type
            )

        elif event == octoprint.events.Events.FILE_REMOVED:
            dirty = True
            with self._full_check_lock:
                for check in self._check_result:
                    current = len(self._check_result[check])
                    self._check_result[check] = [
                        path
                        for path in self._check_result[check]
                        if path != f"{payload['storage']}:{payload['path']}"
                    ]
                    dirty = dirty or len(self._check_result[check]) < current
            if dirty:
                self._trigger_check_update()

        elif event == octoprint.events.Events.FOLDER_REMOVED:
            dirty = False
            with self._full_check_lock:
                for check in self._check_result:
                    current = len(self._check_result[check])
                    self._check_result[check] = [
                        path
                        for path in self._check_result[check]
                        if not path.startswith(f"{payload['storage']}:{payload['path']}/")
                    ]
                    dirty = dirty or len(self._check_result[check]) < current
            if dirty:
                self._trigger_check_update()

    ##~~ SimpleApiPlugin API

    def on_api_get(self, request):
        if not octoprint.access.permissions.Permissions.PLUGIN_FILE_CHECK_RUN.can():
            return flask.make_response("Insufficient rights", 403)

        response = {
            "native_grep": self._native_grep_available,
            "check_result": self._check_result,
        }
        return flask.jsonify(**response)

    def get_api_commands(self):
        return {"check_all": []}

    def on_api_command(self, command, data):
        if command == "check_all":
            if not octoprint.access.permissions.Permissions.PLUGIN_FILE_CHECK_RUN.can():
                return flask.make_response("Insufficient rights", 403)

            self._start_full_check()
            return flask.Response(
                status=202,
                headers={"Location": flask.url_for("index") + "api/plugin/file_check"},
            )

    ##~~ Additional permissions hook

    def get_additional_permissions(self):
        return [
            {
                "key": "RUN",
                "name": "Run File Check",
                "description": gettext("Allows to run File Check and view the results."),
                "default_groups": [USER_GROUP, ADMIN_GROUP],
                "roles": ["run"],
            }
        ]

    ##~~ SoftwareUpdate hook

    def get_update_information(self):
        return dict(
            file_check=dict(
                displayName="File Check Plugin",
                displayVersion=self._plugin_version,
                # version check: github repository
                type="github_release",
                user="OctoPrint",
                repo="OctoPrint-FileCheck",
                current=self._plugin_version,
                stable_branch={
                    "name": "Stable",
                    "branch": "master",
                    "commitish": ["devel", "master"],
                },
                prerelease_branches=[
                    {
                        "name": "Prerelease",
                        "branch": "devel",
                        "commitish": ["devel", "master"],
                    }
                ],
                # update method: pip
                pip="https://github.com/OctoPrint/OctoPrint-FileCheck/archive/{target_version}.zip",
            )
        )

    ##~~ Internal logic & helpers

    def _start_full_check(self):
        with self._full_check_lock:
            self._check_result = None
            job = self._executor.submit(self._check_all_files)
            job.add_done_callback(self._full_check_done)

    def _full_check_done(self, future):
        try:
            result = future.result()
        except Exception:
            self._logger.exception("Full check failed")
            return

        path_to_checks = defaultdict(list)
        for check, matches in result.items():
            for match in matches:
                path_to_checks[match].append(check)

        self._trigger_check_update()

    def _check_all_files(self):
        with self._full_check_lock:
            if not self._native_grep_available:
                return {}

            path = self._settings.global_get_basefolder("uploads")
            self._logger.info(f"Running check on all files in {path} (local storage)")

            full_check_result = {}
            for check, params in CHECKS.items():
                self._logger.info(f"Running check {check}")
                pattern = params["pattern"]
                sanitized = self._sanitize_pattern(
                    pattern,
                    incl_comments=params.get("incl_comments", False),
                    regex=params.get("regex", False),
                )

                result = sarge.capture_both(["grep", "-r", "-E", sanitized, path])
                if result.stderr.text:
                    self._logger.warning(
                        f"Error raised by native grep, can't run check {check} on all files"
                    )
                    continue

                matches = []
                if result.returncode == 0:
                    for line in result.stdout.text.splitlines():
                        p, _ = line.split(":", 1)
                        matches.append("local:" + p.replace(path + os.path.sep, ""))

                self._logger.info(f"... got {len(matches)} matches")
                full_check_result[check] = matches

            self._check_result = full_check_result
            return full_check_result

    def _validate_file(self, storage, path, file_type):
        try:
            path_on_disk = self._file_manager.path_on_disk(storage, path)
        except NotImplementedError:
            # storage doesn't support path_on_disk, ignore
            return

        if file_type[-1] != "gcode":
            return

        types = []
        for check, params in CHECKS.items():
            pattern = params["pattern"]
            if self._search_through_file(
                path_on_disk,
                pattern,
                incl_comments=params.get("incl_comments", False),
                regex=params.get("regex", False),
            ):
                types.append(check)

        if types:
            self._notify(storage, path, types)

    def _search_through_file(self, path, pattern, incl_comments=False, regex=False):
        sanitized = self._sanitize_pattern(
            pattern, incl_comments=incl_comments, regex=regex
        )
        compiled = re.compile(pattern)

        try:
            if self._native_grep_available:
                result = sarge.capture_stderr(["grep", "-q", "-E", sanitized, path])
                if not result.stderr.text:
                    return result.returncode == 0

                self._logger.warning(
                    "Error raised by native grep, falling back to python "
                    "implementation: {}".format(result.stderr.text.strip())
                )

            return self._search_through_file_python(
                path, sanitized, compiled, incl_comments=incl_comments
            )

        except Exception:
            self._logger.exception(
                "Something unexpectedly went wrong while trying to "
                "search for {} in {}".format(pattern, path)
            )

        return False

    def _search_through_file_python(self, path, term, compiled, incl_comments=False):
        with open(path, encoding="utf8", errors="replace") as f:
            for line in f:
                if term in line and (incl_comments or compiled.match(line)):
                    return True
        return False

    def _sanitize_pattern(self, pattern, incl_comments=False, regex=False):
        if regex:
            return pattern

        if incl_comments:
            return re.escape(pattern)
        else:
            return r"^[^;]*" + re.escape(pattern)

    def _notify(self, storage, path, types):
        self._logger.warning(f"File check identified issues for {storage}:{path}:")
        for t in types:
            self._logger.warning(
                f"  {t}, see https://faq.octoprint.org/file-check-{t.replace('_', '-')} for details"
            )

        with self._full_check_lock:
            for t in types:
                if t not in self._check_result:
                    self._check_result[t] = []
                if path not in self._check_result[t]:
                    self._check_result[t].append(f"{storage}:{path}")

        self._plugin_manager.send_plugin_message(
            self._identifier,
            {"action": "notify", "storage": storage, "path": path, "types": types},
        )

    def _trigger_check_update(self):
        self._plugin_manager.send_plugin_message(
            self._identifier, dict(action="check_update")
        )


__plugin_name__ = "File Check"
__plugin_pythoncompat__ = ">3.7,<4"
__plugin_disabling_discouraged__ = gettext(
    "Without this plugin OctoPrint will no longer be able to "
    "check if uploaded files contain common problems and inform you "
    "about that fact."
)

__plugin_implementation__ = FileCheckPlugin()
__plugin_hooks__ = {
    "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions,
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
}
