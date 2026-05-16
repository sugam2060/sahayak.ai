import { SignupData } from '@/types/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface RegistrationResponse {
  organization_id: string;
  user_id: string;
  message: string;
}

export interface ApiError {
  detail: string;
}

export const registerUser = async (data: SignupData): Promise<RegistrationResponse> => {
  const payload = {
    org_name: data.organizationName,
    org_slug: data.organizationSlug,
    full_name: data.fullName,
    email: data.email,
    password: data.password,
  };

  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || 'An error occurred during registration');
  }

  return result as RegistrationResponse;
};
