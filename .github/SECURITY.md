# Security Policy

## Supported Versions

We actively support the following versions of coldpack with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take the security of coldpack seriously. If you discover a security vulnerability, please follow these steps:

### 1. Do NOT Create a Public Issue

Please **do not** report security vulnerabilities through public GitHub issues. This helps protect our users until a fix can be implemented.

### 2. Report Privately

Send your vulnerability report to: **[rxchi1d@gmail.com]**

Include the following information in your report:

- **Description**: A clear description of the vulnerability
- **Impact**: Potential impact and attack scenarios
- **Reproduction**: Steps to reproduce the vulnerability
- **Environment**: Operating system, Python version, coldpack version
- **Proof of Concept**: If applicable, include a minimal code example

### 3. Expected Response Timeline

- **Initial Response**: Within 48 hours
- **Assessment**: Within 1 week
- **Fix Timeline**: Depends on severity (see below)

## Vulnerability Severity and Response

### Critical (CVE Score 9.0-10.0)
- **Response Time**: 24-48 hours
- **Fix Timeline**: 1-3 days
- **Examples**: Remote code execution, arbitrary file access

### High (CVE Score 7.0-8.9)
- **Response Time**: 48-72 hours
- **Fix Timeline**: 1-7 days
- **Examples**: Data corruption, significant privilege escalation

### Medium (CVE Score 4.0-6.9)
- **Response Time**: 1 week
- **Fix Timeline**: 2-4 weeks
- **Examples**: Information disclosure, limited privilege escalation

### Low (CVE Score 0.1-3.9)
- **Response Time**: 2 weeks
- **Fix Timeline**: Next release cycle
- **Examples**: Minor information leaks, edge case vulnerabilities

## Security Considerations for coldpack

### Archive Processing
- **Zip Bombs**: coldpack includes protection against decompression bombs
- **Path Traversal**: Archive extraction is sandboxed to prevent directory traversal
- **Memory Limits**: Large archive processing includes memory usage controls

### File System Security
- **Temporary Files**: All temporary files are created with secure permissions
- **Path Validation**: Input paths are validated to prevent unauthorized access
- **Permission Preservation**: Archive permissions are handled safely

### Cryptographic Components
- **Hash Verification**: Dual-hash verification (SHA-256 + BLAKE3) for integrity
- **PAR2 Integration**: Secure integration with PAR2 error correction
- **Version Pinning**: Cryptographic libraries are pinned to known-secure versions

### Dependencies
- **Automated Scanning**: Dependabot monitors for vulnerable dependencies
- **Regular Updates**: Security updates are prioritized in our release cycle
- **Minimal Dependencies**: We maintain a minimal dependency footprint

## Security Best Practices for Users

### When Using coldpack
1. **Verify Sources**: Only process archives from trusted sources
2. **Check Integrity**: Always verify archive integrity using coldpack's built-in verification
3. **Sandbox Extraction**: Extract archives in isolated directories
4. **Regular Updates**: Keep coldpack updated to the latest version

### When Reporting Issues
1. **Sensitive Data**: Never include sensitive data in bug reports
2. **Minimal Examples**: Use minimal, non-sensitive examples for reproduction
3. **Environment Details**: Include relevant environment information

## Security Updates

Security updates will be:
- Released as patch versions (e.g., 0.1.1 → 0.1.2)
- Documented in release notes with severity assessment
- Announced through GitHub Security Advisories
- Backported to supported versions when possible

## Bug Bounty Program

Currently, we do not offer a formal bug bounty program. However, we deeply appreciate security researchers who responsibly disclose vulnerabilities and will:

- Acknowledge your contribution in release notes (if desired)
- Provide attribution in our security advisory
- Consider featuring your research in our documentation

## Security Research Guidelines

We encourage security research on coldpack with the following guidelines:

### Permitted Activities
- Testing on your own systems and data
- Analysis of publicly available coldpack source code
- Responsible vulnerability disclosure

### Prohibited Activities
- Testing against third-party systems without permission
- Social engineering of coldpack maintainers or users
- Physical attacks against infrastructure
- Denial of service attacks

## Contact Information

- **Security Contact**: rxchi1d@gmail.com
- **GitHub Repository**: https://github.com/rxchi1d/coldpack
- **Security Advisories**: https://github.com/rxchi1d/coldpack/security/advisories

## Acknowledgments

We thank the security research community for helping keep coldpack and its users safe. Past contributors to coldpack security include:

- (This section will be updated as security researchers contribute)

---

*This security policy is subject to change. Please check back regularly for updates.*

*Last updated: 2025-01-19*
