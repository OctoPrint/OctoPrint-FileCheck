__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 The OctoPrint Project - Released under terms of the AGPLv3 License"

import glob
import json
import os
import re
import threading
import time
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

WIZARD_VERSION = 1  # bump on addition of critical checks

CHECKS_VERSION = 1  # bump on any change to the checks
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
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.WizardPlugin,
):
    def __init__(self):
        self._executor = ThreadPoolExecutor()

        self._native_grep_available = False

        self._last_check_mutex = threading.RLock()
        self._full_check_lock = threading.RLock()
        self._check_result = {}

    def initialize(self):
        try:
            sarge.run(["grep", "-q", "--version"])
            self._native_grep_available = True
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
        if (
            event == octoprint.events.Events.FILE_ADDED
            and payload.get("operation", "add") == "add"
        ):
            self._executor.submit(
                self._validate_file, payload["storage"], payload["path"], payload["type"]
            )

        elif event == octoprint.events.Events.FILE_SELECTED:
            file_type = get_file_type(payload["name"])
            self._executor.submit(
                self._validate_file, payload["origin"], payload["path"], file_type
            )

    ##~~ SettingsPlugin API

    def get_settings_defaults(self):
        return {
            "ignored_checks": [],
        }

    ##~~ SimpleApiPlugin API

    def on_api_get(self, request):
        if not octoprint.access.permissions.Permissions.PLUGIN_FILE_CHECK_RUN.can():
            return flask.make_response("Insufficient rights", 403)

        last_check_info = self._load_last_check_info()

        response = {
            "native_grep": self._native_grep_available,
            "last_full_check": {
                "timestamp": last_check_info.get("timestamp"),
                "current": last_check_info.get("version") == CHECKS_VERSION,
            },
        }

        if octoprint.access.permissions.Permissions.FILES_LIST.can():
            # only return the check result if the user has permissions
            # to see a file list, otherwise we might leak data
            response["check_result"] = (
                self._gather_from_local_metadata()
            )  # TODO: caching?

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

    def is_api_protected(self):
        return True

    ##~~ TemplatePlugin API

    def get_template_configs(self):
        templates = [
            {
                "type": "settings",
                "custom_bindings": True,
            }
        ]

        if self._native_grep_available:
            templates.append(
                {
                    "type": "wizard",
                    "template": "file_check_wizard_fullcheck.jinja2",
                    "custom_bindings": True,
                }
            )

        return templates

    ##~~ WizardPlugin API

    def is_wizard_required(self):
        last_check_info = self._load_last_check_info()
        first_run = self._settings.global_get_boolean(["server", "firstRun"])
        return (
            self._native_grep_available
            and last_check_info.get("version") != CHECKS_VERSION
            and not first_run
        )

    def get_wizard_version(self):
        return WIZARD_VERSION

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
        return {
            "file_check": {
                "displayName": "File Check Plugin",
                "displayVersion": self._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "OctoPrint",
                "repo": "OctoPrint-FileCheck",
                "current": self._plugin_version,
                "stable_branch": {
                    "name": "Stable",
                    "branch": "master",
                    "commitish": ["devel", "master"],
                },
                "prerelease_branches": [
                    {
                        "name": "Prerelease",
                        "branch": "devel",
                        "commitish": ["devel", "master"],
                    }
                ],
                # update method: pip
                "pip": "https://github.com/OctoPrint/OctoPrint-FileCheck/archive/{target_version}.zip",
            }
        }

    ##~~ Internal logic & helpers

    def _start_full_check(self):
        with self._full_check_lock:
            job = self._executor.submit(self._check_all_files)
            job.add_done_callback(self._full_check_done)

    def _full_check_done(self, future):
        try:
            future.result()
        except Exception:
            self._logger.exception("Full check failed")
            return
        self._trigger_check_update()

    def _check_all_files(self):
        if not self._native_grep_available:
            return {}

        with self._full_check_lock:
            path = self._settings.global_get_basefolder("uploads")
            self._logger.info(f"Running check on all files in {path} (local storage)")
            ignored_checks = self._settings.get(["ignored_checks"])

            full_check_result = defaultdict(list)
            for check, params in CHECKS.items():
                if check in ignored_checks:
                    continue
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
                        match = p.replace(path + os.path.sep, "")
                        if get_file_type(match)[-1] == "gcode":
                            matches.append(match)

                self._logger.info(f"... got {len(matches)} matches")
                for match in matches:
                    full_check_result[match].append(check)

            for f, checks in full_check_result.items():
                self._save_to_metadata("local", f, checks)
            self._save_last_check_info()

    def _save_last_check_info(self):
        data = {
            "version": CHECKS_VERSION,
            "timestamp": int(time.time()),
        }

        try:
            with self._last_check_mutex:
                with open(
                    os.path.join(self.get_plugin_data_folder(), "last_check_info.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    data = json.dump(data, f)
        except Exception:
            self._logger.exception(
                "Could not save information about last full file check"
            )
            return

    def _load_last_check_info(self):
        path = os.path.join(self.get_plugin_data_folder(), "last_check_info.json")
        if not os.path.isfile(path):
            files = self._file_manager.list_files("local", recursive=False)
            if not len(files.get("local", {})):
                # no files there, mark things as up to date
                self._save_last_check_info()
            else:
                # there are files, we can't take that shortcut
                return {}

        try:
            with self._last_check_mutex:
                with open(
                    path,
                    encoding="utf-8",
                ) as f:
                    data = json.load(f)
                    if (
                        isinstance(data, dict)
                        and "version" in data
                        and "timestamp" in data
                    ):
                        return data
        except Exception:
            self._logger.exception(
                "Could not load information about last full file check"
            )

        return {}

    def _validate_file(self, storage, path, file_type):
        try:
            path_on_disk = self._file_manager.path_on_disk(storage, path)
        except NotImplementedError:
            # storage doesn't support path_on_disk, ignore
            return

        if file_type[-1] != "gcode":
            return

        ignored_checks = self._settings.get(["ignored_checks"])

        types = []
        for check, params in CHECKS.items():
            if check in ignored_checks:
                continue

            pattern = params["pattern"]
            if self._search_through_file(
                path_on_disk,
                pattern,
                incl_comments=params.get("incl_comments", False),
                regex=params.get("regex", False),
            ):
                types.append(check)

        if types:
            self._save_to_metadata(storage, path, types)
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

            return self._search_through_file_python(path, compiled)

        except Exception:
            self._logger.exception(
                "Something unexpectedly went wrong while trying to "
                "search for {} in {}".format(pattern, path)
            )

        return False

    def _search_through_file_python(self, path, compiled):
        with open(path, encoding="utf8", errors="replace") as f:
            for line in f:
                if compiled.search(line):
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

        self._plugin_manager.send_plugin_message(
            self._identifier,
            {"action": "notify", "storage": storage, "path": path, "types": types},
        )

    def _trigger_check_update(self):
        self._plugin_manager.send_plugin_message(
            self._identifier, {"action": "check_update"}
        )

    def _save_to_metadata(self, storage, path, positive_checks):
        metadata = {
            "version": CHECKS_VERSION,
            "checks": positive_checks,
        }
        self._file_manager.set_additional_metadata(
            storage, path, "file_check", metadata, overwrite=True
        )

    def _gather_from_local_metadata(self):
        uploads = self._settings.global_get_basefolder("uploads")

        ignored_checks = self._settings.get(["ignored_checks"])

        result = {}
        for path in glob.glob(
            os.path.join(uploads, "**", ".metadata.json"), recursive=True
        ):
            internal_path = path[len(uploads) + 1 : -len(".metadata.json")]
            from_metadata = self._gather_metadata_from_file(
                path, ignored_checks=ignored_checks
            )
            result.update(
                {f"local:{internal_path}{k}": v for k, v in from_metadata.items()}
            )
        return result

    def _gather_metadata_from_file(self, path, ignored_checks=None):
        with open(path, encoding="utf-8") as f:
            metadata = json.load(f)

        if not isinstance(metadata, dict):
            return {}

        if ignored_checks is None:
            ignored_checks = self._settings.get(["ignored_checks"])

        result = {}
        for key, value in metadata.items():
            if "file_check" in value and isinstance(value["file_check"], dict):
                filtered = list(
                    filter(
                        lambda x: x not in ignored_checks,
                        value["file_check"].get("checks", []),
                    )
                )
                if len(filtered) > 0:
                    result[key] = filtered
        return result


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
