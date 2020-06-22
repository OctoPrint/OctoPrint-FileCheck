/*
 * View model for OctoPrint-FileCheck
 *
 * Author: Gina Häußge
 * License: AGPLv3
 */
$(function() {
    function FileCheckViewModel(parameters) {
        var self = this;

        var issues = {
            travel_speed: gettext("Your sliced file still contains a place holder <code>{travel_speed}</code>. "
                + "This is a common issue when using old start/stop GCODE code snippets in current versions of "
                + "Cura, as the placeholder name switched to <code>{speed_travel}</code> at some point and "
                + "no longer gets replaced in current versions. You need to fix this in your slicer and reslice "
                + "your file, do not print it like it is as it will cause issues!")
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin !== "file_check") {
                return;
            }

            var message = issues[data["type"]];
            if (!message) {
                return;
            }

            var faq = "<a href='https://faq.octoprint.org/file-check-"
                + data["type"].replace("_", "-") + "' target='_blank' rel='noreferrer noopener'>"
                + gettext("Read more...") + "</a>";

            new PNotify({
                title: _.sprintf(gettext('File Check detected issues with %(storage)s:%(path)s!'), data),
                text: "<p>" + message + "</p><p>" + faq + "</p>",
                hide: false
            });
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: FileCheckViewModel
    });
});
