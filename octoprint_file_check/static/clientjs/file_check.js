(function (global, factory) {
    if (typeof define === "function" && define.amd) {
        define(["OctoPrintClient"], factory);
    } else {
        factory(global.OctoPrintClient);
    }
})(this, function (OctoPrintClient) {
    var OctoPrintFileCheckClient = function (base) {
        this.base = base;
    };

    OctoPrintFileCheckClient.prototype.get = function (opts) {
        return this.base.simpleApiGet("file_check", opts);
    };

    OctoPrintFileCheckClient.prototype.checkAll = function (opts) {
        return this.base.simpleApiCommand("file_check", "check_all", opts);
    };

    OctoPrintClient.registerPluginComponent("file_check", OctoPrintFileCheckClient);
    return OctoPrintFileCheckClient;
});
