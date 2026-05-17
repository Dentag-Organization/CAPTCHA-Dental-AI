"""AWS S3 service for handling image uploads"""

import boto3
from botocore.exceptions import ClientError
import logging
import uuid
from pathlib import Path
from typing import Optional
from schemas.user import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_S3_BUCKET

    def _url_to_key(self, file_url: str) -> str:
        """Extract the S3 object key from a full S3 URL."""
        key = file_url.split(f"{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
        return key.replace('+', ' ')

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "image/jpeg",
        folder: str = "images"
    ) -> Optional[str]:
        """Upload bytes to S3 and return the permanent URL, or None on failure."""
        try:
            unique_filename = f"{folder}/{Path(filename).stem}_{uuid.uuid4().hex[:8]}{Path(filename).suffix}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=unique_filename,
                Body=file_data,
                ContentType=content_type
            )
            s3_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
            logger.info(f"Successfully uploaded {filename} to {s3_url}")
            return s3_url
        except ClientError as e:
            logger.error(f"Failed to upload {filename} to S3: {str(e)}")
            return None

    def delete_file(self, file_url: str) -> bool:
        """Delete a file from S3 by its URL. Returns True on success."""
        try:
            key = self._url_to_key(file_url)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted {key} from S3")
            return True
        except (ClientError, IndexError) as e:
            logger.error(f"Failed to delete file from S3: {str(e)}")
            return False

    def list_objects(self, prefix: str) -> list:
        """Return a list of full S3 URLs for all objects under the given prefix."""
        urls = []
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue
                    urls.append(f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key}")
        except ClientError as e:
            logger.error(f"Failed to list objects with prefix '{prefix}': {str(e)}")
        return urls

    def download_file(self, file_url: str, local_path: str) -> bool:
        """Download a file from S3 to a local path. Returns True on success."""
        try:
            self.s3_client.download_file(self.bucket_name, self._url_to_key(file_url), local_path)
            return True
        except (ClientError, IndexError) as e:
            logger.error(f"Failed to download {file_url}: {str(e)}")
            return False

    def generate_presigned_url(self, file_url: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for temporary access to a private S3 object."""
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': self._url_to_key(file_url)},
                ExpiresIn=expiration
            )
            return presigned_url
        except (ClientError, IndexError) as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None


# Global S3 service instance
s3_service = S3Service()