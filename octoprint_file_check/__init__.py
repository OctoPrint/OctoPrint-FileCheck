# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2020 The OctoPrint Project - Released under terms of the AGPLv3 License"

import octoprint.plugin
import octoprint.events

import sarge
import io
import re

from flask_babel import gettext

# noinspection PyCompatibility
from concurrent.futures import ThreadPoolExecutor

class FileCheckPlugin(octoprint.plugin.AssetPlugin,
                      octoprint.plugin.EventHandlerPlugin):
	def __init__(self):
		self._executor = ThreadPoolExecutor()

	##~~ AssetPlugin API

	def get_assets(self):
		return dict(js=("js/file_check.js",))

	##~~ EventHandlerPlugin API

	def on_event(self, event, payload):
		if event == octoprint.events.Events.FILE_ADDED:
			self._executor.submit(self._validate_file, payload["storage"], payload["path"], payload["type"])

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

				# update method: pip
				pip="https://github.com/OctoPrint/OctoPrint-FileCheck/archive/{target_version}.zip"
			)
		)

	##~~ Internal logic & helpers

	def _validate_file(self, storage, path, file_type):
		try:
			path_on_disk = self._file_manager.path_on_disk(storage, path)
		except NotImplementedError:
			# storage doesn't support path_on_disk, ignore
			return

		if file_type[-1] == "gcode":
			if self._search_through_file(path_on_disk, "{travel_speed}"):
				self._notify("travel_speed", storage, path)

	def _search_through_file(self, path, term, incl_comments=False):
		if incl_comments:
			pattern = re.escape(term)
		else:
			pattern = r"^[^;]*" + re.escape(term)
		compiled = re.compile(pattern)

		try:
			# try native grep
			result = sarge.run(["grep", "-q", pattern, path])
			return result.returncode == 0
		except ValueError as exc:
			if 'Command not found' in str(exc):
				try:
					# try python only approach
					with io.open(path, mode="r", encoding="utf8", errors="replace") as f:
						for line in f:
							if term in line and (incl_comments or compiled.match(line)):
								return True
					return False
				except:
					self._logger.exception("Something unexpectedly went wrong while trying to "
					                       "search for {} in {} via native python".format(term, path))
			else:
				self._logger.exception("Something unexpectedly went wrong while trying to "
				                       "search for {} in {} via grep".format(term, path))

		return False

	def _notify(self, notification_type, storage, path):
		self._logger.warning("File check identified an issue: {} for {}:{}, see "
		                     "https://faq.octoprint.org/file-check-{} for details".format(notification_type,
		                                                                                  storage,
		                                                                                  path,
		                                                                                  notification_type.replace("_", "-")))
		self._plugin_manager.send_plugin_message(self._identifier, dict(type=notification_type,
		                                                                storage=storage,
		                                                                path=path))


__plugin_name__ = "File Check"
__plugin_pythoncompat__ = ">2.7,<4"
__plugin_disabling_discouraged__ = gettext("Without this plugin OctoPrint will no longer be able to "
                                           "check if uploaded files contain common problems and inform you "
                                           "about that fact.")

__plugin_implementation__ = FileCheckPlugin()
__plugin_hooks__ = {
	"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}
