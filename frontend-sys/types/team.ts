export interface TeamMember {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface Team {
  id: string;
  organization_id: string;
  team_name: string;
  description?: string;
  role: string;
  permissions: string[];
  created_at: string;
  members: TeamMember[];
}

export interface InvitePayload {
  full_name: string;
  email: string;
  password?: string;
  role: string;
  team_id?: string;
}

export interface TeamCreatePayload {
  team_name: string;
  description?: string;
  role: string;
  permissions: string[];
}
