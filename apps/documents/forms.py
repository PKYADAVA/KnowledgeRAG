"""Document upload form with file validation."""
import magic
from django import forms
from django.conf import settings
from .models import Document


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ("title", "description", "file")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Document title",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                    "rows": 2,
                    "placeholder": "Optional description...",
                }
            ),
            "file": forms.FileInput(
                attrs={
                    "class": "hidden",
                    "accept": ".pdf,.docx,.txt,.md",
                    "id": "file-upload",
                }
            ),
        }

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if not file:
            return file

        # Size check
        if file.size > settings.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(
                f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        # Extension check
        ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
        if ext not in settings.ALLOWED_FILE_TYPES:
            raise forms.ValidationError(
                f"Unsupported file type. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES).upper()}"
            )

        # MIME type check via python-magic
        try:
            file.seek(0)
            mime = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)
            allowed_mimes = {
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
                "text/markdown",
                "text/x-markdown",
            }
            if mime not in allowed_mimes:
                raise forms.ValidationError(
                    f"File content does not match its extension (detected: {mime})."
                )
        except Exception as exc:
            if "File content" in str(exc):
                raise
            # If magic fails for any other reason, pass through (non-critical)

        return file

    def clean_title(self):
        title = self.cleaned_data.get("title", "").strip()
        if not title:
            raise forms.ValidationError("Title is required.")
        return title
