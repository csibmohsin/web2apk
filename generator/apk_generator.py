"""
High-level orchestrator for the Evidentix URL to APK Generator.
Coordinates validation, temporary project isolation, icon processing,
configuration substitution, Gradle execution, and artifact delivery.
"""

from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Tuple

from .package_generator import PackageGenerator
from .icon_processor import IconProcessor
from .template_manager import TemplateManager, get_runtime_dir
from .build_manager import BuildManager, EnvironmentDetector


class BuildStatus(Enum):
    IDLE = "Idle"
    VALIDATING = "Validating inputs..."
    PREPARING = "Preparing project..."
    PROCESSING_ICON = "Processing icon..."
    CONFIGURING = "Configuring WebView..."
    RUNNING_GRADLE = "Running Gradle..."
    BUILDING_APK = "Building APK..."
    SUCCESS = "APK generated successfully"
    FAILED = "Build failed"


class ApkGenerator:
    """End-to-end pipeline coordinator for generating an Android WebView APK."""

    def __init__(
        self,
        template_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        self.template_manager = TemplateManager(template_dir)
        self.output_dir = output_dir or str(get_runtime_dir() / "Generated_APKs")
        self.build_manager = BuildManager(self.output_dir)

    def generate(
        self,
        app_name: str,
        webview_url: str = "",
        icon_path: Optional[str] = None,
        custom_output_dir: Optional[str] = None,
        local_html_path: Optional[str] = None,
        custom_package_id: Optional[str] = None,
        status_callback: Optional[Callable[[BuildStatus, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Executes the full pipeline:
        1. Validate inputs (either website URL or local HTML package)
        2. Create isolated temporary build directory from template
        3. Configure package name, app name, and WebView URL or local assets
        4. Process user icon into density mipmaps and adaptive drawables
        5. Run Gradle build
        6. Copy output APK to target directory
        7. Teardown temporary project
        """
        def update_status(status: BuildStatus, detail: str = ""):
            if status_callback:
                status_callback(status, detail)
            if log_callback:
                log_callback(f"\n>>> [{status.value.upper()}] {detail}")

        # 1. Validation
        update_status(BuildStatus.VALIDATING, "Checking application parameters...")
        is_name_valid, name_err = PackageGenerator.validate_app_name(app_name)
        if not is_name_valid:
            update_status(BuildStatus.FAILED, name_err)
            return False, None, name_err

        # Custom package name or auto-derived
        if custom_package_id and custom_package_id.strip():
            is_pkg_valid, pkg_err = PackageGenerator.validate_package_name(custom_package_id.strip())
            if not is_pkg_valid:
                update_status(BuildStatus.FAILED, pkg_err)
                return False, None, pkg_err
            package_name = custom_package_id.strip()
        else:
            package_name = PackageGenerator.generate_package_name(app_name)
        application_id = package_name

        if local_html_path:
            p = Path(local_html_path)
            if not p.exists():
                err = f"Local HTML file not found: {local_html_path}"
                update_status(BuildStatus.FAILED, err)
                return False, None, err
            webview_url = "file:///android_asset/index.html"
        else:
            is_url_valid, url_err = PackageGenerator.validate_url(webview_url)
            if not is_url_valid:
                update_status(BuildStatus.FAILED, url_err)
                return False, None, url_err

        if log_callback:
            log_callback(f"Target App Name: {app_name}")
            if local_html_path:
                log_callback(f"Source: Embedded Local HTML ({Path(local_html_path).name})")
                log_callback(f"Target Web URL: {webview_url}")
            else:
                log_callback(f"Target Web URL: {webview_url}")
            log_callback(f"Configured Package ID: {package_name}")

        # 2. Preparing project in isolated workspace
        update_status(BuildStatus.PREPARING, "Creating isolated project from master template...")
        project_dir: Optional[Path] = None

        try:
            project_dir = self.template_manager.create_isolated_project(
                app_name=app_name,
                webview_url=webview_url,
                package_name=package_name,
                application_id=application_id,
                local_html_path=local_html_path,
            )

            # 3. Processing icon
            update_status(BuildStatus.PROCESSING_ICON, "Generating density mipmaps and adaptive assets...")
            res_dir = project_dir / "app" / "src" / "main" / "res"

            if icon_path and Path(icon_path).exists():
                IconProcessor.process_icon(icon_path, str(res_dir))
                if log_callback:
                    log_callback(f"Processed custom icon from: {icon_path}")
            else:
                default_icon_temp = project_dir / "default_icon.png"
                created_icon = IconProcessor.generate_default_icon(str(default_icon_temp), app_name)
                if created_icon and Path(created_icon).exists():
                    IconProcessor.process_icon(created_icon, str(res_dir))
                    if log_callback:
                        log_callback("Generated and applied branded Evidentix application icon.")
                else:
                    if log_callback:
                        log_callback("Using template standard launcher icon assets.")

            # 4. Configuring WebView
            update_status(BuildStatus.CONFIGURING, "Finalizing manifest and webview settings...")

            # 5. Build execution with Gradle
            update_status(BuildStatus.RUNNING_GRADLE, "Executing Gradle build...")
            if custom_output_dir:
                self.build_manager.output_dir = Path(custom_output_dir).resolve()
                self.build_manager.output_dir.mkdir(parents=True, exist_ok=True)

            update_status(BuildStatus.BUILDING_APK, "Assembling installable APK artifact...")
            success, apk_path, error_msg = self.build_manager.build_apk(
                project_dir=project_dir,
                app_name=app_name,
                log_callback=log_callback,
                cancel_check=cancel_check,
            )

            if success and apk_path:
                update_status(BuildStatus.SUCCESS, f"Saved to: {apk_path}")
                return True, apk_path, ""
            else:
                update_status(BuildStatus.FAILED, error_msg or "Build failed.")
                return False, None, error_msg

        except Exception as e:
            err = f"Generator exception: {str(e)}"
            update_status(BuildStatus.FAILED, err)
            return False, None, err

        finally:
            # 6. Isolation cleanup: Always remove the temporary project directory
            if project_dir and project_dir.exists():
                if log_callback:
                    log_callback(f"\n[CLEANUP] Removing temporary workspace: {project_dir}")
                TemplateManager.cleanup_project(project_dir)
