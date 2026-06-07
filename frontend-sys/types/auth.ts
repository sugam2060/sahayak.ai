export type LoginData = {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export type SignupData = LoginData & {
  fullName: string;
  confirmPassword: string;
  organizationName: string;
  organizationSlug: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user_id?: string;
  organization_id?: string;
  is_verified: boolean;
  full_name?: string;
  organization_name?: string;
  organization_slug?: string;
  email?: string;
  role?: string;
  permissions?: string[];
}

export interface AuthBackgroundProps {
  showMesh?: boolean;
  animate?: boolean;
  className?: string;
}
