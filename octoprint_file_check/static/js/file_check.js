$(function () {
    function FileCheckViewModel(parameters) {
        const self = this;

        self.loginState = parameters[0];
        self.access = parameters[1];
        self.printerState = parameters[2];
        self.filesViewModel = parameters[3];

        self.fullCheckAvailable = ko.observable(false);
        self.checkResult = ko.observable();
        self.checkRunning = ko.observable(false);

        self.issueNotification = undefined;

        const ISSUES = {
            travel_speed: {
                message: gettext(
                    "Your file still contains a place holder <code>{travel_speed}</code>. " +
                        "This is a common issue when using old start/stop GCODE code snippets in current versions of " +
                        "Cura, as the placeholder name switched to <code>{speed_travel}</code> at some point and " +
                        "no longer gets replaced in current versions. You need to fix this in your slicer and reslice " +
                        "your file, do not print it like it is as it will cause issues!"
                )
            },
            leaked_api_key: {
                message: gettext(
                    "Your file contains an API key that is not supposed to be there. " +
                        "This is caused by a bug in your slicer, and known to happen with PrusaSlicer (<1.4.0), " +
                        "BambuStudio (<=1.8.4) and OrcaSlicer (<=1.9.0). " +
                        "Do not share this file with anyone, update your slicer to a patched version immediately, " +
                        "and reslice your file. Also consider changing your API key in OctoPrint, as it might have been leaked by your slicer " +
                        "to third parties through any GCODE files shared previously."
                ),
                severity: "error"
            }
        };

        self.requestData = function () {
            if (!self.loginState.hasPermission(self.access.permissions.FILES_DOWNLOAD))
                return $.Deferred().reject();
            return OctoPrint.plugins.file_check.get().done(self.fromResponse);
        };

        self.fromResponse = function (response) {
            self.fullCheckAvailable(response.native_grep);

            if (response.check_result) {
                const result = {};
                for (const [key, value] of Object.entries(response.check_result)) {
                    for (const filename of value) {
                        result[filename] = result[filename] || [];
                        result[filename].push(key);
                    }
                }
                self.checkResult(result);
            }
        };

        self.checkAll = function () {
            if (!self.loginState.hasPermission(self.access.permissions.FILES_DOWNLOAD))
                return;

            showConfirmationDialog({
                title: gettext("Run File Check on all files?"),
                message: gettext(
                    "This will perform a check of all of your uploaded files for known issues. " +
                        "Depending on the amount of files this could take several minutes. " +
                        "It should not be done while a print is running."
                ),
                onproceed: () => {
                    self.checkRunning(true);
                    OctoPrint.plugins.file_check.checkAll();
                }
            });
        };

        self.hasCheckResult = function (storage, file) {
            if (!storage) return null;

            if (_.isPlainObject(storage)) {
                file = storage.path;
                storage = storage.origin;
            } else if (!file) {
                file = storage;
                storage = "local";
            }

            const key = `${storage}:${file}`;
            return (
                self.checkResult() &&
                self.checkResult()[key] &&
                self.loginState.hasPermission(self.access.permissions.FILES_DOWNLOAD)
            );
        };

        self.showCheckResult = function (storage, file) {
            if (!self.loginState.hasPermission(self.access.permissions.FILES_DOWNLOAD))
                return;

            if (_.isPlainObject(storage)) {
                file = storage.path;
                storage = storage.origin;
            } else if (!file) {
                file = storage;
                storage = "local";
            }

            const key = `${storage}:${file}`;
            const data = self.checkResult()[key];
            if (!data) return;

            const getMessage = (issue) => {
                return $("<p/>", {html: ISSUES[issue].message});
            };

            const getReadMore = (issue) => {
                return $("<p/>").append(
                    $("<a/>", {
                        href:
                            "https://faq.octoprint.org/file-check-" +
                            issue.replace("_", "-"),
                        target: "_blank",
                        rel: "noreferrer noopener",
                        text: gettext("Read more...")
                    })
                );
            };

            const title = gettext("File Check detected the following issues:");
            let message;

            if (data.length === 1) {
                const issue = data[0];
                message = getMessage(issue).after(getReadMore(issue));
            } else {
                message = $("<ul/>").append(
                    data.map((issue) =>
                        $("<li/>").append(getMessage(issue)).append(getReadMore(issue))
                    )
                );
            }

            showMessageDialog({
                title: title,
                message: message
            });
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "file_check") return;

            if (!self.loginState.hasPermission(self.access.permissions.FILES_DOWNLOAD))
                return;

            switch (data["action"]) {
                case "notify": {
                    self._handleNotification(data);
                    break;
                }
                case "check_update": {
                    self._handleCheckUpdate(data);
                    break;
                }
            }
        };

        self._handleNotification = function (data) {
            let severity = "warning";

            const result = [];
            for (const t of data["types"]) {
                if (!ISSUES[t]) continue;

                const spec = ISSUES[t];
                const message = spec["message"];

                if (spec["severity"] === "error") {
                    severity = "error";
                }

                const faq =
                    "<a href='https://faq.octoprint.org/file-check-" +
                    t.replace("_", "-") +
                    "' target='_blank' rel='noreferrer noopener'>" +
                    gettext("Read more...") +
                    "</a>";

                result.push("<p>" + message + "</p><p>" + faq + "</p>");
            }

            if (result.length === 0) {
                return;
            }

            let text;
            if (result.length === 1) {
                text = result[0];
            } else {
                text = "<ul>" + result.map((r) => `<li>${r}</li>`).join("") + "</ul>";
            }

            self.issueNotification && self.issueNotification.remove();
            self.issueNotification = new PNotify({
                title: _.sprintf(
                    gettext("File Check detected issues with %(path)s!"),
                    data
                ),
                text: text,
                hide: false,
                type: severity
            });

            self._handleCheckUpdate();
        };

        self._handleCheckUpdate = function (data) {
            self.requestData().done(() => {
                self.checkRunning(false);
            });
        };

        self.onStartup = function () {
            self.filesViewModel.fileCheckViewModel = self;
            self.printerState.fileCheckViewModel = self;

            // files list injection

            $("#files_wrapper .accordion-heading").append(
                $("<div/>", {
                    class: "filecheck-trigger accordion-heading-button btn-group",
                    attr: {
                        "data-bind":
                            "visible: $root.fileCheckViewModel.fullCheckAvailable() && $root.loginState.hasPermission($root.access.permissions.FILES_DOWNLOAD)"
                    }
                }).append(
                    $("<a/>", {
                        href: "javascript:void(0);",
                        attr: {
                            "data-bind":
                                "click: function () { if (!$root.printerState.isPrinting()) { $root.fileCheckViewModel.checkAll() } },",
                            "title": gettext("Run File Check on all files"),
                            "aria-label": gettext("Run File Check on all files")
                        }
                    }).append(
                        $("<i/>", {
                            class: "fas",
                            attr: {
                                "data-bind":
                                    "css: {'fa-spinner fa-spin': $root.fileCheckViewModel.checkRunning, 'fa-stamp': !$root.fileCheckViewModel.checkRunning(), 'muted': $root.fileCheckViewModel.checkRunning() || $root.printerState.isPrinting()}"
                            }
                        })
                    )
                )
            );

            const regex = /<div class="uploaded">/;
            const template =
                "<div class='filecheck_result' data-bind='visible: $root.fileCheckViewModel.hasCheckResult($data) && $root.loginState.hasPermission($root.access.permissions.FILES_DOWNLOAD)'><small>" +
                "<a href='javascript:void(0)' class='text-error' style='text-decoration: underline' data-bind='click: function() { $root.fileCheckViewModel.showCheckResult($data) }'>" +
                "<i class='fas fa-exclamation-circle'></i> " +
                gettext("File Check detected issues with this file!") +
                "</a></small></div>";
            $("#files_template_machinecode").text((idx, text) => {
                const position = text.search(regex);
                return text.substring(0, position) + template + text.substring(position);
            });

            // printer state injection

            $("#state .accordion-inner hr:nth-of-type(2)").before(
                $("<small/>", {
                    attr: {
                        "data-bind":
                            "visible: $root.fileCheckViewModel.hasCheckResult($root.filepath()) && $root.loginState.hasPermission($root.access.permissions.FILES_DOWNLOAD)"
                    }
                })
                    .append(
                        $("<a/>", {
                            href: "javascript:void(0);",
                            class: "text-error",
                            style: "text-decoration: underline",
                            attr: {
                                "data-bind":
                                    "click: function() { $root.fileCheckViewModel.showCheckResult($root.filepath()) }"
                            }
                        })
                            .append(
                                $("<i/>", {
                                    class: "fas fa-exclamation-circle"
                                })
                            )
                            .append(
                                " " +
                                    gettext("File Check detected issues with this file!")
                            )
                    )
                    .after($("<br/>"))
            );
        };

        self.onUserLoggedIn = self.onUserLoggedOut = function () {
            self.requestData();
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: FileCheckViewModel,
        dependencies: [
            "loginStateViewModel",
            "accessViewModel",
            "printerStateViewModel",
            "filesViewModel"
        ]
    });
});
