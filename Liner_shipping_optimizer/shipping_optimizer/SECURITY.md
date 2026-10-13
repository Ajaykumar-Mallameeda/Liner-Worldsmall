# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.0-rc1 | ✅ |

## Reporting a Vulnerability

This is a research/academic project. If you discover a security vulnerability, please open an issue describing the concern. Do not disclose vulnerabilities publicly until they have been addressed.

## Security Considerations

- This system is designed for research and demonstration purposes
- The mock WebSocket server (`mock-server.cjs`) is for development use only
- In production, configure proper authentication, HTTPS/WSS, and network isolation
- `pipeline_output.json` contains operational data — restrict access in production deployments
- No user authentication is implemented — this is a local/institutional deployment tool
