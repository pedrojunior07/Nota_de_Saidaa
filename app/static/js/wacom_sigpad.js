/* Adaptador da signature pad Wacom STU via SigCaptX.
 *
 * Liga-se ao serviço local "STU-SigCaptX" (https://localhost:9000 por
 * omissão — é a porta que a própria Wacom usa por defeito no instalador),
 * instala a licença e expõe uma captura simples que devolve a assinatura
 * como data-URL PNG — o mesmo formato que `canvas.toDataURL()`.
 *
 * Depende de: vendor/sigcaptx/wgssSigCaptX.js (define window.WacomGSS_SignatureSDK).
 *
 * API — window.WacomSigPad:
 *   configure({ port, licence })   guarda a configuração vinda do template
 *   init(force?) -> Promise<estado> "ready" | "no-service" | "no-licence" | "error"
 *   isReady() -> bool
 *   getState() -> estado atual
 *   onState(fn)                     observador de mudanças de estado
 *   capture({ who, why }) -> Promise<dataURL PNG>
 *        rejeita com "cancel" | "pad-error" | "not-licensed" | "render-error" | "error"
 */
(function () {
    "use strict";

    var OK = 0;
    var cfg = { port: 9000, licence: "" };
    var sdk = null;
    var sigCtl = null;
    var dynCapt = null;
    var state = "idle";
    var initPromise = null;
    var observers = [];

    function setState(novo) {
        state = novo;
        observers.forEach(function (fn) {
            try { fn(novo); } catch (_e) { /* observador com erro não trava os outros */ }
        });
    }

    function configure(opts) {
        if (!opts) return;
        if (opts.port) {
            var p = parseInt(opts.port, 10);
            if (!Number.isNaN(p)) cfg.port = p;
        }
        if (typeof opts.licence === "string") cfg.licence = opts.licence.trim();
    }

    function onState(fn) {
        if (typeof fn === "function") observers.push(fn);
    }

    function isReady() { return state === "ready"; }
    function getState() { return state; }

    function temSDK() {
        return typeof window.WacomGSS_SignatureSDK === "function";
    }

    function init(force) {
        if (initPromise && !force) return initPromise;

        initPromise = new Promise(function (resolve) {
            if (!temSDK()) { setState("error"); return resolve("error"); }

            setState("connecting");
            sigCtl = null;
            dynCapt = null;

            var terminado = false;
            function done(estado) {
                if (terminado) return;
                terminado = true;
                setState(estado);
                resolve(estado);
            }

            try {
                sdk = new window.WacomGSS_SignatureSDK(function onDetectRunning() {
                    if (sdk && sdk.running) arrancarComponentes(done);
                    else done("no-service");
                }, cfg.port);
            } catch (_e) {
                return done("error");
            }

            // O serviço pode demorar alguns segundos a responder (ou não existir).
            setTimeout(function () {
                if (terminado) return;
                if (sdk && sdk.running) arrancarComponentes(done);
                else done("no-service");
            }, 6000);
        });

        return initPromise;
    }

    function arrancarComponentes(done) {
        try {
            sigCtl = new sdk.SigCtl(function (_ctl, status) {
                if (status !== OK) return done("error");
                sigCtl.PutLicence(cfg.licence || "", function () {
                    dynCapt = new sdk.DynamicCapture(function (_dc, s) {
                        if (s !== OK) return done("error");
                        if (!cfg.licence) return done("no-licence");
                        dynCapt.PutLicence(cfg.licence, function () { done("ready"); });
                    });
                });
            });
        } catch (_e) {
            done("error");
        }
    }

    function render(sigObj, resolve, reject) {
        var F = sdk.RBFlags;
        var flags = F.RenderOutputBase64 | F.RenderColor32BPP | F.RenderColorAntiAlias;
        sigObj.RenderBitmap(
            "png", 600, 240, 0.7, 0x000000, 0x00FFFFFF, flags, 4, 4,
            function (_so, dados, status) {
                if (status === OK && typeof dados === "string" && dados.length) {
                    resolve("data:image/png;base64," + dados);
                } else {
                    reject("render-error");
                }
            }
        );
    }

    function capture(opts) {
        opts = opts || {};
        var who = opts.who || "";
        var why = opts.why || "Assinatura de documento";

        return new Promise(function (resolve, reject) {
            if (state !== "ready" || !dynCapt || !sigCtl) return reject("error");
            var reiniciou = false;

            function correr() {
                dynCapt.Capture(sigCtl, who, why, null, null, function (_dc, sigObj, status) {
                    var R = sdk.DynamicCaptureResult;
                    if (status === R.DynCaptOK) return render(sigObj, resolve, reject);
                    if (status === R.DynCaptCancel || status === R.DynCaptAbort) return reject("cancel");
                    if (status === R.DynCaptNotLicensed) return reject("not-licensed");
                    if (status === R.DynCaptPadError) return reject("pad-error");
                    if (status === sdk.ResponseStatus.INVALID_SESSION && !reiniciou) {
                        reiniciou = true;
                        init(true).then(function (estado) {
                            if (estado === "ready") correr();
                            else reject("error");
                        });
                        return;
                    }
                    reject("error");
                });
            }

            correr();
        });
    }

    window.WacomSigPad = {
        configure: configure,
        init: init,
        capture: capture,
        isReady: isReady,
        getState: getState,
        onState: onState,
    };
})();
