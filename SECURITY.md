# Security Guidelines for Cradlepoint SDK Projects

## Overview
This document outlines security practices for the Cradlepoint SDK sample projects repository to prevent accidental exposure of sensitive information.

## 🔒 Sensitive Information Protection

### Files That Should NEVER Be Committed:
- `sdk_settings.ini` - Contains device passwords and credentials
- Any files containing actual passwords, API keys, or device-specific credentials
- State files with runtime data (`simselector_state.json`, etc.)
- Personal device certificates or keys (`.pem`, `.key`, `.crt` files)

### ✅ Safe to Commit:
- `package.ini` files - Application package manifests
- Template files (`.template` extension)
- Source code (`.py` files) - as long as they don't contain hardcoded credentials
- Documentation files

## 🛡️ Security Measures in Place

### 1. Comprehensive .gitignore
The repository includes a comprehensive `.gitignore` file that automatically excludes:
- Configuration files with credentials
- Runtime state files
- Temporary and cache files
- IDE-specific files
- OS-generated files

### 2. Template System
Sensitive configuration files are provided as templates:
- `sdk_settings.ini.template` - Safe template with placeholder values
- Developers copy templates and fill in actual values locally
- Template files can be safely committed

### 3. Git History Cleanup
If sensitive information was previously committed:
```bash
# Remove file from tracking (keeps local copy)
git rm --cached filename

# For complete history cleanup (use with caution):
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch filename' --prune-empty --tag-name-filter cat -- --all
```

## 🚨 Pre-Commit Checklist

Before committing code, always verify:

1. **No passwords or credentials in code**
   ```bash
   # Search for potential secrets
   grep -r -i "password\|secret\|key\|token\|credential" --include="*.py" .
   ```

2. **No sensitive configuration files**
   ```bash
   git status
   # Ensure no .ini files with actual credentials are staged
   ```

3. **Check .gitignore is working**
   ```bash
   git status --ignored
   # Verify sensitive files appear in ignored list
   ```

## 🔧 Development Setup

### Initial Setup:
1. Clone the repository
2. Copy `sdk_settings.ini.template` to `sdk_settings.ini`
3. Fill in your actual device credentials in `sdk_settings.ini`
4. Verify `sdk_settings.ini` is ignored: `git status` should not show it

### Regular Development:
- Never commit actual device passwords or IP addresses
- Use environment variables for sensitive data when possible
- Regularly audit committed files for accidental credential exposure

## 🚫 What NOT to Do

- **Never** commit files containing real passwords or credentials
- **Never** hardcode device IPs, passwords, or API keys in source code
- **Never** disable or modify `.gitignore` to include sensitive files
- **Never** commit state files or runtime data

## ✅ Best Practices

1. **Use environment variables** for sensitive configuration when possible
2. **Use template files** for configuration that needs to be shared
3. **Regularly audit** your commits for sensitive information
4. **Use descriptive commit messages** but avoid including sensitive details
5. **Review pull requests** carefully for credential exposure

## 📞 Incident Response

If sensitive information is accidentally committed:

1. **Immediately** remove the file from tracking: `git rm --cached filename`
2. **Change any exposed credentials** (passwords, keys, etc.)
3. **Consider history cleanup** if the information was pushed to remote
4. **Audit logs** to see if the information was accessed

## 🔍 Monitoring

Regular security checks:
- Monthly audit of tracked files for sensitive content
- Review of new contributors' commits
- Periodic update of `.gitignore` based on new file types

---

**Remember: Security is everyone's responsibility. When in doubt, don't commit it!** 