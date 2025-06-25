#!/bin/bash

# ==============================================
# SimSelector Security Cleanup Script
# ==============================================
# This script removes any accidentally committed credentials
# and ensures proper security going forward.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "🔒 SimSelector Security Cleanup"
echo "=================================="

# 1. Check current status
print_status "Checking current repository status..."

# Check if sdk_settings.ini exists and is tracked
if git ls-files --error-unmatch sdk_settings.ini >/dev/null 2>&1; then
    print_warning "sdk_settings.ini is currently tracked by git!"
    
    # Remove from tracking but keep local file
    print_status "Removing sdk_settings.ini from git tracking..."
    git rm --cached sdk_settings.ini
    
    # Move to backup if it contains real credentials
    if [[ -f "sdk_settings.ini" ]]; then
        print_status "Backing up current sdk_settings.ini..."
        cp sdk_settings.ini sdk_settings.ini.backup
        print_warning "Your credentials are backed up in sdk_settings.ini.backup"
    fi
else
    print_success "sdk_settings.ini is not currently tracked ✓"
fi

# 2. Ensure .gitignore is protecting sensitive files
print_status "Verifying .gitignore protections..."

if grep -q "sdk_settings.ini" .gitignore 2>/dev/null; then
    print_success ".gitignore already protects sdk_settings.ini ✓"
else
    print_warning ".gitignore needs to be updated"
    echo "" >> .gitignore
    echo "# Sensitive configuration files" >> .gitignore
    echo "sdk_settings.ini" >> .gitignore
    echo "*/sdk_settings.ini" >> .gitignore
    print_success "Updated .gitignore to protect sdk_settings.ini"
fi

# 3. Create secure template if it doesn't exist
if [[ ! -f "sdk_settings.ini.template" ]]; then
    print_status "Creating secure template file..."
    cat > sdk_settings.ini.template << 'EOF'
# SimSelector SDK Settings Template
# Copy this file to sdk_settings.ini and fill in your actual values
# NEVER commit sdk_settings.ini to git!

[csclient]
# Your router/device ID
router_id = YOUR_ROUTER_ID_HERE

# Device connection details
dev_client_ip = YOUR_DEVICE_IP_HERE
dev_client_username = YOUR_USERNAME_HERE
dev_client_password = YOUR_PASSWORD_HERE

# Optional: API settings
api_version = v1
timeout = 30

# Optional: Logging
log_level = INFO
EOF
    print_success "Created sdk_settings.ini.template"
fi

# 4. Set proper file permissions
if [[ -f "sdk_settings.ini" ]]; then
    chmod 600 sdk_settings.ini
    print_success "Set restrictive permissions on sdk_settings.ini (600)"
fi

if [[ -f "sdk_settings.ini.backup" ]]; then
    chmod 600 sdk_settings.ini.backup
    print_success "Set restrictive permissions on backup file (600)"
fi

# 5. Check for other potential credential files
print_status "Scanning for other potential credential files..."

SENSITIVE_PATTERNS=(
    "*.env"
    "config.ini"
    "settings.ini"
    "credentials.*"
    "secrets.*"
    "*.key"
    "*.pem"
)

FOUND_SENSITIVE=false
for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    if git ls-files "$pattern" 2>/dev/null | grep -q .; then
        print_warning "Found potentially sensitive files tracked by git:"
        git ls-files "$pattern"
        FOUND_SENSITIVE=true
    fi
done

if [[ "$FOUND_SENSITIVE" == "false" ]]; then
    print_success "No other sensitive files found in git tracking ✓"
fi

# 6. Provide security recommendations
echo ""
print_status "🛡️  Security Recommendations"
echo "============================"
echo ""
echo "✅ COMPLETED:"
echo "   - Removed sdk_settings.ini from git tracking"
echo "   - Updated .gitignore to protect sensitive files"
echo "   - Created secure template file"
echo "   - Set restrictive file permissions"
echo ""
echo "🔄 NEXT STEPS:"
echo "   1. Copy sdk_settings.ini.template to sdk_settings.ini"
echo "   2. Fill in your actual credentials in sdk_settings.ini"
echo "   3. Verify sdk_settings.ini is never committed:"
echo "      git status  # should not show sdk_settings.ini"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - sdk_settings.ini.backup contains your credentials"
echo "   - Review and delete it when no longer needed"
echo "   - Never share or commit files containing real credentials"
echo ""

# 7. Optional: Remove from git history (DANGEROUS!)
echo "🚨 ADVANCED OPTION:"
echo "   To completely remove sdk_settings.ini from git history:"
echo "   (WARNING: This rewrites history and affects all clones)"
echo ""
echo "   git filter-branch --force --index-filter \\"
echo "     'git rm --cached --ignore-unmatch sdk_settings.ini' \\"
echo "     --prune-empty --tag-name-filter cat -- --all"
echo ""
echo "   Only do this if you're sure and coordinate with your team!"
echo ""

print_success "Security cleanup completed! 🎉"

# 8. Final verification
print_status "Final verification..."
if git status --porcelain | grep -q "sdk_settings.ini"; then
    print_warning "sdk_settings.ini appears in git status - this is expected if you just removed it"
    echo "Run 'git add .' and 'git commit' to complete the cleanup"
else
    print_success "Repository is secure ✓"
fi 