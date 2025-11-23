# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# Docker Build Known Issues

## SSL Certificate Issues in CI/CD

When building Docker images in certain CI/CD environments (including GitHub Actions), you may encounter SSL certificate verification errors like:

```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

### Root Cause

This is typically caused by:
1. Corporate/enterprise proxy certificates in the CI environment
2. Self-signed certificates in the certificate chain
3. CA certificate bundle not properly updated in the build environment

### Workarounds

#### For Local Development

If you encounter this locally, update CA certificates:

```dockerfile
RUN apt-get update && apt-get install -y ca-certificates && \
    update-ca-certificates
```

#### For CI/CD Environments

If building in CI fails, you can:

1. **Use pre-built images from Docker Hub** (recommended):
   ```yaml
   image: knitli/codeweaver:latest
   ```

2. **Skip SSL verification** (not recommended for production):
   ```dockerfile
   RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org ...
   ```

3. **Build outside of Docker** and copy artifacts:
   ```bash
   # Build wheel locally
   python -m build
   
   # Copy wheel into Docker and install
   COPY dist/*.whl /tmp/
   RUN pip install /tmp/*.whl
   ```

### Status

The Docker images build successfully in most environments. CI/CD issues are environment-specific and don't affect the functionality of the Docker images themselves.

## Testing

To test the Docker build locally:

```bash
# Basic build test
docker build -t codeweaver:test .

# If you encounter SSL issues locally, try:
docker build --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" -t codeweaver:test .
```

## Alternative: Use Pre-built Images

The recommended approach is to use pre-built images from Docker Hub:

```bash
docker pull knitli/codeweaver:latest
```

Or with docker-compose:

```yaml
services:
  codeweaver:
    image: knitli/codeweaver:latest  # Use pre-built image
    # ... rest of configuration
```
