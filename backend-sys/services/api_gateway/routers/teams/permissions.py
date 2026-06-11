from shared.permissions import check_permission, require_owner

# Dependency helper to enforce "teams" permission
require_teams = check_permission("teams")

