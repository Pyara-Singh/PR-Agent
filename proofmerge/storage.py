import asyncio
from pathlib import Path
from typing import Protocol

import boto3

from proofmerge.config import Settings


class ArtifactStore(Protocol):
    async def put_text(self, key: str, content: str, content_type: str) -> str: ...


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def put_text(self, key: str, content: str, content_type: str) -> str:
        del content_type
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("Artifact key escaped the configured root")
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")
        return target.as_uri()


class S3ArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
        )

    async def put_text(self, key: str, content: str, content_type: str) -> str:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content.encode(),
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return f"s3://{self.bucket}/{key}"


def build_artifact_store(settings: Settings) -> ArtifactStore:
    if settings.s3_endpoint_url or settings.environment == "production":
        return S3ArtifactStore(settings)
    return LocalArtifactStore(settings.artifact_dir)
