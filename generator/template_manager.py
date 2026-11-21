"""
Template manager for isolated Android WebView builds.
Copies master template into a temporary isolated workspace,
substitutes placeholders, generates package directory structure,
and applies icons without modifying the master template.
"""

import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional


def get_base_dir() -> Path:
    """Returns the base directory for the application, supporting both frozen PyInstaller and script modes."""
    if getattr(sys, "frozen", False):
        # When running under PyInstaller
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_runtime_dir() -> Path:
    """Returns the directory where user files and temporary build workspaces should be placed."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


class TemplateManager:
    """Manages creation, configuration, and cleanup of isolated Android project builds."""

    def __init__(self, master_template_path: Optional[str] = None):
        if master_template_path:
            self.master_template = Path(master_template_path).resolve()
        else:
            # Check candidate locations for bundled template
            candidates = [
                get_base_dir() / "template" / "android_webview",
                get_runtime_dir() / "template" / "android_webview",
                Path(__file__).resolve().parent.parent / "template" / "android_webview",
            ]
            found_template = None
            for cand in candidates:
                if (cand / "build.gradle").exists():
                    found_template = cand.resolve()
                    break

            if found_template:
                self.master_template = found_template
            else:
                self.master_template = candidates[0].resolve()

        if not self.master_template.exists():
            raise FileNotFoundError(f"Master Android template not found at: {self.master_template}")

    def create_isolated_project(
        self,
        app_name: str,
        webview_url: str,
        package_name: str,
        application_id: str,
        workspace_base: Optional[str] = None,
        local_html_path: Optional[str] = None,
    ) -> Path:
        """
        Creates an isolated temporary Android project from the master template
        and configures all placeholders.
        """
        # Determine temporary workspace folder
        if workspace_base:
            workspace_dir = Path(workspace_base).resolve()
        else:
            # Use build_workspace/ in the application runtime root
            workspace_dir = get_runtime_dir() / "build_workspace"

        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create unique project directory
        timestamp = int(time.time() * 1000)
        project_dir = workspace_dir / f"project_{timestamp}"
        project_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Copy entire master template to temporary project
            shutil.copytree(self.master_template, project_dir, dirs_exist_ok=True)

            # If local HTML or ZIP is provided, embed inside app/src/main/assets/
            if local_html_path:
                src_path = Path(local_html_path).resolve()
                if src_path.exists():
                    assets_dir = project_dir / "app" / "src" / "main" / "assets"
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    if src_path.suffix.lower() == ".zip":
                        import zipfile
                        with zipfile.ZipFile(src_path, "r") as z:
                            z.extractall(assets_dir)
                    else:
                        shutil.copy2(src_path, assets_dir / "index.html")
                    webview_url = "file:///android_asset/index.html"

            # 2. Substitute placeholders in configuration files
            self._apply_placeholders(
                project_dir,
                {
                    "%%APP_NAME%%": app_name,
                    "%%WEBVIEW_URL%%": webview_url,
                    "%%PACKAGE_NAME%%": package_name,
                    "%%APPLICATION_ID%%": application_id,
                },
            )

            # 3. Refactor Java package directory structure
            self._refactor_java_package(project_dir, package_name)

            return project_dir
        except Exception as e:
            # Cleanup on failure
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to prepare isolated project: {str(e)}")

    def _apply_placeholders(self, project_dir: Path, replacements: Dict[str, str]):
        """Recursively replaces placeholder tokens in gradle, xml, java, and properties files."""
        text_extensions = {".gradle", ".kts", ".properties", ".xml", ".java", ".kt", ".txt", ".pro", ".json"}

        for root, _, files in os.walk(project_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                if file_path.suffix.lower() in text_extensions or file_name in {"gradlew", "gradlew.bat"}:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        modified = False
                        for placeholder, value in replacements.items():
                            if placeholder in content:
                                content = content.replace(placeholder, value)
                                modified = True
                        if modified:
                            file_path.write_text(content, encoding="utf-8")
                    except Exception as e:
                        # Skip binary or unreadable files
                        pass

    def _refactor_java_package(self, project_dir: Path, new_package_name: str):
        """
        Moves Java source files from template default package to match the new package_name structure.
        """
        java_root = project_dir / "app" / "src" / "main" / "java"
        if not java_root.exists():
            return

        # Target package directory
        package_path_segments = new_package_name.split(".")
        target_dir = java_root
        for segment in package_path_segments:
            target_dir = target_dir / segment

        template_old_dir = java_root / "com" / "evidentix" / "webview"

        # If old dir exists and target dir is different, move Java files cleanly
        if template_old_dir.exists() and template_old_dir != target_dir:
            temp_stage = project_dir / "app" / "src" / "main" / "_java_stage"
            temp_stage.mkdir(parents=True, exist_ok=True)

            for file_name in os.listdir(template_old_dir):
                src_file = template_old_dir / file_name
                if src_file.is_file():
                    shutil.move(str(src_file), str(temp_stage / file_name))

            # Remove old template tree under com
            shutil.rmtree(java_root / "com", ignore_errors=True)

            # Create target package dir and move files in
            target_dir.mkdir(parents=True, exist_ok=True)
            for file_name in os.listdir(temp_stage):
                shutil.move(str(temp_stage / file_name), str(target_dir / file_name))

            shutil.rmtree(temp_stage, ignore_errors=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def cleanup_project(project_dir: Path):
        """Safely removes a temporary project directory after build."""
        try:
            if project_dir and project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
        except Exception:
            pass
