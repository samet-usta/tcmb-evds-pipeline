#!/bin/bash
# Creates the landing bucket when LocalStack is ready.
# In production the bucket is created by IaC, not by the application.
set -euo pipefail

BUCKET="${S3_BUCKET:?S3_BUCKET is not set}"
REGION="${AWS_DEFAULT_REGION:?AWS_DEFAULT_REGION is not set}"

if awslocal s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket already exists: $BUCKET"
else
  awslocal s3 mb "s3://$BUCKET" --region "$REGION"
  echo "Bucket created: $BUCKET"
fi
