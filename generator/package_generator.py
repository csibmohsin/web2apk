"""
Package and naming sanitization module for Android APK generation.
Ensures valid package names, application IDs, and file names.
"""

import re
import hashlib
from typing import Set

JAVA_RESERVED_KEYWORDS: Set[str] = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while", "true", "false", "null"
}


class PackageGenerator:
    """Handles generation and validation of Android package names and safe filenames."""

    DEFAULT_BASE_PACKAGE = "com.evidentix.webapp"

    @classmethod
    def sanitize_package_segment(cls, segment: str) -> str:
        """
        Sanitizes a single package identifier segment:
        - Converts to lowercase
        - Strips any non-alphanumeric or underscore characters
        - Ensures it starts with a valid ASCII letter
        - Ensures it is not a Java reserved keyword
        """
        if not segment:
            return "app"

        # Replace hyphens and spaces with underscores
        cleaned = re.sub(r"[\s\-]+", "_", segment.lower())
        # Remove any non-alphanumeric and non-underscore characters
        cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)

        # Must start with a letter (a-z)
        if not cleaned or not cleaned[0].isalpha():
            cleaned = f"app_{cleaned}"

        # Truncate to reasonable length (max 30 chars per segment)
        cleaned = cleaned[:30].strip("_")
        if not cleaned:
            cleaned = "app"

        # Avoid Java reserved keywords
        if cleaned in JAVA_RESERVED_KEYWORDS:
            cleaned = f"app_{cleaned}"

        return cleaned

    @classmethod
    def generate_package_name(cls, app_name: str, base_package: str = DEFAULT_BASE_PACKAGE) -> str:
        """
        Generates a valid Android package name from the app name.
        Example: 'Evidentix Portal' -> 'com.evidentix.webapp.evidentixportal'
        Example: 'CSIB Portal' -> 'com.evidentix.webapp.csibportal'
        """
        # Create a single slug segment for the app
        cleaned_words = [w for w in re.split(r"[\s\-_]+", app_name.strip()) if w]
        if not cleaned_words:
            slug = "app"
        else:
            slug = "".join(cleaned_words)

        sanitized_slug = cls.sanitize_package_segment(slug)

        # Append short hash if the sanitized slug is too generic or short (< 3 chars)
        if len(sanitized_slug) < 3:
            h = hashlib.md5(app_name.encode("utf-8")).hexdigest()[:4]
            sanitized_slug = f"{sanitized_slug}_{h}"

        return f"{base_package}.{sanitized_slug}"

    @classmethod
    def sanitize_filename(cls, name: str, extension: str = ".apk") -> str:
        """
        Generates a safe Windows/Android filename for the APK.
        Example: 'Evidentix Portal' -> 'Evidentix_Portal.apk'
        Example: 'CSIB Portal!' -> 'CSIB_Portal.apk'
        """
        if not name or not name.strip():
            base = "App"
        else:
            # Replace spaces and hyphens with underscores
            base = re.sub(r"[\s\-]+", "_", name.strip())
            # Remove any invalid filename characters (\ / : * ? " < > |)
            base = re.sub(r'[\\/*?:"<>|]', "", base)
            # Remove any consecutive underscores
            base = re.sub(r"_+", "_", base)
            base = base.strip("._")

        if not base:
            base = "App"

        # Truncate base name to 60 characters for safety
        base = base[:60]
        ext = extension if extension.startswith(".") else f".{extension}"
        return f"{base}{ext}"

    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, str]:
        """
        Validates the user-entered URL.
        Must be a non-empty string starting with http:// or https:// with a valid domain.
        """
        if not url or not url.strip():
            return False, "URL cannot be empty."

        url = url.strip()

        # Check scheme
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "URL must begin with http:// or https://"

        # Comprehensive URL regex
        pattern = re.compile(
            r"^(https?://)"  # http:// or https://
            r"(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}|localhost|(\d{1,3}\.){3}\d{1,3})"  # domain or localhost or IP
            r"(:\d{1,5})?"  # optional port
            r"(/.*)?$",  # optional path
            re.IGNORECASE,
        )

        if not pattern.match(url):
            return False, "Please enter a valid web address (e.g., https://example.com)."

        return True, ""

    @classmethod
    def validate_app_name(cls, app_name: str) -> tuple[bool, str]:
        """
        Validates the user-entered application name.
        """
        if not app_name or not app_name.strip():
            return False, "Application name cannot be empty."

        name = app_name.strip()
        if len(name) < 2:
            return False, "Application name must be at least 2 characters long."

        if len(name) > 50:
            return False, "Application name cannot exceed 50 characters."

        return True, ""

    @classmethod
    def validate_package_name(cls, package_name: str) -> tuple[bool, str]:
        """
        Validates a custom Android package name (e.g. 'com.example.app' or 'in.csib.portal').
        """
        if not package_name or not package_name.strip():
            return False, "Package ID cannot be empty."

        pkg = package_name.strip()
        segments = pkg.split(".")
        if len(segments) < 2:
            return False, "Package ID must contain at least two segments separated by a dot (e.g., com.example.app)."

        for seg in segments:
            if not seg:
                return False, "Package ID cannot have empty segments."
            if not seg[0].isalpha():
                return False, f"Each segment in Package ID must start with a letter (invalid: '{seg}')."
            if not re.match(r"^[a-zA-Z0-9_]+$", seg):
                return False, f"Segment '{seg}' contains invalid characters. Only alphanumeric and underscore allowed."
            if seg in JAVA_RESERVED_KEYWORDS:
                return False, f"Segment '{seg}' is a reserved Java keyword."

        return True, ""
