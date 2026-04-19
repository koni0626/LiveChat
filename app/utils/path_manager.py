import os


def build_project_path(base_dir: str, project_id: int) -> str:
    return os.path.join(base_dir, str(project_id))


def ensure_project_dirs(base_dir: str, project_id: int) -> dict:
    root = build_project_path(base_dir, project_id)
    return {
        "root": root,
        "scenes": os.path.join(root, "scenes"),
        "images": os.path.join(root, "images"),
        "exports": os.path.join(root, "exports"),
    }
