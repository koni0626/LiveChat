from datetime import datetime

from ..extensions import db
from ..models.asset import Asset

class AssetRepository:
    def list_by_project(
        self, project_id: int, include_deleted: bool = False, asset_type: str | None = None
    ):
        query = Asset.query.filter(Asset.project_id == project_id)
        if asset_type:
            query = query.filter(Asset.asset_type == asset_type)
        if not include_deleted:
            query = query.filter(Asset.deleted_at.is_(None))
        return query.order_by(Asset.id).all()

    def get(self, asset_id: int, include_deleted: bool = False):
        query = Asset.query.filter(Asset.id == asset_id)
        if not include_deleted:
            query = query.filter(Asset.deleted_at.is_(None))
        return query.first()

    def create(self, project_id: int | None, payload: dict):
        asset = Asset(
            project_id=project_id if project_id is not None else payload.get("project_id"),
            asset_type=payload["asset_type"],
            file_name=payload["file_name"],
            file_path=payload["file_path"],
            mime_type=payload.get("mime_type"),
            file_size=payload.get("file_size"),
            width=payload.get("width"),
            height=payload.get("height"),
            checksum=payload.get("checksum"),
            metadata_json=payload.get("metadata_json"),
        )
        db.session.add(asset)
        db.session.commit()
        return asset

    def update(self, asset_id: int, payload: dict):
        asset = self.get(asset_id, include_deleted=True)
        if not asset or asset.deleted_at is not None:
            return None
        for field in (
            "asset_type",
            "file_name",
            "file_path",
            "mime_type",
            "file_size",
            "width",
            "height",
            "checksum",
            "metadata_json",
            "project_id",
        ):
            if field in payload:
                setattr(asset, field, payload[field])
        db.session.commit()
        return asset

    def delete(self, asset_id: int):
        asset = self.get(asset_id, include_deleted=True)
        if not asset:
            return False
        if asset.deleted_at is not None:
            return True
        asset.deleted_at = datetime.utcnow()
        db.session.commit()
        return True

    def restore(self, asset_id: int):
        asset = self.get(asset_id, include_deleted=True)
        if not asset or asset.deleted_at is None:
            return None
        asset.deleted_at = None
        db.session.commit()
        return asset
