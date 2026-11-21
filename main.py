"""
Web2Apk v1.0 — By Mohsin Khawaja
"Get rid of paid web to apk tools"
100% Pure Python Web Console & CLI for compiling real Android APKs.
"""

import os
import sys
import time
import argparse
import threading
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from generator.apk_generator import ApkGenerator, BuildStatus
from generator.build_manager import EnvironmentDetector
from generator.package_generator import PackageGenerator
from generator.template_manager import get_runtime_dir


# Global build state for the Web Console
class BuildStateManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock if hasattr(self, 'lock') else threading.Lock():
            self.running = False
            self.status = "Idle"
            self.stage = "IDLE"
            self.progress = 0
            self.logs = []
            self.success = None
            self.apk_path = None
            self.apk_name = None
            self.apk_size_mb = 0.0
            self.package_name = ""
            self.error = None
            self.cancelled = False

    def update_status(self, status: BuildStatus, detail: str):
        with self.lock:
            self.status = detail or status.value
            self.stage = status.name
            progress_map = {
                BuildStatus.VALIDATING: 10,
                BuildStatus.PREPARING: 25,
                BuildStatus.PROCESSING_ICON: 40,
                BuildStatus.CONFIGURING: 55,
                BuildStatus.RUNNING_GRADLE: 70,
                BuildStatus.BUILDING_APK: 85,
                BuildStatus.SUCCESS: 100,
                BuildStatus.FAILED: 0,
            }
            if status in progress_map:
                self.progress = progress_map[status]

    def add_log(self, line: str):
        with self.lock:
            self.logs.append(line)

    def complete(self, success: bool, apk_path: Optional[str], error: Optional[str], package_name: str = ""):
        with self.lock:
            self.running = False
            self.success = success
            self.error = error
            self.package_name = package_name
            if success and apk_path:
                p = Path(apk_path)
                self.apk_path = str(p)
                self.apk_name = p.name
                if p.exists():
                    self.apk_size_mb = round(p.stat().st_size / (1024 * 1024), 2)
                self.progress = 100
                self.status = "Build completed successfully!"
                self.stage = "SUCCESS"
            else:
                self.stage = "FAILED"
                self.status = error or "Build failed."

    def get_snapshot(self, log_offset: int = 0) -> Dict[str, Any]:
        with self.lock:
            new_logs = self.logs[log_offset:]
            return {
                "running": self.running,
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "success": self.success,
                "apk_path": self.apk_path,
                "apk_name": self.apk_name,
                "apk_size_mb": self.apk_size_mb,
                "package_name": self.package_name,
                "error": self.error,
                "new_logs": new_logs,
                "total_logs": len(self.logs),
            }


build_state = BuildStateManager()


def run_web_server(host: str = "127.0.0.1", port: int = 5000, auto_open: bool = True):
    """Starts the Flask-powered local Web Console and opens it in the browser."""
    from flask import Flask, render_template, request, jsonify, send_from_directory

    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

    # Output directory for generated APKs
    output_dir = BASE_DIR / "Generated_APKs"
    output_dir.mkdir(parents=True, exist_ok=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/env")
    def api_env():
        """Returns detected system environment status (Java, SDK, Build Tools, Gradle)."""
        diagnostics = EnvironmentDetector.detect_all()
        return jsonify(diagnostics)

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        """Accepts app parameters and initiates APK generation in a background thread."""
        if build_state.running:
            return jsonify({"error": "A build is currently in progress."}), 400

        app_name = request.form.get("app_name", "").strip()
        source_type = request.form.get("source_type", "url").strip()
        webview_url = request.form.get("webview_url", "").strip()
        custom_package_id = request.form.get("package_id", "").strip() or None

        if not app_name:
            return jsonify({"error": "Application Name is required."}), 400

        local_html_path = None
        if source_type == "file":
            if "local_html" not in request.files or not request.files["local_html"].filename:
                return jsonify({"error": "Please select a local HTML file or ZIP package."}), 400
            html_file = request.files["local_html"]
            temp_html_dir = BASE_DIR / "temp_html"
            temp_html_dir.mkdir(parents=True, exist_ok=True)
            ext = Path(html_file.filename).suffix or ".html"
            local_html_path = str(temp_html_dir / f"app_source{ext}")
            html_file.save(local_html_path)
        else:
            if not webview_url:
                return jsonify({"error": "Website URL is required in URL mode."}), 400

        # Handle optional icon upload
        icon_path = None
        if "icon" in request.files:
            icon_file = request.files["icon"]
            if icon_file.filename:
                temp_icon_dir = BASE_DIR / "temp_icon"
                temp_icon_dir.mkdir(parents=True, exist_ok=True)
                ext = Path(icon_file.filename).suffix or ".png"
                icon_path = str(temp_icon_dir / f"app_icon{ext}")
                icon_file.save(icon_path)

        # Reset build state and start thread
        build_state.reset()
        build_state.running = True

        def build_worker():
            package_name = custom_package_id if custom_package_id else PackageGenerator.generate_package_name(app_name)
            try:
                generator = ApkGenerator(output_dir=str(output_dir))

                def status_cb(status: BuildStatus, detail: str):
                    build_state.update_status(status, detail)

                def log_cb(line: str):
                    build_state.add_log(line)

                def cancel_check() -> bool:
                    return build_state.cancelled

                success, apk_path, error_msg = generator.generate(
                    app_name=app_name,
                    webview_url=webview_url,
                    icon_path=icon_path,
                    custom_output_dir=str(output_dir),
                    local_html_path=local_html_path,
                    custom_package_id=custom_package_id,
                    status_callback=status_cb,
                    log_callback=log_cb,
                    cancel_check=cancel_check,
                )

                build_state.complete(success, apk_path, error_msg, package_name)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                build_state.add_log(f"\n[CRITICAL ERROR] Internal build failure:\n{tb}")
                build_state.complete(False, None, f"Internal build error: {str(e)}", package_name)

        thread = threading.Thread(target=build_worker, daemon=True)
        thread.start()

        return jsonify({"status": "started", "app_name": app_name, "source_type": source_type})

    @app.route("/api/status")
    def api_status():
        """Returns real-time build progress and incremental log lines."""
        offset = request.args.get("log_offset", 0, type=int)
        return jsonify(build_state.get_snapshot(log_offset=offset))

    @app.route("/api/cancel", methods=["POST"])
    def api_cancel():
        """Cancels an ongoing build."""
        build_state.cancelled = True
        return jsonify({"status": "cancelled"})

    @app.route("/api/download/<path:filename>")
    def api_download(filename):
        """Downloads a compiled APK file from the output directory."""
        return send_from_directory(str(output_dir), filename, as_attachment=True)

    @app.route("/api/open-folder", methods=["POST"])
    def api_open_folder():
        """Opens the Generated_APKs folder in Windows Explorer / OS file manager."""
        try:
            if sys.platform == "win32":
                os.startfile(str(output_dir))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(output_dir)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(output_dir)])
            return jsonify({"status": "opened"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    url = f"http://{host}:{port}"
    print("=" * 65)
    print("  WEB2APK v1.0 — BY MOHSIN KHAWAJA")
    print("  \"Get rid of paid web to apk tools\"")
    print("=" * 65)
    print(f"  Web Console:   {url}")
    print(f"  Output Folder: {output_dir}")
    print("  Instagram:     https://www.instagram.com/csib.mohsin/")
    print("  Press Ctrl+C to terminate the local server.")
    print("=" * 65)

    if auto_open:
        def open_browser():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(host=host, port=port, debug=False, use_reloader=False)


def run_cli(args):
    """Executes APK generation in headless command-line mode."""
    print("=" * 65)
    print("EVIDENTIX URL TO APK GENERATOR [CLI MODE]")
    print("=" * 65)

    env = EnvironmentDetector.detect_all()
    print(f"Java Status:       {env['java']['message']}")
    print(f"Android SDK:       {env['sdk']['message']}")
    print(f"Build Tools:       {env['build_tools']['message']}")
    print(f"Gradle:            {env['gradle']['message']}")
    print("-" * 65)

    if not env["ready"]:
        print("[ERROR] Required build dependencies are missing. Aborting build.")
        sys.exit(1)

    out_dir = args.out or str(BASE_DIR / "Generated_APKs")
    generator = ApkGenerator(output_dir=out_dir)

    def status_cb(status: BuildStatus, detail: str):
        print(f"[{status.value.upper()}] {detail}")

    def log_cb(line: str):
        print(line)

    success, apk_path, error_msg = generator.generate(
        app_name=args.name,
        webview_url=args.url,
        icon_path=args.icon,
        custom_output_dir=out_dir,
        status_callback=status_cb,
        log_callback=log_cb,
    )

    if success:
        print("\n" + "=" * 65)
        print("APK GENERATED SUCCESSFULLY!")
        print(f"Output File: {apk_path}")
        print("=" * 65)
        sys.exit(0)
    else:
        print("\n" + "=" * 65)
        print(f"[ERROR] Build failed: {error_msg}")
        print("=" * 65)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Evidentix URL to APK Generator — Local Web Console & CLI")
    parser.add_argument("--cli", action="store_true", help="Run in headless CLI mode instead of Web UI")
    parser.add_argument("--name", type=str, help="Application Name (CLI mode)")
    parser.add_argument("--url", type=str, help="Website / Web App URL (CLI mode)")
    parser.add_argument("--icon", type=str, help="Path to custom launcher icon (CLI mode)")
    parser.add_argument("--out", type=str, help="Custom output directory for generated APK")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web server host (Default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (Default: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser on startup")

    args = parser.parse_args()

    if args.cli:
        if not args.name or not args.url:
            print("[ERROR] Both --name and --url arguments are required in CLI mode.")
            print('Example: python main.py --cli --name "My App" --url "https://example.com"')
            sys.exit(1)
        run_cli(args)
    else:
        run_web_server(host=args.host, port=args.port, auto_open=not args.no_browser)


if __name__ == "__main__":
    main()
