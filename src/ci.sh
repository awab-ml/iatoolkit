#!/usr/bin/env bash

set -euo pipefail

registry=998432919236.dkr.ecr.us-east-1.amazonaws.com
namespace=maxxa-eks
project=iatoolkit

build_and_push() {
  image_tag="$1"

  echo "Building docker image..."
  docker build -t $project:$image_tag -f Dockerfile .

  echo "Signing in to AWS ECR..."
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $registry

  echo "Pushing docker image $project/$image_tag to ECR..."
  docker tag $project:$image_tag $registry/$namespace/$project:$image_tag
  docker push $registry/$namespace/$project:$image_tag
}

if [ $# -ne 1 ]; then
  echo "Usage: $0 {ci|dev|prod|test|cov}"
  exit 1
fi

case "$1" in
  "ci")
    echo "Running CI build..."
    docker build -t $project:ci --target base -f Dockerfile .
    ;;
  "dev")
    echo "Running development build..."
    build_and_push $(date -u +%y%m%d%H%M) 
    ;;
  "prod")
    echo "Running production build..."
    build_and_push $(date -u +%y%m%d%H%M)-prod 
    ;;
  "test")
    echo "Running tests..."
    docker run --rm $project:ci pytest tests/
    ;;
  "cov")
    echo "Running tests with coverage..."
    docker run --rm $project:ci pytest --cov=. --cov-report=term --cov-fail-under=80
    ;;
  *)
    echo "Usage: $0 {ci|dev|prod|test|cov}"
    exit 1
    ;;
esac
